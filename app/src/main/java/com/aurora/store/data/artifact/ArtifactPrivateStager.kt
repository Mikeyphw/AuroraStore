/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import android.content.Context
import android.net.Uri
import com.aurora.store.data.installer.verification.ApkVerificationException
import java.io.File
import java.io.FileOutputStream
import java.io.InputStream
import java.security.MessageDigest
import java.util.Locale
import java.util.UUID
import java.util.zip.ZipFile

/**
 * One-time SAF stream copy into app-private cache. No global storage permission,
 * no URI persistence, no untrusted archive path extraction and no Play metadata.
 */
internal object ArtifactPrivateStager {
    data class CopiedApk(val file: File, val sha256: String, val byteCount: Long)

    class Staged internal constructor(
        val directory: File,
        val format: ArtifactArchivePolicy.Format,
        val apks: List<CopiedApk>,
        val originalSha256: String,
        val originalSize: Long
    ) {
        fun discard() {
            directory.deleteRecursively()
        }
    }

    private fun checkActive(cancelled: () -> Boolean) {
        if (cancelled()) throw ApkVerificationException("Import was cancelled")
    }

    private fun hex(bytes: ByteArray): String = bytes.joinToString("") {
        "%02x".format(Locale.ROOT, it.toInt() and 0xff)
    }

    private fun copyBounded(
        from: InputStream,
        to: File,
        limit: Long,
        cancelled: () -> Boolean
    ): CopiedApk {
        val digest = MessageDigest.getInstance("SHA-256")
        var size = 0L
        FileOutputStream(to).use { output ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                checkActive(cancelled)
                val n = from.read(buffer)
                if (n < 0) break
                size += n
                if (size > limit) throw ApkVerificationException("Import size limit exceeded")
                digest.update(buffer, 0, n)
                output.write(buffer, 0, n)
            }
            output.fd.sync()
        }
        if (size <= 0L || !to.setReadOnly()) {
            throw ApkVerificationException("Imported APK is empty or could not be protected")
        }
        return CopiedApk(to, hex(digest.digest()), size)
    }

    fun stage(
        context: Context,
        uri: Uri,
        displayName: String,
        cancelled: () -> Boolean
    ): Staged {
        val format = ArtifactArchivePolicy.format(displayName)
            ?: throw ApkVerificationException("Choose a .apk, .apks, .apkm or .xapk file")
        val directory = File(context.cacheDir, "artifact-imports/${UUID.randomUUID()}")
        if (!directory.mkdirs()) throw ApkVerificationException("Cannot reserve private staging")
        try {
            checkActive(cancelled)
            val copied = context.contentResolver.openInputStream(uri)?.use { source ->
                copyBounded(
                    source,
                    File(directory, "selected-source.bin"),
                    ArtifactArchivePolicy.MAX_SOURCE_BYTES,
                    cancelled
                )
            } ?: throw ApkVerificationException("Document permission expired or unreadable")
            // Never accept a filename as evidence of actual APK or archive bytes.
            if (format == ArtifactArchivePolicy.Format.APK) {
                val dest = File(directory, "part-000.apk")
                if (!copied.file.renameTo(dest)) {
                    throw ApkVerificationException("Private APK staging failed")
                }
                return Staged(directory, format, listOf(copied.copy(file = dest)),
                    copied.sha256, copied.byteCount)
            }
            val entries = mutableListOf<CopiedApk>()
            val usedNames = mutableSetOf<String>()
            var total = 0L
            ZipFile(copied.file).use { archive ->
                val items = archive.entries().toList()
                if (items.isEmpty() || items.size > ArtifactArchivePolicy.MAX_ITEMS) {
                    throw ApkVerificationException("Archive has too many entries")
                }
                for (entry in items) {
                    checkActive(cancelled)
                    val safeName = entry.name.removeSuffix("/")
                    val kind = ArtifactArchivePolicy.classify(safeName, entry.isDirectory)
                        ?: throw ApkVerificationException("Unsafe or unsupported archive entry")
                    if (!usedNames.add(safeName.lowercase(Locale.ROOT))) {
                        throw ApkVerificationException("Duplicate archive paths are not allowed")
                    }
                    if (kind == ArtifactArchivePolicy.Entry.DIRECTORY) continue
                    val isApk = kind == ArtifactArchivePolicy.Entry.APK
                    if (!ArtifactArchivePolicy.safeSize(entry.size, entry.compressedSize, isApk)) {
                        throw ApkVerificationException("Archive entry is too large or compressed")
                    }
                    if (!isApk) continue // metadata is never interpreted as provenance
                    if (entries.size >= ArtifactArchivePolicy.MAX_APKS) {
                        throw ApkVerificationException("Too many split APKs")
                    }
                    val path = File(directory, "part-${entries.size.toString().padStart(3, '0')}.apk")
                    val apk = archive.getInputStream(entry).use { stream ->
                        copyBounded(stream, path, ArtifactArchivePolicy.MAX_APK_BYTES, cancelled)
                    }
                    if (apk.byteCount != entry.size) {
                        throw ApkVerificationException("Archive entry uncompressed length differs")
                    }
                    total += apk.byteCount
                    if (total > ArtifactArchivePolicy.MAX_TOTAL_APK_BYTES) {
                        throw ApkVerificationException("Archive exceeds total APK size limit")
                    }
                    entries.add(apk)
                }
            }
            if (entries.isEmpty()) throw ApkVerificationException("No installable APKs in archive")
            copied.file.delete()
            return Staged(directory, format, entries, copied.sha256, copied.byteCount)
        } catch (error: Exception) {
            directory.deleteRecursively()
            throw if (error is ApkVerificationException) error else
                ApkVerificationException("Document archive invalid or unreadable")
        }
    }

    fun sha256(file: File, cancelled: () -> Boolean = { false }): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { source ->
            val data = ByteArray(64 * 1024)
            while (true) {
                checkActive(cancelled)
                val n = source.read(data)
                if (n < 0) break
                digest.update(data, 0, n)
            }
        }
        return hex(digest.digest())
    }
}
