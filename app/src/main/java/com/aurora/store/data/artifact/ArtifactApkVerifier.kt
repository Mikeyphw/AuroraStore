/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import android.content.Context
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.content.pm.Signature
import android.content.pm.SigningInfo
import android.os.Build
import com.aurora.store.data.installer.verification.ApkIdentity
import com.aurora.store.data.installer.verification.ApkSetPolicy
import com.aurora.store.data.installer.verification.ApkVerificationException
import com.aurora.store.data.installer.verification.BinaryApkManifest
import java.io.File
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.Locale

/**
 * Independent non-Play evidence. Must never call matchesPlayDigest, mint a Play
 * evidence row, or accept a provider checksum as proof of legitimate publisher.
 */
internal object ArtifactApkVerifier {
    class VerifiedImport internal constructor(
        val staged: ArtifactPrivateStager.Staged,
        val attempt: ArtifactAttempt,
        val signerSha256: Set<String>,
        val trustTier: ArtifactTrustTier,
        val installedVersion: Long?,
        val signerMatchesInstalled: Boolean?,
        val splitNames: List<String?>,
        val totalApkBytes: Long
    ) {
        val files: List<ArtifactPrivateStager.CopiedApk> get() = staged.apks
        val isPlayEvidence: Boolean get() = false
        fun discard() = staged.discard()
    }

    private fun digest(signature: Signature): String = MessageDigest.getInstance("SHA-256")
        .digest(signature.toByteArray()).joinToString("") { "%02x".format(Locale.ROOT, it.toInt() and 0xff) }

    private fun signed(info: PackageInfo): Set<String> = if (Build.VERSION.SDK_INT >= 28) {
        info.signingInfo?.apkContentsSigners.orEmpty().map(::digest).toSet()
    } else {
        @Suppress("DEPRECATION")
        info.signatures.orEmpty().map(::digest).toSet()
    }

    private fun archiveInfo(manager: PackageManager, file: File): PackageInfo? {
        val flags = if (Build.VERSION.SDK_INT >= 28) PackageManager.GET_SIGNING_CERTIFICATES
            else {
                @Suppress("DEPRECATION")
                PackageManager.GET_SIGNATURES
            }
        return manager.getPackageArchiveInfo(file.absolutePath, flags)
    }

    private fun signerFor(manager: PackageManager, file: File): Set<String> {
        // getPackageArchiveInfo() is not a standalone proof that the complete
        // APK v2/v3 signing block was cryptographically authenticated. Until a
        // separately audited apksig verifier is integrated, fail closed on older APIs.
        if (Build.VERSION.SDK_INT < 36) {
            throw ApkVerificationException(
                "Independent APK signature verification requires Android API 36"
            )
        }
        val info = archiveInfo(manager, file)
        if (Build.VERSION.SDK_INT >= 36) {
            val authenticated = try {
                PackageManager.getVerifiedSigningInfo(
                    file.absolutePath,
                    SigningInfo.VERSION_SIGNING_BLOCK_V2
                ).apkContentsSigners.orEmpty().map(::digest).toSet()
            } catch (_: Exception) {
                throw ApkVerificationException("APK v2+ signature verification failed")
            }
            if (authenticated.isEmpty() || info?.let(::signed)?.let {
                    it.isNotEmpty() && it != authenticated
                } == true
            ) throw ApkVerificationException("Archive signing identity mismatch")
            return authenticated
        }
        throw ApkVerificationException("Independent APK verifier is unavailable")
    }

    private fun installed(manager: PackageManager, pkg: String): PackageInfo? = try {
        val flags = if (Build.VERSION.SDK_INT >= 28) PackageManager.GET_SIGNING_CERTIFICATES
            else {
                @Suppress("DEPRECATION")
                PackageManager.GET_SIGNATURES
            }
        manager.getPackageInfo(pkg, flags)
    } catch (_: PackageManager.NameNotFoundException) {
        null
    }

    /**
     * Fresh, non-Play security revalidation after consent, immediately before OS session.
     * Source claims cannot authenticate the installed app or reuse old signing evidence.
     * Any package/version/signature/split/installed-version drift cancels this attempt.
     */
    fun revalidateForInstall(
        context: Context,
        imported: VerifiedImport,
        cancelled: () -> Boolean
    ) {
        if (cancelled()) throw ApkVerificationException("Import cancelled before installation")
        val manager = context.packageManager
        val pieces = imported.files.map { part ->
            if (cancelled() || !part.file.isFile || part.file.length() != part.byteCount ||
                ArtifactPrivateStager.sha256(part.file, cancelled) != part.sha256
            ) {
                throw ApkVerificationException("Private APK changed before installation")
            }
            val identity = BinaryApkManifest.read(part.file)
            val signer = signerFor(manager, part.file)
            ApkIdentity(
                part.file.name, identity.packageName, identity.versionCode,
                identity.splitName.isNullOrEmpty(), signer
            ) to identity.splitName
        }
        val attempt = imported.attempt
        ApkSetPolicy.check(attempt.packageName, attempt.versionCode, pieces.map { it.first })
        if (pieces.map { it.second } != imported.splitNames ||
            pieces.first { it.first.isBase }.first.signerDigests != imported.signerSha256
        ) {
            throw ApkVerificationException("Verified split or signer identity changed")
        }
        val current = installed(manager, attempt.packageName)
        @Suppress("DEPRECATION")
        val version = current?.let {
            if (Build.VERSION.SDK_INT >= 28) it.longVersionCode else it.versionCode.toLong()
        }
        if (version != imported.installedVersion) {
            throw ApkVerificationException("Installed app changed after import review")
        }
        val continuity = current?.let { installedInfo ->
            val active = signed(installedInfo)
            val history = if (Build.VERSION.SDK_INT >= 28) {
                installedInfo.signingInfo?.signingCertificateHistory.orEmpty()
                    .map(::digest).toSet()
            } else active
            ApkSetPolicy.compatibleInstalledSigners(imported.signerSha256, active, history)
        }
        if (continuity != imported.signerMatchesInstalled || continuity == false) {
            throw ApkVerificationException("Installed app signer changed after import review")
        }
        for (part in imported.files) {
            if (cancelled() || !part.file.isFile || part.file.length() != part.byteCount ||
                ArtifactPrivateStager.sha256(part.file, cancelled) != part.sha256
            ) {
                throw ApkVerificationException("Verified APK bytes changed before session creation")
            }
        }
    }

