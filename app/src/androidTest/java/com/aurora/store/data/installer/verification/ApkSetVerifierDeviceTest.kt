/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.installer.verification

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.aurora.gplayapi.model.AppFile
import com.aurora.store.data.model.DownloadStatus
import com.aurora.store.data.room.download.Download
import com.aurora.store.util.PathUtil
import com.google.common.truth.Truth.assertThat
import java.io.File
import java.security.MessageDigest
import org.junit.Test
import org.junit.runner.RunWith

/** API 36 synthetic signed APK acceptance: no Play account/network or production signing key. */
@RunWith(AndroidJUnit4::class)
class ApkSetVerifierDeviceTest {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val packageName = "com.aurora.r3b.fixture"
    private val fixtureDir get() = File(context.cacheDir, "r3b-fixtures")

    private fun digest(file: File) = MessageDigest.getInstance("SHA-256")
        .digest(file.readBytes()).joinToString("") { "%02x".format(it.toInt() and 0xff) }

    private fun download(
        source: String = "base.apk",
        requestedPackage: String = packageName,
        version: Long = 73L,
        status: DownloadStatus = DownloadStatus.COMPLETED,
        checksum: String? = null,
        includeSplit: Boolean = false
    ): Download {
        val fixture = File(fixtureDir, source)
        val base = AppFile(
            url = "https://localhost.invalid/offline",
            name = "base.apk",
            size = fixture.length(),
            sha256 = checksum ?: digest(fixture)
        )
        val split = File(fixtureDir, "matching-split.apk")
        val splitFile = AppFile(
            url = "https://localhost.invalid/offline",
            name = "config.en.apk",
            size = split.length(),
            sha256 = digest(split),
            type = AppFile.Type.SPLIT
        )
        val files = if (includeSplit) listOf(base, splitFile) else listOf(base)
        return Download(
            packageName = requestedPackage,
            versionCode = version,
            offerType = 0,
            isInstalled = false,
            displayName = "R3B offline fixture",
            iconURL = "",
            size = files.sumOf { it.size },
            id = 0,
            status = status,
            progress = 100,
            speed = 0,
            timeRemaining = 0,
            totalFiles = files.size,
            downloadedFiles = files.size,
            fileList = files,
            sharedLibs = emptyList(),
            downloadedAt = 8675309L
        ).also { download ->
            val target = PathUtil.getAppDownloadDir(context, requestedPackage, version)
            target.deleteRecursively()
            assertThat(target.mkdirs()).isTrue()
            fixture.copyTo(File(target, "base.apk"), overwrite = true)
            if (includeSplit) split.copyTo(File(target, "config.en.apk"), overwrite = true)
        }
    }

    private fun rejects(block: () -> Unit) {
        try {
            block()
            throw AssertionError("Expected the APK set verifier to reject this artifact")
        } catch (_: ApkVerificationException) {
            // A fail-closed verifier rejection is the expected outcome.
        }
    }

    @Test
    fun correctOfflineSignedApkAndVersionAreAccepted() {
        val item = download()
        ApkSetVerifier.verify(context, item)
        val staged = ApkSetVerifier.prepare(context, item)
        assertThat(staged.filesFor("")).hasSize(1)
        assertThat(staged.filesFor("").single().isFile).isTrue()
    }

    @Test
    fun wrongRequestedPackageIsRejected() {
        rejects { ApkSetVerifier.verify(context, download(requestedPackage = "com.aurora.r3b.other")) }
    }

    @Test
    fun wrongRequestedVersionIsRejected() {
        rejects { ApkSetVerifier.verify(context, download(version = 74L)) }
    }

    @Test
    fun validHistoricalVersionIsAcceptedAsExactArtifact() {
        ApkSetVerifier.verify(context, download(source = "older.apk", version = 72L))
    }

    @Test
    fun truncatedApkIsRejectedEvenWhenMetadataMatchesItsBytes() {
        val item = download()
        val base = PathUtil.getLocalFile(context, item.fileList.single(), item)
        base.writeBytes(base.readBytes().copyOf(48))
        rejects { ApkSetVerifier.verify(context, item) }
    }

    @Test
    fun invalidPlayHashIsRejected() {
        rejects { ApkSetVerifier.verify(context, download(checksum = "0".repeat(64))) }
    }

