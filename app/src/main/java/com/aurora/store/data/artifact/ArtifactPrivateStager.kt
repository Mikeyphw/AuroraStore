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
import java.util.zip.CRC32
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
        if (cancelled() || Thread.currentThread().isInterrupted) {
            throw ApkVerificationException("Import was cancelled")
        }
    }

    private fun hex(bytes: ByteArray): String = bytes.joinToString("") {
        "%02x".format(Locale.ROOT, it.toInt() and 0xff)
    }

    private fun copyBounded(
        from: InputStream,
        to: File,
        limit: Long,
        cancelled: () -> Boolean,
        expectedCrc: Long? = null
    ): CopiedApk {
        val digest = MessageDigest.getInstance("SHA-256")
        val crc = CRC32()
        var size = 0L
        FileOutputStream(to).use { output ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                checkActive(cancelled)
                val n = from.read(buffer)
                if (n < 0) break
                if (n == 0) throw ApkVerificationException("Import stream stalled")
                checkActive(cancelled)
                size += n
                if (size > limit) throw ApkVerificationException("Import size limit exceeded")
                digest.update(buffer, 0, n)
                crc.update(buffer, 0, n)
                output.write(buffer, 0, n)
            }
            output.fd.sync()
        }
        checkActive(cancelled)
        if (expectedCrc != null && crc.value != expectedCrc) {
            throw ApkVerificationException("Archive entry checksum mismatch")
        }
        if (size <= 0L || !to.setReadOnly()) {
            throw ApkVerificationException("Imported APK is empty or could not be protected")
        }
        return CopiedApk(to, hex(digest.digest()), size)
    }

    /** Check every metadata stream too: ignored bytes must not hide corruption or bombs. */
    private fun verifyMetadata(
        input: InputStream, expectedSize: Long, expectedCrc: Long,
        cancelled: () -> Boolean
    ) {
        val crc = CRC32()
        val buffer = ByteArray(64 * 1024)
        var size = 0L
        while (true) {
            checkActive(cancelled)
            val n = input.read(buffer)
            if (n < 0) break
            if (n == 0) throw ApkVerificationException("Metadata stream stalled")
            size += n
            if (size > 2L * 1024 * 1024 || size > expectedSize) {
                throw ApkVerificationException("Archive metadata exceeds declared limit")
            }
            crc.update(buffer, 0, n)
        }
        checkActive(cancelled)
        if (size != expectedSize || crc.value != expectedCrc) {
            throw ApkVerificationException("Archive metadata checksum or size mismatch")
        }
    }

    fun stage(
        context: Context,
        uri: Uri,
        displayName: String,
        sourceCancellation: ArtifactCopyCancellation? = null,
        cancelled: () -> Boolean
    ): Staged {
        val format = ArtifactArchivePolicy.format(displayName)
            ?: throw ApkVerificationException("Choose a .apk, .apks, .apkm or .xapk file")
        val directory = File(context.cacheDir, "artifact-imports/${UUID.randomUUID()}")
        if (!directory.mkdirs()) throw ApkVerificationException("Cannot reserve private staging")
        try {
            checkActive(cancelled)
            val source = context.contentResolver.openInputStream(uri)
                ?: throw ApkVerificationException("Document permission expired or unreadable")
            val copied = source.use { stream ->
                try {
                    sourceCancellation?.attach(stream)
                    checkActive(cancelled)
                    copyBounded(stream, File(directory, "selected-source.bin"),
                        ArtifactArchivePolicy.MAX_SOURCE_BYTES, cancelled)
                } finally {
                    sourceCancellation?.detach(stream)
                }
            }
            // Never accept a filename as evidence of actual APK or archive bytes.
            if (format == ArtifactArchivePolicy.Format.APK) {
                if (copied.byteCount > ArtifactArchivePolicy.MAX_APK_BYTES) {
                    throw ApkVerificationException("APK exceeds per-file size limit")
                }
                val dest = File(directory, "part-000.apk")
                if (!copied.file.renameTo(dest)) {
                    throw ApkVerificationException("Private APK staging failed")
                }
                checkActive(cancelled)
                return Staged(directory, format, listOf(copied.copy(file = dest)),
                    copied.sha256, copied.byteCount)
            }
            // ZipFile internally indexes the WHOLE central directory before entries()
            // is available. Preflight bounds count, layout, modes and symlink attributes.
            val inspected = ArtifactZipPreflight.inspect(copied.file)
            val entries = mutableListOf<CopiedApk>()
            val usedNames = mutableSetOf<String>()
            var total = 0L
            ZipFile(copied.file).use { archive ->
                // Bound enumeration itself; toList() could allocate for an arbitrary
                // number of central-directory entries before the limit was enforced.
                val items = archive.entries()
                var entryCount = 0
                while (items.hasMoreElements()) {
                    checkActive(cancelled)
                    if (++entryCount > ArtifactArchivePolicy.MAX_ITEMS) {
                        throw ApkVerificationException("Archive has too many entries")
                    }
                    val entry = items.nextElement()
                    checkActive(cancelled)
                    val expected = inspected.getOrNull(entryCount - 1)
                        ?: throw ApkVerificationException("ZIP entry count changed after preflight")
                    if (entry.name != expected.name || entry.isDirectory != expected.directory ||
                        entry.size != expected.size || entry.compressedSize != expected.compressed ||
                        entry.crc != expected.crc || entry.method != expected.method
                    ) throw ApkVerificationException("ZIP changed after central-directory preflight")
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
                    total += entry.size
                    if (total > ArtifactArchivePolicy.MAX_TOTAL_APK_BYTES) {
                        throw ApkVerificationException("Archive exceeds total expanded size limit")
                    }
                    if (!isApk) {
                        // No metadata is trusted, but its CRC and expanded length must still match.
                        archive.getInputStream(entry).use { stream ->
                            verifyMetadata(stream, entry.size, entry.crc, cancelled)
                        }
                        continue
                    }
                    if (entries.size >= ArtifactArchivePolicy.MAX_APKS) {
                        throw ApkVerificationException("Too many split APKs")
                    }
                    val path = File(directory, "part-${entries.size.toString().padStart(3, '0')}.apk")
                    val apk = archive.getInputStream(entry).use { stream ->
                        copyBounded(stream, path, ArtifactArchivePolicy.MAX_APK_BYTES,
                            cancelled, entry.crc)
                    }
                    if (apk.byteCount != entry.size) {
                        throw ApkVerificationException("Archive entry uncompressed length differs")
                    }
                    entries.add(apk)
                }
                if (entryCount != inspected.size) {
                    throw ApkVerificationException("ZIP entry count differs after preflight")
                }
            }
            if (entries.isEmpty()) throw ApkVerificationException("No installable APKs in archive")
            checkActive(cancelled)
            if (!copied.file.delete()) {
                throw ApkVerificationException("Cannot discard original ZIP after staging")
            }
            checkActive(cancelled)
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
                if (n == 0) throw ApkVerificationException("APK digest stream stalled")
                checkActive(cancelled)
                digest.update(data, 0, n)
            }
        }
        checkActive(cancelled)
        return hex(digest.digest())
    }
}
