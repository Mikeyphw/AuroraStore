/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import android.net.Uri
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.io.FileOutputStream
import java.util.UUID
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/** API36 native SAF-stream staging fixtures; no Play or install receipt is fabricated. */
@RunWith(AndroidJUnit4::class)
class ArtifactPrivateStagerDeviceTest {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext

    private fun archive(vararg entries: Pair<String, ByteArray>): File {
        val file = File(context.cacheDir, "archive-${UUID.randomUUID()}.apks")
        ZipOutputStream(FileOutputStream(file)).use { output ->
            for ((name, bytes) in entries) {
                output.putNextEntry(ZipEntry(name))
                output.write(bytes)
                output.closeEntry()
            }
        }
        return file
    }

    @Test
    fun safeArchivePrivatelyExtractsExactApkBytes() {
        val input = archive("base.apk" to ByteArray(2048) { 1 })
        try {
            val stage = ArtifactPrivateStager.stage(context, Uri.fromFile(input), input.name) { false }
            try {
                assertThat(stage.apks).hasSize(1)
                assertThat(stage.apks.single().byteCount).isEqualTo(2048)
                assertThat(stage.apks.single().file.canonicalPath)
                    .startsWith(context.cacheDir.canonicalPath)
                assertThat(stage.apks.single().file.name).isEqualTo("part-000.apk")
            } finally { stage.discard() }
        } finally { input.delete() }

        // Standalone .apk uses the same private file/byte-boundary model.
        val standalone = File(context.cacheDir, "standalone-${UUID.randomUUID()}.apk")
        standalone.writeBytes(ByteArray(2048) { 2 })
        try {
            val stage = ArtifactPrivateStager.stage(context,
                Uri.fromFile(standalone), standalone.name) { false }
            try {
                assertThat(stage.apks).hasSize(1)
                assertThat(stage.apks.single().byteCount).isEqualTo(2048)
                assertThat(stage.format).isEqualTo(ArtifactArchivePolicy.Format.APK)
            } finally { stage.discard() }
        } finally { standalone.delete() }
    }

    @Test
    fun zipTraversalNeverEscapesPrivateStaging() {
        val input = archive("../../outside.apk" to byteArrayOf(1, 2))
        try {
            assertThat(runCatching {
                ArtifactPrivateStager.stage(context, Uri.fromFile(input), input.name) { false }
            }.isFailure).isTrue()
        } finally { input.delete() }
    }

    @Test
    fun duplicateNamesAreRefused() {
        val input = archive(
            "base.apk" to byteArrayOf(1, 2, 3),
            "BASE.apk" to byteArrayOf(4, 5, 6)
        )
        try {
            assertThat(runCatching {
                ArtifactPrivateStager.stage(context, Uri.fromFile(input), input.name) { false }
            }.isFailure).isTrue()
        } finally { input.delete() }
    }

    @Test
    fun archiveWithExpansionAssetsFailsClosed() {
        val input = archive("base.apk" to ByteArray(256) { 1 }, "Android/obb/test/main.obb" to byteArrayOf(7))
        try {
            assertThat(runCatching {
                ArtifactPrivateStager.stage(context, Uri.fromFile(input), input.name) { false }
            }.isFailure).isTrue()
        } finally { input.delete() }
    }

    @Test
    fun compressedBombIsRejected() {
        val input = archive("base.apk" to ByteArray(3_000_000))
        try {
            assertThat(runCatching {
                ArtifactPrivateStager.stage(context, Uri.fromFile(input), input.name) { false }
            }.isFailure).isTrue()
        } finally { input.delete() }
    }

    @Test
    fun manyArchiveEntriesRefusedBeforeStagingAnyApks() {
        val input = archive(*Array(129) { i ->
            "assets/part-$i.txt" to byteArrayOf(1)
        })
        try {
            assertThat(runCatching {
                ArtifactPrivateStager.stage(context, Uri.fromFile(input), input.name) { false }
            }.isFailure).isTrue()
        } finally { input.delete() }
    }

    @Test
    fun cancelledImportNeverLeavesVerifiedReceipt() {
        val input = archive("base.apk" to ByteArray(128) { 1 })
        try {
            assertThat(runCatching {
                ArtifactPrivateStager.stage(context, Uri.fromFile(input), input.name) { true }
            }.isFailure).isTrue()
        } finally { input.delete() }
    }

