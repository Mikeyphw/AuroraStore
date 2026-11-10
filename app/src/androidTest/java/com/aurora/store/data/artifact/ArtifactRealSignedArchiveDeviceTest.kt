/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.artifact

import android.net.Uri
import android.os.Build
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

/** Signed real APK bytes on API36, wrapped in synthetic APKM/XAPK containers.
 * Not evidence of a real-world APKMirror publisher identity or vendor dialect support.
 */
@RunWith(AndroidJUnit4::class)
class ArtifactRealSignedArchiveDeviceTest {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val original get() = File(context.applicationInfo.sourceDir)
    private val packageVersion: Long get() = context.packageManager
        .getPackageInfo(context.packageName, 0).longVersionCode
    private fun source(format: String, pkg: String = context.packageName,
                       version: Long = packageVersion, tamper: Boolean = false): File {
        val zip = File(context.cacheDir, "r3c06-signed-${UUID.randomUUID()}.$format")
        ZipOutputStream(FileOutputStream(zip)).use { out ->
            fun add(name: String, bytes: ByteArray) {
                out.putNextEntry(ZipEntry(name))
                out.write(bytes)
                out.closeEntry()
            }
            out.putNextEntry(ZipEntry("base.apk"))
            original.inputStream().use { source ->
                val buffer = ByteArray(64 * 1024)
                var copied = 0L
                val change = original.length() / 2
                while (true) {
                    val n = source.read(buffer)
                    if (n < 0) break
                    if (n == 0) throw IllegalStateException("Signed fixture source stalled")
                    if (tamper && copied <= change && change < copied + n) {
                        val at = (change - copied).toInt()
                        buffer[at] = (buffer[at].toInt() xor 1).toByte()
                    }
                    out.write(buffer, 0, n)
                    copied += n
                }
            }
            out.closeEntry()
            if (format == "apkm") {
                add("info.json", "{\"pname\":\"$pkg\",\"versioncode\":$version}".toByteArray())
            } else {
                add("manifest.json", ("{\"package_name\":\"$pkg\",\"version_code\":\"$version\"," +
                    "\"split_apks\":[{\"file\":\"base.apk\",\"id\":\"base\"}]}").toByteArray())
            }
        }
        return zip
    }
    private fun verifyFile(file: File): ArtifactApkVerifier.VerifiedImport {
        val stage = ArtifactPrivateStager.stage(context, Uri.fromFile(file), file.name) { false }
        return try {
            ArtifactApkVerifier.verify(context, stage,
                ArtifactProvenance(ArtifactSource.LOCAL_DOCUMENT)) { false }
        } catch (e: Exception) { stage.discard(); throw e }
    }
    @Test fun realSignedApkmVerifiesAndRevalidates() {
        assertThat(Build.VERSION.SDK_INT).isEqualTo(36)
        val zip = source("apkm")
        try {
            val receipt = verifyFile(zip)
            try {
                assertThat(receipt.attempt.packageName).isEqualTo(context.packageName)
                assertThat(receipt.signerSha256).isNotEmpty()
                assertThat(receipt.signerMatchesInstalled).isTrue()
                assertThat(receipt.isPlayEvidence).isFalse()
                ArtifactApkVerifier.revalidateForInstall(context, receipt) { false }
            } finally { receipt.discard() }
        } finally { zip.delete() }
    }
    @Test fun realSignedXapkVerifiesAndRevalidates() {
        assertThat(Build.VERSION.SDK_INT).isEqualTo(36)
        val zip = source("xapk")
        try {
            val receipt = verifyFile(zip)
            try {
                assertThat(receipt.staged.format).isEqualTo(ArtifactArchivePolicy.Format.XAPK)
                assertThat(receipt.staged.archiveApkEntryNames).containsExactly("base.apk")
                ArtifactApkVerifier.revalidateForInstall(context, receipt) { false }
            } finally { receipt.discard() }
        } finally { zip.delete() }
    }
    @Test fun signedApkmCannotBorrowDifferentPackageDescriptor() {
        val zip = source("apkm", pkg="org.different.package")
        try { assertThat(runCatching { verifyFile(zip).discard() }.isFailure).isTrue() }
        finally { zip.delete() }
    }
    @Test fun signedXapkCannotBorrowDifferentVersionDescriptor() {
        val zip = source("xapk", version=packageVersion + 1)
        try { assertThat(runCatching { verifyFile(zip).discard() }.isFailure).isTrue() }
        finally { zip.delete() }
    }
    @Test fun modifiedSignedApkmCannotPassSignatureVerification() {
        val zip = source("apkm", tamper=true)
        try { assertThat(runCatching { verifyFile(zip).discard() }.isFailure).isTrue() }
        finally { zip.delete() }
    }
    @Test fun realSignedManifestDependencyReaderHasNoUnknownFeatureClaim() {
        assertThat(Build.VERSION.SDK_INT).isEqualTo(36)
        // This repository's ordinary debug base APK has no uses-split dependency.
        assertThat(ArtifactSignedManifestDependencies.read(original)).isNull()
    }
}
