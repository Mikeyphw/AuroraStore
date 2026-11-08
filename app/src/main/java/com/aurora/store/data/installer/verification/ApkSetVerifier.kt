/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.installer.verification

import android.content.Context
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.content.pm.Signature
import android.content.pm.SigningInfo
import android.os.Build
import com.aurora.gplayapi.model.AppFile
import com.aurora.store.data.model.DownloadStatus
import com.aurora.store.data.room.download.Download
import com.aurora.store.util.PackageUtil
import com.aurora.store.util.PathUtil
import java.io.File
import java.io.FileInputStream
import java.security.MessageDigest
import java.util.UUID

/**
 * Turns Play delivery metadata into an exact, signer-checked APK set. The package manager
 * verifies the archive certificates; Android 16 verifies v2+ signatures on stand-alone split APKs
 * using getVerifiedSigningInfo(). Neither a valid certificate nor a matching downloaded hash
 * establishes Google Play provenance. The OS remains the installation authority.
 */
object ApkSetVerifier {
    class Prepared internal constructor(
        val attempt: Long,
        val packageName: String,
        val versionCode: Long,
        private val files: Map<String, List<File>>,
        private val directory: File
    ) {
        val libraryPackages: Set<String> get() = files.keys - ""
        fun bundleFile(): File = File(directory, "verified-handoff.apks")

        fun filesFor(libraryPackage: String): List<File> =
            files[libraryPackage] ?: throw ApkVerificationException(
                "Verified APK files are missing for ${libraryPackage.ifEmpty { packageName }}"
            )
    }

    private data class Requested(
        val group: String,
        val packageName: String,
        val versionCode: Long,
        val metadata: AppFile,
        val original: File
    )

    /** Used by the worker while it is still in VERIFYING, before marking COMPLETED. */
    fun verify(context: Context, download: Download, interrupted: () -> Boolean = { false }) {
        try {
            val entries = requested(context, download)
            verifyEntries(context, entries, interrupted) { it.original }
        } catch (error: Exception) {
            throw if (error is ApkVerificationException) error else ApkVerificationException(
                "Downloaded APK is unreadable or corrupt: ${error.javaClass.simpleName}"
            )
        }
    }

    /**
     * Installer entry point. Copies only declared APKs to a private, unpredictable per-request
     * snapshot, then verifies the COPIES before any backend receives a path. A later worker
     * replacing a cache file cannot change the bytes delivered to this installation.
     */
    fun prepare(context: Context, download: Download): Prepared {
        if (download.status !in DownloadStatus.installable + DownloadStatus.INSTALLING) {
            throw ApkVerificationException("This download attempt is not installable")
        }
        val entries = requested(context, download)
        val target = File(context.cacheDir, "verified-installations/${UUID.randomUUID()}")
        if (!target.mkdirs()) {
            throw ApkVerificationException("Could not reserve a private APK installation snapshot")
        }
        try {
            val copied = entries.associateWith { entry ->
                val dir = File(target, if (entry.group.isEmpty()) "app" else "libraries/${entry.group}")
                if (!dir.mkdirs() && !dir.isDirectory) {
                    throw ApkVerificationException("Could not stage APK installation files")
                }
                val file = File(dir, entry.metadata.name)
                entry.original.inputStream().use { input ->
                    file.outputStream().use { output ->
                        input.copyTo(output)
                        output.fd.sync()
                    }
                }
                if (!file.setReadOnly()) {
                    throw ApkVerificationException("Cannot protect staged APK from replacement")
                }
                file
            }
            verifyEntries(context, entries, { false }) { copied.getValue(it) }
            return Prepared(
                download.downloadedAt,
                download.packageName,
                download.versionCode,
                copied.entries.groupBy({ it.key.group }, { it.value }),
                target
            )
        } catch (error: Exception) {
            target.deleteRecursively()
            throw if (error is ApkVerificationException) error else ApkVerificationException(
                "Unable to prepare a complete verified APK set: ${error.javaClass.simpleName}"
            )
        }
    }

