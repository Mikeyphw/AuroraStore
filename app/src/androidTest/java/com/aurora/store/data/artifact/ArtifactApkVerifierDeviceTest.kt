/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import android.net.Uri
import android.os.Build
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.util.UUID

/** Real installed debug APK signs the positive fixture; never fabricates signing receipts. */
@RunWith(AndroidJUnit4::class)
class ArtifactApkVerifierDeviceTest {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext

    @Test
    fun realInstalledSignedApkAuthenticatesExactPackageAndSigner() {
        assertThat(Build.VERSION.SDK_INT).isEqualTo(36)
        val original = File(context.applicationInfo.sourceDir)
        val staged = ArtifactPrivateStager.stage(context, Uri.fromFile(original), "fixture.apk") { false }
        try {
            val verified = ArtifactApkVerifier.verify(
                context, staged, ArtifactProvenance(ArtifactSource.LOCAL_DOCUMENT)
            ) { false }
            assertThat(verified.attempt.packageName).isEqualTo(context.packageName)
            assertThat(verified.signerSha256).isNotEmpty()
            assertThat(verified.signerMatchesInstalled).isTrue()
            assertThat(verified.trustTier).isEqualTo(ArtifactTrustTier.INSTALLED_SIGNER_CONTINUITY)
            assertThat(verified.isPlayEvidence).isFalse()
        } finally {
            staged.discard()
        }
    }

    @Test
    fun corruptUnsignedApkCannotMintVerifiedImport() {
        assertThat(Build.VERSION.SDK_INT).isEqualTo(36)
        val fake = File(context.cacheDir, "unsigned-${UUID.randomUUID()}.apk")
        fake.writeBytes(ByteArray(4096) { 0x42 })
        try {
            val staged = ArtifactPrivateStager.stage(context, Uri.fromFile(fake), "fake.apk") { false }
            try {
                assertThat(runCatching {
                    ArtifactApkVerifier.verify(
                        context, staged, ArtifactProvenance(ArtifactSource.LOCAL_DOCUMENT)
                    ) { false }
                }.isFailure).isTrue()
            } finally {
                staged.discard()
            }
        } finally {
            fake.delete()
        }
    }

    @Test
    fun mutatedStagedBytesCannotBeVerified() {
        assertThat(Build.VERSION.SDK_INT).isEqualTo(36)
        val original = File(context.applicationInfo.sourceDir)
        val staged = ArtifactPrivateStager.stage(context, Uri.fromFile(original), "fixture.apk") { false }
        try {
            val file = staged.apks.single().file
            assertThat(file.setWritable(true)).isTrue()
            file.appendBytes(byteArrayOf(1, 2, 3))
            assertThat(runCatching {
                ArtifactApkVerifier.verify(
                    context, staged, ArtifactProvenance(ArtifactSource.LOCAL_DOCUMENT)
                ) { false }
            }.isFailure).isTrue()
        } finally {
            staged.discard()
        }
    }
}
