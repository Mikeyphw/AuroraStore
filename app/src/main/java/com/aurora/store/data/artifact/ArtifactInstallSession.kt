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

/** OS install is an explicit, source-bound, user-confirmed session; never a Play download. */
internal object ArtifactInstallSession {
    private const val PREFS = "artifact_import_session_receipts"
    const val EXTRA_SESSION = "artifact_session"
    const val EXTRA_GENERATION = "artifact_generation"

    fun install(
        context: Context,
        imported: ArtifactApkVerifier.VerifiedImport,
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
            userApprovedInstall = true,
            userAcceptedUnknownPublisher = approvedUnknownPublisher,
            userApprovedDowngrade = approvedDowngrade
        )
        val blocks = ArtifactImportDecision.blockers(review)
        if (blocks.isNotEmpty()) throw ApkVerificationException(
            "Import cannot proceed: ${blocks.joinToString()}"
        )
        if (cancelled()) throw ApkVerificationException("Import cancelled")
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
                    if (file.file.length() != file.byteCount ||
                        ArtifactPrivateStager.sha256(file.file, cancelled) != file.sha256
                    ) throw ApkVerificationException("Private staged APK changed")
                    session.openWrite(file.file.name, 0L, file.byteCount).use { out ->
                        file.file.inputStream().use { input ->
                            val buffer = ByteArray(64 * 1024)
                            while (true) {
                                if (cancelled()) throw ApkVerificationException("Import cancelled")
                                val n = input.read(buffer)
                                if (n < 0) break
                                out.write(buffer, 0, n)
                            }
                        }
                        session.fsync(out)
                    }
                }
                if (cancelled()) throw ApkVerificationException("Import cancelled")
                // Persist only public, source-bound identity; never URI, tokens or APK bytes.
                val preferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                if (!preferences.edit()
                        .putInt("session", sessionId)
                        .putLong("generation", id.attemptGeneration)
                        .putString("package", id.packageName)
                        .putLong("version", id.versionCode)
                        .putString("source", id.provenance.source.name)
                        .putString("signer", imported.signerSha256.sorted().joinToString(","))
                        .putString("result", "AWAITING_ANDROID")
                        .commit()
                ) throw ApkVerificationException("Cannot persist install attempt")
                val callback = Intent(context, ArtifactInstallStatusReceiver::class.java).apply {
                    putExtra(EXTRA_SESSION, sessionId)
                    putExtra(EXTRA_GENERATION, id.attemptGeneration)
                }
                val flags = PendingIntent.FLAG_UPDATE_CURRENT or
                    if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0
                val pending = PendingIntent.getBroadcast(context, sessionId, callback, flags)
                session.commit(pending.intentSender)
                committed = true
            }
            imported.discard()
            return sessionId
        } catch (error: Exception) {
            if (!committed) runCatching { installer.abandonSession(sessionId) }
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                .remove("session").remove("generation")
                .putString("result", "FAILED_TO_STAGE").apply()
            throw error
        }
    }

    fun lastResult(context: Context): String {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val pkg = prefs.getString("package", null) ?: return "No installation attempted"
        return "$pkg · ${prefs.getString("result", "UNKNOWN")}"
    }

    fun recordStatus(context: Context, session: Int, generation: Long, code: Int): Boolean {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (session <= 0 || prefs.getInt("session", -1) != session ||
            generation <= 0L || prefs.getLong("generation", -1) != generation
        ) return false
        val status = when (code) {
            PackageInstaller.STATUS_PENDING_USER_ACTION -> "AWAITING_USER_APPROVAL"
            PackageInstaller.STATUS_SUCCESS -> "INSTALLED_BY_ANDROID"
            else -> "ANDROID_REJECTED_$code"
        }
        return prefs.edit().putString("result", status).commit()
    }
}