    private fun requested(context: Context, download: Download): List<Requested> {
        val packagePattern = Regex("[A-Za-z_][A-Za-z0-9_]*(\\.[A-Za-z_][A-Za-z0-9_]*)+")
        if (!packagePattern.matches(download.packageName) || download.versionCode <= 0L) {
            throw ApkVerificationException("Requested APK package or version is invalid")
        }
        val groups = buildList {
            add(Triple("", download.packageName to download.versionCode, download.fileList))
            for (lib in download.sharedLibs) {
                if (!packagePattern.matches(lib.packageName) || lib.versionCode <= 0L ||
                    lib.packageName == download.packageName) {
                    throw ApkVerificationException("Invalid requested shared-library identity")
                }
                if (PackageUtil.isSharedLibraryInstalled(context, lib.packageName, lib.versionCode)) {
                    continue
                }
                add(Triple(lib.packageName, lib.packageName to lib.versionCode, lib.fileList))
            }
        }
        if (groups.map { it.first }.distinct().size != groups.size) {
            throw ApkVerificationException("Duplicate shared-library package in download metadata")
        }
        val requested = groups.flatMap { (group, pkgVersion, files) ->
            val apks = files.filter { it.type == AppFile.Type.BASE || it.type == AppFile.Type.SPLIT }
            if (apks.isEmpty() || apks.count { it.type == AppFile.Type.BASE } != 1) {
                throw ApkVerificationException("Missing base APK for ${pkgVersion.first}")
            }
            val names = apks.map { it.name }
            if (names.distinct().size != names.size) {
                throw ApkVerificationException("Duplicate APK names for ${pkgVersion.first}")
            }
            apks.map { entry ->
                if (entry.name.isEmpty() || !entry.name.endsWith(".apk") ||
                    entry.name == ".apk" || File(entry.name).name != entry.name ||
                    entry.name.contains('\\') || entry.name.contains("..") ||
                    entry.size <= 0L
                ) {
                    throw ApkVerificationException("Unsafe or incomplete APK metadata")
                }
                Requested(
                    group,
                    pkgVersion.first,
                    pkgVersion.second,
                    entry,
                    File(
                        if (group.isEmpty()) {
                            PathUtil.getAppDownloadDir(
                                context, download.packageName, download.versionCode
                            )
                        } else {
                            PathUtil.getLibDownloadDir(
                                context, download.packageName, download.versionCode, group
                            )
                        },
                        entry.name
                    )
                )
            }
        }
        // An unlisted APK must never be picked up by a backend's directory scan.
        // Fail rather than accidentally install files left by a prior attempt.
        for ((group, pkgVersion, _) in groups) {
            val folder = if (group.isEmpty()) {
                PathUtil.getAppDownloadDir(context, download.packageName, download.versionCode)
            } else {
                PathUtil.getLibDownloadDir(
                    context, download.packageName, download.versionCode, group
                )
            }
            val declared = requested.filter { it.group == group }.map { it.metadata.name }.toSet()
            if (folder.listFiles().orEmpty().any {
                it.name.endsWith(".apk") && it.name !in declared
            }) {
                throw ApkVerificationException("Undeclared cached APK exists for ${pkgVersion.first}")
            }
        }
        return requested
    }

