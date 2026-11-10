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
}
