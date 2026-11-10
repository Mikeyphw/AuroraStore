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
                if (!preferences.edit()
                        .putLong(key(sessionId, "generation"), id.attemptGeneration)
                        .putString(key(sessionId, "package"), id.packageName)
                        .putLong(key(sessionId, "version"), id.versionCode)
                        .putString(key(sessionId, "source"), id.provenance.source.name)
                        .putString(
                            key(sessionId, "signer"),
                            imported.signerSha256.sorted().joinToString(",")
                        )
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
                context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                    .remove(key(sessionId, "generation"))
                    .remove(key(sessionId, "state"))
                    .remove(key(sessionId, "package"))
                    .remove(key(sessionId, "version"))
                    .remove(key(sessionId, "source"))
                    .remove(key(sessionId, "signer"))
                    .commit()
            }
            throw error
        }
    }

    private fun key(session: Int, field: String): String = "session_${session}_$field"

    fun lastResult(context: Context): String {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val session = prefs.getInt("last_session", -1)
        if (session < 0) return "No installation attempted"
        val pkg = prefs.getString(key(session, "package"), null)
            ?: return "No installation attempted"
        val version = prefs.getLong(key(session, "version"), -1L)
        val source = prefs.getString(key(session, "source"), "UNKNOWN")
        val signer = prefs.getString(key(session, "signer"), "").orEmpty().take(16)
        val state = prefs.getString(key(session, "state"), "UNKNOWN")
        return "$pkg v$version · $state · $source · signer $signer"
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