    fun verify(
        context: Context,
        staged: ArtifactPrivateStager.Staged,
        provenance: ArtifactProvenance,
        cancelled: () -> Boolean
    ): VerifiedImport {
        val manager = context.packageManager
        val ids = staged.apks.map { part ->
            if (cancelled()) throw ApkVerificationException("Import was cancelled")
            if (!part.file.isFile || part.file.length() != part.byteCount ||
                ArtifactPrivateStager.sha256(part.file, cancelled) != part.sha256
            ) throw ApkVerificationException("Staged file changed since copying")
            val manifest = BinaryApkManifest.read(part.file)
            val names = signerFor(manager, part.file)
            Pair(
                ApkIdentity(
                    part.file.name,
                    manifest.packageName,
                    manifest.versionCode,
                    manifest.splitName.isNullOrEmpty(),
                    names
                ),
                manifest.splitName
            )
        }
        val base = ids.singleOrNull { it.first.isBase }?.first
            ?: throw ApkVerificationException("Archive needs exactly one base APK")
        ApkSetPolicy.check(base.packageName, base.versionCode, ids.map { it.first })
        // Reject duplicate split identities even when archive entry filenames differ.
        val splitNames = ids.map { it.second }
        if (splitNames.filterNotNull().size != splitNames.filterNotNull().distinct().size) {
            throw ApkVerificationException("Duplicate split manifest identity")
        }
        val abiSplits = splitNames.filterNotNull().filter { name ->
            listOf("arm64_v8a", "armeabi_v7a", "x86_64", "x86", "mips").any { tag ->
                name.contains(tag)
            }
        }
        if (abiSplits.isNotEmpty()) {
            val device = Build.SUPPORTED_ABIS.map { it.replace('-', '_') }.toSet()
            if (abiSplits.none { split -> device.any { abi -> split.contains(abi) } }) {
                throw ApkVerificationException("Archive lacks a supported ABI split")
            }
        }
        val installed = installed(manager, base.packageName)
        val installedSigners = installed?.let(::signed)
        val history = if (Build.VERSION.SDK_INT >= 28) {
            installed?.signingInfo?.signingCertificateHistory.orEmpty().map(::digest).toSet()
        } else installedSigners.orEmpty()
        val compatible = installedSigners?.let {
            ApkSetPolicy.compatibleInstalledSigners(base.signerDigests, it, history)
        }
        if (compatible == false) throw ApkVerificationException(
            "APK signer does not match the installed app"
        )
        // Bind the eventual PackageInstaller handoff to the same immutable
        // private bytes whose archive manifest and certificates were verified.
        for (part in staged.apks) {
            if (cancelled() || !part.file.isFile ||
                part.file.length() != part.byteCount ||
                ArtifactPrivateStager.sha256(part.file, cancelled) != part.sha256
            ) throw ApkVerificationException("Verified APK bytes changed during inspection")
        }
        val generation = SecureRandom().nextLong().ushr(1).coerceAtLeast(1L)
        val attempt = ArtifactAttempt(base.packageName, base.versionCode, generation, provenance)
        val selected = ArtifactAttemptPolicy.reduce(
            attempt,
            null,
            ArtifactAttemptPolicy.Event.DocumentSelected(attempt)
        ) ?: throw ApkVerificationException("Document selection not authorized")
        ArtifactAttemptPolicy.reduce(
            attempt,
            selected,
            ArtifactAttemptPolicy.Event.BytesStaged(
                attempt, staged.originalSha256, staged.originalSize
            )
        ) ?: throw ApkVerificationException("Invalid private staging receipt")
        val tier = if (compatible == true) ArtifactTrustTier.INSTALLED_SIGNER_CONTINUITY
            else ArtifactTrustTier.APK_SIGNER_VALID_PUBLISHER_UNANCHORED
        @Suppress("DEPRECATION")
        val installedVersion = installed?.let {
            if (Build.VERSION.SDK_INT >= 28) it.longVersionCode else it.versionCode.toLong()
        }
        return VerifiedImport(
            staged, attempt, base.signerDigests, tier, installedVersion,
            compatible, splitNames, staged.apks.sumOf { it.byteCount }
        )
    }
}
