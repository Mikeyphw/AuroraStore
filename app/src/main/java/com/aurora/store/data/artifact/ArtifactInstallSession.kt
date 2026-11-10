/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.os.Build
import com.aurora.store.data.installer.verification.ApkVerificationException
import java.security.MessageDigest
import java.util.Locale

/** OS install is an explicit, source-bound, user-confirmed session; never a Play download. */
internal object ArtifactInstallSession {
    private const val PREFS = "artifact_import_session_receipts"
    const val EXTRA_SESSION = "artifact_session"
    const val EXTRA_GENERATION = "artifact_generation"

    fun install(
        context: Context,
        imported: ArtifactApkVerifier.VerifiedImport,
        approvedInstall: Boolean,
        approvedUnknownPublisher: Boolean,
        approvedDowngrade: Boolean,
        cancelled: () -> Boolean
    ): Int {
        val id = imported.attempt
        val evidence = ArtifactIndependentEvidence.fromVerifiedImport(imported)
        val review = ArtifactImportDecision.Review(
            id.packageName,
            id.versionCode,
            signerVerified = true,
            installedSignerMatches = imported.signerMatchesInstalled,
            installedVersion = imported.installedVersion,
            trustedPublisherAnchor = false,
            userApprovedInstall = approvedInstall,
            userAcceptedUnknownPublisher = approvedUnknownPublisher,
            userApprovedDowngrade = approvedDowngrade
        )
        val blocks = ArtifactImportDecision.blockers(review)
        if (blocks.isNotEmpty()) {
            throw ApkVerificationException("Import cannot proceed: ${blocks.joinToString()}")
        }
        if (cancelled()) throw ApkVerificationException("Import cancelled")
        ArtifactApkVerifier.revalidateForInstall(context, imported, cancelled)
        val installer = context.packageManager.packageInstaller
        val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL)
        params.setAppPackageName(id.packageName)
        params.setSize(imported.totalApkBytes)
        if (Build.VERSION.SDK_INT >= 31) {
            params.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_REQUIRED)
        }
        if (Build.VERSION.SDK_INT >= 33) {
            params.setPackageSource(PackageInstaller.PACKAGE_SOURCE_LOCAL_FILE)
        }
        val sessionId = installer.createSession(params)
        var committed = false
        var previousLastSession = -1
        try {
            installer.openSession(sessionId).use { session ->
                for (file in imported.files) {
                    if (cancelled()) throw ApkVerificationException("Import cancelled")
                    if (file.file.length() != file.byteCount) {
                        throw ApkVerificationException("Private staged APK size changed")
                    }
                    // Hash exactly what is written to the OS-owned session, rather
                    // than hashing a separate earlier read vulnerable to file swap.
                    val writtenHash = MessageDigest.getInstance("SHA-256")
                    var written = 0L
                    session.openWrite(file.file.name, 0L, file.byteCount).use { out ->
                        file.file.inputStream().use { input ->
                            val buffer = ByteArray(64 * 1024)
                            while (true) {
                                if (cancelled()) throw ApkVerificationException("Import cancelled")
                                val n = input.read(buffer)
                                if (n < 0) break
                                written += n
                                if (written > file.byteCount) {
                                    throw ApkVerificationException("APK grew during installation")
                                }
                                writtenHash.update(buffer, 0, n)
                                out.write(buffer, 0, n)
                            }
                        }
                        if (written != file.byteCount ||
                            !writtenHash.digest().joinToString("") {
                                "%02x".format(Locale.ROOT, it.toInt() and 0xff)
                            }.equals(file.sha256, ignoreCase = false)
                        ) throw ApkVerificationException("APK changed while writing Android session")
                        session.fsync(out)
                    }
                }
                if (cancelled()) throw ApkVerificationException("Import cancelled")
                // Each session owns its own CAS receipt; never overwrite another
                // still-pending session's generation, source, signer or result.
                val preferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                previousLastSession = preferences.getInt("last_session", -1)
                if (!preferences.edit()
                        .putLong(key(sessionId, "generation"), id.attemptGeneration)
                        .putString(key(sessionId, "package"), id.packageName)
                        .putLong(key(sessionId, "version"), id.versionCode)
                        .putString(key(sessionId, "source"), id.provenance.source.name)
                        .putString(key(sessionId, "origin_family"), evidence.distribution.name)
                        .putString(key(sessionId, "evidence_scope"), "INDEPENDENT_NON_PLAY")
                        .putString(key(sessionId, "apk_sha256"), evidence.apkSha256.joinToString(","))
                        .putString(
                            key(sessionId, "signer"),
                            imported.signerSha256.sorted().joinToString(",")
                        )
                        // Private, per-session evidence; do not persist URI/URL or claim Play proof.
                        .putString(key(sessionId, "source_reference"),
                            id.provenance.displayOrigin.orEmpty())
                        .putString(key(sessionId, "source_sha256"), imported.staged.originalSha256)
                        .putInt(key(sessionId, "apk_count"), imported.files.size)
                        .putLong(key(sessionId, "apk_bytes"), imported.totalApkBytes)
                        .putString(key(sessionId, "trust"), imported.trustTier.name)
                        .putBoolean(key(sessionId, "consent_install"), approvedInstall)
                        .putBoolean(key(sessionId, "consent_unknown"), approvedUnknownPublisher)
                        .putBoolean(key(sessionId, "consent_downgrade"), approvedDowngrade)
                        .putString(
                            key(sessionId, "state"),
                            ArtifactSessionReceiptPolicy.State.AWAITING_ANDROID.name
                        )
                        .putInt("last_session", sessionId)
                        .commit()
                ) throw ApkVerificationException("Cannot persist install attempt")
                val callback = Intent(context, ArtifactInstallStatusReceiver::class.java).apply {
                    putExtra(EXTRA_SESSION, sessionId)
                    putExtra(EXTRA_GENERATION, id.attemptGeneration)
                }
                val flags = PendingIntent.FLAG_UPDATE_CURRENT or
                    if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0
                val pending = PendingIntent.getBroadcast(context, sessionId, callback, flags)
                if (cancelled()) throw ApkVerificationException("Import cancelled before commit")
                session.commit(pending.intentSender)
                committed = true
            }
            // Cleanup cannot retroactively turn an already committed OS session into
            // an app-level failure; Android now owns the install outcome.
            runCatching { imported.discard() }
            return sessionId
        } catch (error: Exception) {
            if (!committed) runCatching { installer.abandonSession(sessionId) }
            if (!committed) {
                val preferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                val cleanup = preferences.edit()
                    .remove(key(sessionId, "generation"))
                    .remove(key(sessionId, "state"))
                    .remove(key(sessionId, "package"))
                    .remove(key(sessionId, "version"))
                    .remove(key(sessionId, "source"))
                    .remove(key(sessionId, "origin_family"))
                    .remove(key(sessionId, "evidence_scope"))
                    .remove(key(sessionId, "apk_sha256"))
                    .remove(key(sessionId, "signer"))
                    .remove(key(sessionId, "source_reference"))
                    .remove(key(sessionId, "source_sha256"))
                    .remove(key(sessionId, "apk_count"))
                    .remove(key(sessionId, "apk_bytes"))
                    .remove(key(sessionId, "trust"))
                    .remove(key(sessionId, "consent_install"))
                    .remove(key(sessionId, "consent_unknown"))
                    .remove(key(sessionId, "consent_downgrade"))
                // Failed pre-commit requests must not hide an older valid receipt.
                if (preferences.getInt("last_session", -1) == sessionId) {
                    if (previousLastSession >= 0) cleanup.putInt("last_session", previousLastSession)
                    else cleanup.remove("last_session")
                }
                cleanup.commit()
            }
            throw error
        }
    }

    private fun key(session: Int, field: String): String = "session_${session}_$field"

    /** The OS receipt is an outcome report, never a publisher-authentication claim. */
    fun lastResult(context: Context): String {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val session = prefs.getInt("last_session", -1)
        if (session < 0) return "No Android installation attempt recorded"
        val pkg = prefs.getString(key(session, "package"), null)
            ?: return "No Android installation attempt recorded"
        val version = prefs.getLong(key(session, "version"), -1L)
        val source = prefs.getString(key(session, "source"), "UNKNOWN")
        val family = prefs.getString(key(session, "origin_family"), "UNKNOWN")
        val scope = prefs.getString(key(session, "evidence_scope"), "UNKNOWN")
        val apkHashes = prefs.getString(key(session, "apk_sha256"), "").orEmpty()
        val reference = prefs.getString(key(session, "source_reference"), "").orEmpty()
        val signer = prefs.getString(key(session, "signer"), "").orEmpty()
        val sourceHash = prefs.getString(key(session, "source_sha256"), "").orEmpty()
        val trust = prefs.getString(key(session, "trust"), "UNKNOWN")
        val state = prefs.getString(key(session, "state"), null)
            ?.let { runCatching { ArtifactSessionReceiptPolicy.State.valueOf(it) }.getOrNull() }
        val status = ArtifactReviewPresentation.androidResult(state)
        return buildString {
            append("Package: $pkg · version code: $version\n")
            append("OS session: $session\n")
            append("Outcome: $status\n")
            append("Source claim: $source ($family)\n")
            append("Evidence scope: $scope (not Play verification)\n")
            append("Attempt generation: ${prefs.getLong(key(session, "generation"), -1L)}\n")
            append("APK file SHA-256: ${apkHashes.ifEmpty { "unavailable" }}\n")
            if (reference.isNotEmpty()) append(" · unverified reference: $reference")
            append("\nPublisher trust at review: $trust (never Play evidence)\n")
            append("Selected file SHA-256: ${sourceHash.ifEmpty { "unavailable" }}\n")
            append("Verified signer SHA-256: ${signer.ifEmpty { "unavailable" }}\n")
            append("APK count: ${prefs.getInt(key(session, "apk_count"), 0)} · ")
            append("APK bytes: ${prefs.getLong(key(session, "apk_bytes"), 0L)}\n")
            append("User approved install: ${prefs.getBoolean(key(session, "consent_install"), false)}")
            append(" · unverified publisher: ${prefs.getBoolean(key(session, "consent_unknown"), false)}")
            append(" · downgrade: ${prefs.getBoolean(key(session, "consent_downgrade"), false)}")
            if (state == ArtifactSessionReceiptPolicy.State.ANDROID_REJECTED) {
                val code = prefs.getInt(key(session, "android_status_code"), -1)
                append("\nAndroid reason: ${ArtifactReviewPresentation.androidFailureReason(code)} (code $code)")
            }
        }
    }

    /** Reject stale/foreign OS session callbacks and forbid terminal-state replay. */
    fun recordStatus(
        context: Context,
        session: Int,
        generation: Long,
        osSession: Int,
        code: Int
    ): Boolean {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (session <= 0 || osSession != session || generation <= 0L ||
            prefs.getLong(key(session, "generation"), -1) != generation
        ) return false
        val previous = prefs.getString(key(session, "state"), null)
            ?.let { runCatching { ArtifactSessionReceiptPolicy.State.valueOf(it) }.getOrNull() }
            ?: return false
        if (code != PackageInstaller.STATUS_PENDING_USER_ACTION &&
            code != PackageInstaller.STATUS_SUCCESS && code !in 1..7
        ) return false
        val event = when (code) {
            PackageInstaller.STATUS_PENDING_USER_ACTION ->
                ArtifactSessionReceiptPolicy.Event.USER_APPROVAL_REQUIRED
            PackageInstaller.STATUS_SUCCESS -> ArtifactSessionReceiptPolicy.Event.INSTALLED
            else -> ArtifactSessionReceiptPolicy.Event.REJECTED
        }
        val next = ArtifactSessionReceiptPolicy.next(previous, event) ?: return false
        return prefs.edit()
            .putString(key(session, "state"), next.name)
            .putInt(key(session, "android_status_code"), code)
            .commit()
    }

    /** Don't claim that Android rejected the APK merely because confirmation UI failed. */
    fun recordPresentationFailure(context: Context, session: Int, generation: Long): Boolean {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (session <= 0 || prefs.getLong(key(session, "generation"), -1) != generation) {
            return false
        }
        val current = prefs.getString(key(session, "state"), null)
            ?.let { runCatching { ArtifactSessionReceiptPolicy.State.valueOf(it) }.getOrNull() }
            ?: return false
        val next = ArtifactSessionReceiptPolicy.next(
            current, ArtifactSessionReceiptPolicy.Event.APPROVAL_PRESENTATION_FAILED
        ) ?: return false
        return prefs.edit().putString(key(session, "state"), next.name).commit()
    }
}
