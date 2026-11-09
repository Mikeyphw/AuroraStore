/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.installer.verification

import android.content.Context
import android.os.Build
import com.aurora.gplayapi.model.AppFile
import com.aurora.store.data.room.download.Download
import com.aurora.store.util.PathUtil
import java.security.MessageDigest

/**
 * Evidence that the R3B verifier accepted the exact downloaded APK set.
 * Cannot be manufactured by a Play listing, a download URL, or a source-only test fixture.
 */
internal class R3bVerifiedProof private constructor(
    val packageName: String,
    val versionCode: Long,
    val attemptGeneration: Long,
    val resolvedFileCount: Int,
    /** Read only from the verified BASE APK, not the Play listing. Null is unknown. */
    val verifiedMinSdk: Int?
) {
    companion object {
        /** Only this factory can mint a proof. It invokes the production R3B gate. */
        fun verify(
            context: Context,
            download: Download,
            interrupted: () -> Boolean
        ): R3bVerifiedProof {
            ApkSetVerifier.verify(context, download, interrupted)
            if (interrupted()) {
                throw ApkVerificationException("APK verification was cancelled")
            }
            val apkCount = download.fileList.count {
                it.type == AppFile.Type.BASE || it.type == AppFile.Type.SPLIT
            }
            if (apkCount <= 0 || download.fileList.isEmpty()) {
                throw ApkVerificationException("Verified APK set is missing its base application")
            }
            val base = download.fileList.single { it.type == AppFile.Type.BASE }
            val file = PathUtil.getLocalFile(context, base, download)
            // Parse minSdk from the same exact downloaded bytes R3B just verified. The
            // second digest protects against a cache swap while the archive is parsed.
            // ApplicationInfo.minSdkVersion was introduced in API 24. Older devices
            // retain UNKNOWN rather than asserting an SDK incompatibility.
            val minSdk = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                context.packageManager.getPackageArchiveInfo(file.absolutePath, 0)
                    ?.applicationInfo?.minSdkVersion?.takeIf { it > 0 }
            } else {
                null
            }
            val algorithm = if (base.sha256.isNotBlank()) "SHA-256" else "SHA-1"
            val expected = if (base.sha256.isNotBlank()) base.sha256 else base.sha1
            val digest = MessageDigest.getInstance(algorithm)
            file.inputStream().use { input ->
                val block = ByteArray(DEFAULT_BUFFER_SIZE)
                while (true) {
                    if (interrupted()) {
                        throw ApkVerificationException("APK verification was cancelled")
                    }
                    val count = input.read(block)
                    if (count < 0) break
                    digest.update(block, 0, count)
                }
            }
            val actual = digest.digest().joinToString("") { "%02x".format(it.toInt() and 0xff) }
            if (!actual.equals(expected, ignoreCase = true)) {
                throw ApkVerificationException(
                    "Verified base APK changed during manifest inspection"
                )
            }
            if (interrupted()) {
                throw ApkVerificationException("APK verification was cancelled")
            }
            return R3bVerifiedProof(
                packageName = download.packageName,
                versionCode = download.versionCode,
                attemptGeneration = download.downloadedAt,
                resolvedFileCount = download.fileList.size,
                verifiedMinSdk = minSdk
            )
        }
    }
}
