/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.artifact

import android.net.Uri
import android.os.Build
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.google.common.truth.Truth.assertThat
import java.io.File
import java.io.FileOutputStream
import java.util.UUID
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.junit.Test
import org.junit.runner.RunWith

/** API36 archive-format acceptance: no untrusted APK is installed or marked signed. */
@RunWith(AndroidJUnit4::class)
class ArtifactArchiveDescriptorDeviceTest {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private fun archive(extension: String, vararg members: Pair<String, ByteArray>): File {
        val file = File(context.cacheDir, "r3c06-${UUID.randomUUID()}.$extension")
        ZipOutputStream(FileOutputStream(file)).use { out ->
            for ((name, bytes) in members) {
                out.putNextEntry(ZipEntry(name))
                out.write(bytes)
                out.closeEntry()
            }
        }
        return file
    }
    private val apkmInfo = """{"apkm_version":5,"pname":"com.example.archive","versioncode":"42"}""".toByteArray()
    private val xapkManifest = """{"package_name":"com.example.archive","version_code":"42","split_apks":[{"file":"base.apk","id":"base"},{"file":"config.en.apk","id":"config.en"}]}""".toByteArray()

    @Test fun actualApkmOuterMetadataStagesPrivatelyWithoutPublisherTrust() {
        assertThat(Build.VERSION.SDK_INT).isEqualTo(36)
        val file=archive("apkm", "base.apk" to ByteArray(2048){1}, "info.json" to apkmInfo,
            "META-INF/MANIFEST.MF" to byteArrayOf(1,2,3),
            "META-INF/APKMIRRO.SF" to byteArrayOf(4,5,6),
            "META-INF/APKMIRRO.RSA" to byteArrayOf(7,8,9),
            "APKM_installer.url" to "[InternetShortcut]".toByteArray())
        try {
            val staged=ArtifactPrivateStager.stage(context,Uri.fromFile(file),file.name){false}
            try {
                assertThat(staged.apks).hasSize(1)
                assertThat(staged.descriptor?.packageName).isEqualTo("com.example.archive")
                assertThat(staged.descriptor?.versionCode).isEqualTo(42L)
            } finally { staged.discard() }
        } finally { file.delete() }
    }
    @Test fun apkmPartialOuterSignatureRefused() {
        val file=archive("apkm","base.apk" to ByteArray(128){1},
            "META-INF/MANIFEST.MF" to byteArrayOf(1))
        try { assertThat(runCatching {
            ArtifactPrivateStager.stage(context,Uri.fromFile(file),file.name){false}
        }.isFailure).isTrue() } finally { file.delete() }
    }
    @Test fun xapkDeclaredBaseAndSplitMustMatchSignedIds() {
        val file=archive("xapk", "base.apk" to ByteArray(512){1},
            "config.en.apk" to ByteArray(512){2}, "manifest.json" to xapkManifest)
        try {
            val staged=ArtifactPrivateStager.stage(context,Uri.fromFile(file),file.name){false}
            try {
                ArtifactArchiveDescriptorPolicy.checkAgainstSignedApks(staged.descriptor,
                    staged.format,"com.example.archive",42L,staged.archiveApkEntryNames,
                    listOf(null,"config.en"))
                assertThat(staged.apks).hasSize(2)
            } finally { staged.discard() }
        } finally { file.delete() }
    }
    @Test fun xapkIndexMismatchRefused() {
        val claim=ArtifactArchiveDescriptorParser.parse(ArtifactArchivePolicy.Format.XAPK,
            xapkManifest)!!
        assertThat(runCatching { ArtifactArchiveDescriptorPolicy.checkAgainstSignedApks(
            claim,ArtifactArchivePolicy.Format.XAPK,"com.example.archive",42L,
            listOf("base.apk","config.en.apk"),listOf(null,"config.fr")
        ) }.isFailure).isTrue()
    }
    @Test fun xapkExpansionClaimsRefusedWithoutStorageAuthorization() {
        val raw="""{"package_name":"com.example.archive","version_code":"42","expansions":[{"file":"main.42.obb"}]}""".toByteArray()
        assertThat(runCatching { ArtifactArchiveDescriptorParser.parse(
            ArtifactArchivePolicy.Format.XAPK,raw) }.isFailure).isTrue()
    }
    @Test fun hostileApkmMetadataJsonCannotCreateReceipt() {
        val bad="""{"pname":"com.example.archive","versioncode":"not-a-version"}""".toByteArray()
        assertThat(runCatching { ArtifactArchiveDescriptorParser.parse(
            ArtifactArchivePolicy.Format.APKM,bad) }.isFailure).isTrue()
    }
}