    @Test
    fun missingSplitIsRejected() {
        val item = download(includeSplit = true)
        File(PathUtil.getAppDownloadDir(context, packageName, 73), "config.en.apk").delete()
        rejects { ApkSetVerifier.verify(context, item) }
    }

    @Test
    fun mismatchedSplitSignerIsRejected() {
        val item = download(includeSplit = true)
        val target = File(PathUtil.getAppDownloadDir(context, packageName, 73), "config.en.apk")
        File(fixtureDir, "other-signer-split.apk").copyTo(target, overwrite = true)
        // Update the delivery checksum too: this must fail due to the SPLIT CERTIFICATE,
        // not only because a prior file hash no longer matches.
        val updated = item.copy(fileList = item.fileList.map { file ->
            if (file.type == AppFile.Type.SPLIT) {
                file.copy(sha256 = digest(target), size = target.length())
            } else {
                file
            }
        })
        rejects { ApkSetVerifier.verify(context, updated) }
    }

    @Test
    fun installedPackageWithDifferentSignerIsRejected() {
        // CI installs the main-signer base fixture before running this suite.
        val installed = context.packageManager.getPackageInfo(packageName, 0)
        assertThat(installed.packageName).isEqualTo(packageName)
        rejects {
            ApkSetVerifier.verify(context, download(source = "other-signer.apk"))
        }
    }

    @Test
    fun alteredSigningBlockIsRejectedEvenWithUpdatedDownloadHash() {
        val item = download()
        val original = PathUtil.getLocalFile(context, item.fileList.single(), item)
        val raw = original.readBytes()
        val magic = "APK Sig Block 42".toByteArray()
        val magicAt = raw.indices.firstOrNull { i ->
            i + magic.size <= raw.size && magic.indices.all { j -> raw[i + j] == magic[j] }
        } ?: throw AssertionError("Hosted fixture lacks an APK v2 signing block")
        assertThat(magicAt).isGreaterThan(64)
        raw[magicAt - 40] = (raw[magicAt - 40].toInt() xor 0x01).toByte()
        original.writeBytes(raw)
        val updated = item.copy(
            fileList = listOf(item.fileList.single().copy(sha256 = digest(original)))
        )
        try {
            ApkSetVerifier.verify(context, updated)
            throw AssertionError("Corrupted APK signer was accepted")
        } catch (error: ApkVerificationException) {
            assertThat(error.message).contains("signature")
        }
    }

    @Test
    fun undeclaredCachedApkIsRejected() {
        val item = download()
        File(fixtureDir, "newer.apk").copyTo(
            File(PathUtil.getAppDownloadDir(context, packageName, 73), "stale.apk")
        )
        rejects { ApkSetVerifier.verify(context, item) }
    }

    @Test
    fun stalePartialDownloadIsRejected() {
        val item = download()
        File(PathUtil.getAppDownloadDir(context, packageName, 73), "base.apk.tmp")
            .writeText("unfinished transfer")
        rejects { ApkSetVerifier.verify(context, item) }
    }

    @Test
    fun cancelledAndReplacedAttemptsAreNotInstallable() {
        val cancelled = download(status = DownloadStatus.CANCELLED)
        rejects { ApkSetVerifier.prepare(context, cancelled) }
        val replacement = cancelled.copy(status = DownloadStatus.QUEUED, downloadedAt = 8675310L)
        rejects { ApkSetVerifier.prepare(context, replacement) }
    }

    @Test
    fun verificationInterruptedBeforeInstallIsRejected() {
        rejects { ApkSetVerifier.verify(context, download()) { true } }
    }

    @Test
    fun privateVerifiedSnapshotCannotBeSwappedWithCacheReplacement() {
        val item = download()
        val staged = ApkSetVerifier.prepare(context, item)
        val original = staged.filesFor("").single()
        File(fixtureDir, "other-package.apk").copyTo(
            PathUtil.getLocalFile(context, item.fileList.single(), item), overwrite = true
        )
        assertThat(digest(original)).isEqualTo(item.fileList.single().sha256)
        rejects { ApkSetVerifier.verify(context, item) }
    }

    @Test
    fun validSignedSplitsRequireMatchingManifestAndSigner() {
        val item = download(includeSplit = true)
        ApkSetVerifier.verify(context, item)
        assertThat(ApkSetVerifier.prepare(context, item).filesFor("")).hasSize(2)
    }
}