    private fun verifyEntries(
        context: Context,
        requested: List<Requested>,
        interrupted: () -> Boolean,
        fileFor: (Requested) -> File
    ) {
        val identities = mutableMapOf<String, MutableList<ApkIdentity>>()
        val packageManager = context.packageManager
        for (entry in requested) {
            if (interrupted()) throw ApkVerificationException("APK verification was cancelled")
            val path = fileFor(entry)
            if (!path.isFile || path.length() != entry.metadata.size ||
                File(entry.original.absolutePath + ".tmp").exists()
            ) {
                throw ApkVerificationException("APK missing, incomplete or still downloading: ${entry.metadata.name}")
            }
            if (!matchesPlayDigest(path, entry.metadata, interrupted)) {
                throw ApkVerificationException("APK integrity mismatch: ${entry.metadata.name}")
            }
            // The manifest identity must be parsed for a SPLIT-only APK too; the regular
            // archive package parser may reject it because it does not contain a base APK.
            // API 36 requires an APK signing-block v2+ signature, not a v1-only
            // certificate: v1 verification does not authenticate the v2 signing block.
            val manifest = BinaryApkManifest.read(path)
            if ((entry.metadata.type == AppFile.Type.BASE) != manifest.splitName.isNullOrEmpty()) {
                throw ApkVerificationException("APK base/split declaration is inconsistent")
            }
            val info = archiveInfo(packageManager, path)
            val signers = if (Build.VERSION.SDK_INT >= 36) {
                val verified = try {
                    PackageManager.getVerifiedSigningInfo(
                        path.absolutePath, SigningInfo.VERSION_SIGNING_BLOCK_V2
                    )
                } catch (_: Exception) {
                    throw ApkVerificationException("APK signature invalid: ${entry.metadata.name}")
                }
                val signed = verified.apkContentsSigners.orEmpty()
                    .map(::signatureDigest).toSet()
                if (signed.isEmpty() || (info != null && signingDigests(info).let {
                    it.isNotEmpty() && it != signed
                })) {
                    throw ApkVerificationException("APK signature mismatch: ${entry.metadata.name}")
                }
                signed
            } else {
                // Below API 36, PackageManager must successfully read a signed archive.
                // A split it cannot independently authenticate is refused, never trusted.
                val signed = info?.let(::signingDigests).orEmpty()
                if (signed.isEmpty()) {
                    throw ApkVerificationException("APK signer cannot be authenticated on this Android version")
                }
                signed
            }
            val identity = ApkIdentity(
                entry.metadata.name,
                manifest.packageName,
                manifest.versionCode,
                entry.metadata.type == AppFile.Type.BASE,
                signers
            )
            identities.getOrPut(entry.group) { mutableListOf() }.add(identity)
        }
        val groups = requested.groupBy { it.group }
        for ((group, entries) in groups) {
            val packageName = entries.first().packageName
            ApkSetPolicy.check(packageName, entries.first().versionCode, identities[group].orEmpty())
            ensureInstalledSignerCompatibility(
                packageManager,
                packageName,
                identities.getValue(group).first().signerDigests
            )
        }
        if (interrupted()) throw ApkVerificationException("APK verification was cancelled")
    }

    private fun archiveInfo(manager: PackageManager, path: File): PackageInfo? {
        val flags = if (Build.VERSION.SDK_INT >= 28) {
            PackageManager.GET_SIGNING_CERTIFICATES
        } else {
            @Suppress("DEPRECATION")
            PackageManager.GET_SIGNATURES
        }
        return manager.getPackageArchiveInfo(path.absolutePath, flags)
    }

    private fun signingDigests(info: PackageInfo): Set<String> {
        val signatures: Array<Signature>? = if (Build.VERSION.SDK_INT >= 28) {
            info.signingInfo?.apkContentsSigners
        } else {
            @Suppress("DEPRECATION")
            info.signatures
        }
        return signatures.orEmpty().map(::signatureDigest).toSet()
    }

    private fun signatureDigest(signature: Signature): String =
        MessageDigest.getInstance("SHA-256").digest(signature.toByteArray())
            .joinToString("") { "%02x".format(it.toInt() and 0xff) }

    private fun ensureInstalledSignerCompatibility(
        manager: PackageManager,
        packageName: String,
        candidateSigners: Set<String>
    ) {
        val installed = try {
            val flag = if (Build.VERSION.SDK_INT >= 28) {
                PackageManager.GET_SIGNING_CERTIFICATES
            } else {
                @Suppress("DEPRECATION")
                PackageManager.GET_SIGNATURES
            }
            manager.getPackageInfo(packageName, flag)
        } catch (_: PackageManager.NameNotFoundException) {
            return // Fresh install: no installed signing identity to compare.
        }
        val installedSigners = signingDigests(installed)
        val history = if (Build.VERSION.SDK_INT >= 28) {
            installed.signingInfo?.signingCertificateHistory.orEmpty()
                .map(::signatureDigest).toSet()
        } else installedSigners
        if (!ApkSetPolicy.compatibleInstalledSigners(candidateSigners, installedSigners, history)) {
            throw ApkVerificationException("APK signer differs from the installed $packageName")
        }
    }

    private fun matchesPlayDigest(
        file: File,
        metadata: AppFile,
        interrupted: () -> Boolean
    ): Boolean {
        val (algorithm, expected) = when {
            metadata.sha256.matches(Regex("[0-9a-fA-F]{64}")) -> "SHA-256" to metadata.sha256
            metadata.sha256.isNotBlank() -> return false
            metadata.sha1.matches(Regex("[0-9a-fA-F]{40}")) -> "SHA-1" to metadata.sha1
            else -> return false
        }
        val digest = MessageDigest.getInstance(algorithm)
        FileInputStream(file).use { stream ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            while (true) {
                if (interrupted()) throw ApkVerificationException("APK verification was cancelled")
                val count = stream.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it.toInt() and 0xff) }
            .equals(expected, ignoreCase = true)
    }
}