    private fun storedArchive(apkName: String, contents: ByteArray): File {
        val file = File(context.cacheDir, "archive-stored-${UUID.randomUUID()}.apks")
        val crc = java.util.zip.CRC32().apply { update(contents) }
        ZipOutputStream(FileOutputStream(file)).use { output ->
            val entry = ZipEntry(apkName)
            entry.method = ZipEntry.STORED
            entry.size = contents.size.toLong()
            entry.compressedSize = contents.size.toLong()
            entry.crc = crc.value
            output.putNextEntry(entry)
            output.write(contents)
            output.closeEntry()
        }
        return file
    }

    private fun corruptStoredPayload(input: File, marker: ByteArray) {
        val bytes = input.readBytes()
        val location = (0..bytes.size - marker.size).first { start ->
            marker.indices.all { i -> bytes[start + i] == marker[i] }
        }
        bytes[location] = (bytes[location].toInt() xor 1).toByte()
        input.writeBytes(bytes)
    }

    @Test
    fun tamperedStoredApkFailsCrcVerification() {
        val payload = "unique-apk-test-contents-HF04".toByteArray()
        val input = storedArchive("base.apk", payload)
        try {
            corruptStoredPayload(input, payload)
            assertThat(runCatching {
                ArtifactPrivateStager.stage(context, Uri.fromFile(input), input.name) { false }
            }.isFailure).isTrue()
        } finally { input.delete() }
    }

    @Test
    fun tamperedMetadataFailsCrcVerificationEvenThoughNotInstalled() {
        val payload = "unique-metadata-contents-HF04".toByteArray()
        val input = File(context.cacheDir, "metadata-${UUID.randomUUID()}.apks")
        ZipOutputStream(FileOutputStream(input)).use { out ->
            out.putNextEntry(ZipEntry("base.apk"))
            out.write(ByteArray(64) { 1 })
            out.closeEntry()
            val crc = java.util.zip.CRC32().apply { update(payload) }
            val meta = ZipEntry("metadata/manifest.json")
            meta.method = ZipEntry.STORED
            meta.size = payload.size.toLong()
            meta.compressedSize = payload.size.toLong()
            meta.crc = crc.value
            out.putNextEntry(meta)
            out.write(payload)
            out.closeEntry()
        }
        try {
            corruptStoredPayload(input, payload)
            assertThat(runCatching {
                ArtifactPrivateStager.stage(context, Uri.fromFile(input), input.name) { false }
            }.isFailure).isTrue()
        } finally { input.delete() }
    }

    @Test
    fun forgedCentralDirectoryCountIsRejected() {
        val input = archive("base.apk" to ByteArray(128) { 1 })
        try {
            val bytes = input.readBytes()
            val eocd = (0..bytes.size - 4).last { offset ->
                bytes[offset] == 0x50.toByte() && bytes[offset + 1] == 0x4b.toByte() &&
                    bytes[offset + 2] == 5.toByte() && bytes[offset + 3] == 6.toByte()
            }
            bytes[eocd + 8] = 0x7f
            bytes[eocd + 10] = 0x7f
            input.writeBytes(bytes)
            assertThat(runCatching {
                ArtifactPrivateStager.stage(context, Uri.fromFile(input), input.name) { false }
            }.isFailure).isTrue()
        } finally { input.delete() }
    }

    @Test
    fun symbolicLinkEntryModeIsRejected() {
        val input = archive("base.apk" to ByteArray(128) { 1 })
        try {
            val bytes = input.readBytes()
            val cen = (0..bytes.size - 4).first { offset ->
                bytes[offset] == 0x50.toByte() && bytes[offset + 1] == 0x4b.toByte() &&
                    bytes[offset + 2] == 1.toByte() && bytes[offset + 3] == 2.toByte()
            }
            bytes[cen + 5] = 3
            bytes[cen + 41] = 0xa0.toByte()
            input.writeBytes(bytes)
            assertThat(runCatching {
                ArtifactPrivateStager.stage(context, Uri.fromFile(input), input.name) { false }
            }.isFailure).isTrue()
        } finally { input.delete() }
    }

