/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import com.google.common.truth.Truth.assertThat
import java.io.File
import java.io.FileOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.junit.Test

/** JVM ZIP-structure negatives, independent of Android PackageInstaller. */
class ArtifactZipPreflightTest {
    private fun make(vararg items: Pair<String, ByteArray>): File {
        val file = File.createTempFile("aurora-hf04-", ".apks")
        ZipOutputStream(FileOutputStream(file)).use { out ->
            for ((name, bytes) in items) {
                out.putNextEntry(ZipEntry(name))
                out.write(bytes)
                out.closeEntry()
            }
        }
        return file
    }

    private fun mutate(file: File, changes: (ByteArray) -> Unit) {
        file.writeBytes(file.readBytes().also(changes))
    }

    private fun find(bytes: ByteArray, sequence: IntArray): Int {
        for (i in 0..(bytes.size - sequence.size)) {
            if (sequence.indices.all { (bytes[i + it].toInt() and 255) == sequence[it] }) return i
        }
        throw IllegalStateException("ZIP record absent")
    }

    @Test fun ordinaryArchiveIsCountedBeforeZipFileIndexing() {
        val file = make("base.apk" to ByteArray(192) { 1 }, "toc.pb" to byteArrayOf(1, 2, 3))
        try {
            val found = ArtifactZipPreflight.inspect(file)
            assertThat(found).hasSize(2)
            assertThat(found[0].name).isEqualTo("base.apk")
            assertThat(found[1].name).isEqualTo("toc.pb")
        } finally { file.delete() }
    }

    @Test fun falsifiedEntryCountFailsBeforeZipFile() {
        val file = make("base.apk" to ByteArray(128) { 1 })
        try {
            mutate(file) { bytes ->
                val eocd = find(bytes, intArrayOf(0x50, 0x4b, 5, 6))
                bytes[eocd + 8] = 0x7f
                bytes[eocd + 10] = 0x7f
            }
            assertThat(runCatching { ArtifactZipPreflight.inspect(file) }.isFailure).isTrue()
        } finally { file.delete() }
    }

    @Test fun zip64SentinelFailsClosed() {
        val file = make("base.apk" to ByteArray(128) { 1 })
        try {
            mutate(file) { bytes ->
                val eocd = find(bytes, intArrayOf(0x50, 0x4b, 5, 6))
                bytes[eocd + 10] = 0xff.toByte()
                bytes[eocd + 11] = 0xff.toByte()
            }
            assertThat(runCatching { ArtifactZipPreflight.inspect(file) }.isFailure).isTrue()
        } finally { file.delete() }
    }

    @Test fun zip64ExtraFieldWithoutSentinelFailsClosed() {
        val file = File.createTempFile("aurora-zip64-extra-", ".apks")
        try {
            ZipOutputStream(FileOutputStream(file)).use { out ->
                val entry = ZipEntry("base.apk")
                entry.extra = byteArrayOf(0xfe.toByte(), 0xca.toByte(), 0, 0)
                out.putNextEntry(entry)
                out.write(byteArrayOf(1, 2, 3))
                out.closeEntry()
            }
            mutate(file) { bytes ->
                val marker = intArrayOf(0xfe, 0xca, 0, 0)
                val first = find(bytes, marker)
                bytes[first] = 1
                bytes[first + 1] = 0
            }
            assertThat(runCatching { ArtifactZipPreflight.inspect(file) }.isFailure).isTrue()
        } finally { file.delete() }
    }

    @Test fun symlinkUnixModeFailsClosed() {
        val file = make("base.apk" to ByteArray(128) { 1 })
        try {
            mutate(file) { bytes ->
                val cen = find(bytes, intArrayOf(0x50, 0x4b, 1, 2))
                bytes[cen + 5] = 3 // made by Unix
                bytes[cen + 40] = 0
                bytes[cen + 41] = 0xa0.toByte() // 0xa000 Unix symlink type
            }
            assertThat(runCatching { ArtifactZipPreflight.inspect(file) }.isFailure).isTrue()
        } finally { file.delete() }
    }

    @Test fun localHeaderNameDisagreementFailsClosed() {
        val file = make("base.apk" to ByteArray(128) { 1 })
        try {
            mutate(file) { bytes -> bytes[30] = 'x'.code.toByte() }
            assertThat(runCatching { ArtifactZipPreflight.inspect(file) }.isFailure).isTrue()
        } finally { file.delete() }
    }

    @Test fun trailingDataIsRefused() {
        val file = make("base.apk" to ByteArray(128) { 1 })
        try {
            file.appendBytes(byteArrayOf(1, 2))
            assertThat(runCatching { ArtifactZipPreflight.inspect(file) }.isFailure).isTrue()
        } finally { file.delete() }
    }

    @Test fun duplicateOrTraversalNamesAreRefused() {
        val file = make("safe/base.apk" to byteArrayOf(2), "safe/../escape.apk" to byteArrayOf(3))
        try {
            assertThat(runCatching { ArtifactZipPreflight.inspect(file) }.isFailure).isTrue()
        } finally { file.delete() }
    }

    @Test fun metadataBombLimitIsEnforcedBeforeExtraction() {
        val file = make("base.apk" to ByteArray(128) { 1 },
            "payload.txt" to ByteArray(2 * 1024 * 1024 + 1) { 5 })
        try {
            assertThat(runCatching { ArtifactZipPreflight.inspect(file) }.isFailure).isTrue()
        } finally { file.delete() }
    }
}
