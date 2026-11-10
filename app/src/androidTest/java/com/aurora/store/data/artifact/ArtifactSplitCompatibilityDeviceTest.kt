/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.artifact

import android.os.Build
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith

/** Read-only API36 targeting contract; no APK install, Play access or metadata trust. */
@RunWith(AndroidJUnit4::class)
class ArtifactSplitCompatibilityDeviceTest {
    @Test fun hostAbiTokenIsAcceptedAsOnlyCandidate() {
        assertThat(Build.VERSION.SDK_INT).isEqualTo(36)
        val device = Build.SUPPORTED_ABIS.toList()
        assertThat(device).isNotEmpty()
        val target = device.first().replace('-', '_')
        val a = ArtifactSplitCompatibilityPolicy.check(
            ArtifactArchivePolicy.Format.APKS,listOf(null,"config.$target"),device
        )
        assertThat(a.installabilityConfirmed).isFalse()
    }
    @Test fun twoDifferentAbiVariantsCannotBeSilentlyInstalledTogether() {
        assertThat(runCatching {
            ArtifactSplitCompatibilityPolicy.check(
                ArtifactArchivePolicy.Format.APKM,
                listOf(null,"config.arm64_v8a","config.x86_64"),Build.SUPPORTED_ABIS.toList()
            )
        }.isFailure).isTrue()
    }
    @Test fun extraDensityVariantsCannotBeSilentlyInstalledTogether() {
        assertThat(runCatching {
            ArtifactSplitCompatibilityPolicy.check(
                ArtifactArchivePolicy.Format.XAPK,
                listOf(null,"config.hdpi","config.xxhdpi"),Build.SUPPORTED_ABIS.toList()
            )
        }.isFailure).isTrue()
    }
    @Test fun featuresRemainUnqualifiedWithoutManifestDependencies() {
        val assessment = ArtifactSplitCompatibilityPolicy.check(
            ArtifactArchivePolicy.Format.APKS,listOf(null,"camera"),Build.SUPPORTED_ABIS.toList()
        )
        assertThat(assessment.featureDependenciesUnverified).isTrue()
        assertThat(assessment.installabilityConfirmed).isFalse()
    }
}