    @Test
    fun tocPbIsVerifiedAsOpaqueMetadataOnly() {
        val input = archive("base.apk" to ByteArray(128) { 1 }, "toc.pb" to byteArrayOf(7, 8, 9))
        try {
            // Same strict extraction for synthetically ZIP-backed APKS/APKM/XAPK,
            // without asserting real-world dialect completeness or device targeting.
            // toc.pb is a bundletool/APKS-specific index. Re-labeling it as
            // APKM or XAPK must not silently grant a compatible container format.
            val candidate = File(context.cacheDir, "synthetic-${UUID.randomUUID()}.apks")
            input.copyTo(candidate)
            try {
                val stage = ArtifactPrivateStager.stage(context,
                    Uri.fromFile(candidate), candidate.name) { false }
                try {
                    assertThat(stage.apks).hasSize(1)
                    assertThat(stage.apks.single().byteCount).isEqualTo(128)
                } finally { stage.discard() }
            } finally { candidate.delete() }
            for (suffix in listOf("apkm", "xapk")) {
                val wrong = File(context.cacheDir, "relabel-${UUID.randomUUID()}.$suffix")
                input.copyTo(wrong)
                try {
                    assertThat(runCatching {
                        ArtifactPrivateStager.stage(context,
                            Uri.fromFile(wrong), wrong.name) { false }
                    }.isFailure).isTrue()
                } finally { wrong.delete() }
            }
        } finally { input.delete() }
    }

    @Test
    fun missingCentralDirectoryTailIsRejected() {
        val input = archive("base.apk" to ByteArray(128) { 1 })
        try {
            input.writeBytes(input.readBytes().dropLast(4).toByteArray())
            assertThat(runCatching {
                ArtifactPrivateStager.stage(context, Uri.fromFile(input), input.name) { false }
            }.isFailure).isTrue()
        } finally { input.delete() }
    }

    /** C04-02: a real content URI from the app-owned FileProvider, not file://. */
    @Test
    fun contentUriProviderStagesInPrivateCache() {
        val input = File(context.cacheDir, "saf-${UUID.randomUUID()}.apk")
        input.writeBytes(ByteArray(4096) { (it % 251).toByte() })
        try {
            val uri = androidx.core.content.FileProvider.getUriForFile(
                context, context.packageName + ".fileProvider", input
            )
            assertThat(uri.scheme).isEqualTo("content")
            val stage = ArtifactPrivateStager.stage(context, uri, input.name) { false }
            try {
                assertThat(stage.apks.single().file.canonicalPath)
                    .startsWith(context.cacheDir.canonicalPath)
                assertThat(stage.originalSize).isEqualTo(4096L)
                assertThat(stage.apks.single().sha256).isEqualTo(stage.originalSha256)
            } finally { stage.discard() }
        } finally { input.delete() }
    }

    private fun importChildNames(): Set<String> =
        File(context.cacheDir, "artifact-imports").listFiles()?.map { it.name }?.toSet()
            ?: emptySet()

    @Test
    fun refusedProviderUriLeavesNoPrivateStaging() {
        val before = importChildNames()
        val uri = Uri.parse("content://com.aurora.store.debug.nonexistent/document/123")
        assertThat(runCatching {
            ArtifactPrivateStager.stage(context, uri, "release.apk") { false }
        }.isFailure).isTrue()
        assertThat(importChildNames()).isEqualTo(before)
    }

    @Test
    fun cancelledLargeCopyRemovesPrivatePartialFiles() {
        val input = File(context.cacheDir, "cancel-${UUID.randomUUID()}.apk")
        input.writeBytes(ByteArray(128 * 1024) { (it % 251).toByte() })
        val before = importChildNames()
        var calls = 0
        try {
            assertThat(runCatching {
                ArtifactPrivateStager.stage(context, Uri.fromFile(input), input.name) {
                    ++calls
                    calls >= 5
                }
            }.isFailure).isTrue()
            assertThat(importChildNames()).isEqualTo(before)
        } finally { input.delete() }
    }

    @Test
    fun alreadyCancelledLeaseFailsBeforeCopyAndCleansUp() {
        val input = File(context.cacheDir, "cancellease-${UUID.randomUUID()}.apk")
        input.writeBytes(byteArrayOf(1, 2, 3, 4))
        val before = importChildNames()
        val lease = ArtifactCopyCancellation()
        lease.cancel()
        try {
            assertThat(runCatching {
                ArtifactPrivateStager.stage(context, Uri.fromFile(input), input.name, lease) {
                    lease.isCancelled()
                }
            }.isFailure).isTrue()
            assertThat(importChildNames()).isEqualTo(before)
        } finally { input.delete() }
    }
}
