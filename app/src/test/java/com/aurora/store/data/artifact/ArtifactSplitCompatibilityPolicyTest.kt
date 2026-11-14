/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.artifact

import com.google.common.truth.Truth.assertThat
import org.junit.Test

class ArtifactSplitCompatibilityPolicyTest {
    private val apks = ArtifactArchivePolicy.Format.APKS
    private val abis = listOf("arm64-v8a", "armeabi-v7a")
    private fun refused(names: List<String?>, abis: List<String> = this.abis) =
        runCatching { ArtifactSplitCompatibilityPolicy.check(apks, names, abis) }.isFailure

    @Test fun standaloneBaseOnlyIsNotClaimedFullyCompatible() {
        val result = ArtifactSplitCompatibilityPolicy.check(
            ArtifactArchivePolicy.Format.APK, listOf(null), abis
        )
        assertThat(result.installabilityConfirmed).isFalse()
        assertThat(result.splitCount).isEqualTo(0)
    }
    @Test fun standaloneCannotClaimMultipleApks() {
        assertThat(runCatching { ArtifactSplitCompatibilityPolicy.check(
            ArtifactArchivePolicy.Format.APK, listOf(null, "config.en"), abis
        ) }.isFailure).isTrue()
    }
    @Test fun missingBaseIsRefused() { assertThat(refused(listOf("config.en"))).isTrue() }
    @Test fun twoBasesAreRefused() { assertThat(refused(listOf(null, null))).isTrue() }
    @Test fun duplicateSplitIdsAreRefused() {
        assertThat(refused(listOf(null,"config.en","config.en"))).isTrue()
    }
    @Test fun exactSupportedAbiIsAcceptedWithoutClaimingFullInstallability() {
        val result = ArtifactSplitCompatibilityPolicy.check(apks, listOf(null,"config.arm64_v8a"), abis)
        assertThat(result.selectedAbiQualifier).isEqualTo("arm64_v8a")
        assertThat(result.installabilityConfirmed).isFalse()
    }
    @Test fun wrongAbiIsRefused() {
        assertThat(refused(listOf(null,"config.x86_64"))).isTrue()
    }
    @Test fun absentDeviceAbiListFailsClosed() {
        assertThat(refused(listOf(null,"config.arm64_v8a"), emptyList())).isTrue()
    }
    @Test fun noSilentMultiAbiVariantSelection() {
        assertThat(refused(listOf(null,"config.arm64_v8a","config.x86_64"))).isTrue()
    }
    @Test fun noSilentMultiDensityVariantSelection() {
        assertThat(refused(listOf(null,"config.hdpi","config.xxhdpi"))).isTrue()
    }
    @Test fun singleDensityAndMultipleLanguagesMayCoexist() {
        val a = ArtifactSplitCompatibilityPolicy.check(
            apks,listOf(null,"config.xxhdpi","config.en","config.pt_rBR"), abis
        )
        assertThat(a.selectedDensityQualifier).isEqualTo("xxhdpi")
        assertThat(a.splitCount).isEqualTo(3)
    }
    @Test fun unsupportedOrUnknownTargetingFailsClosed() {
        assertThat(refused(listOf(null,"config.sw600dp"))).isTrue()
    }
    @Test fun featureScopedConfigRequiresFeatureApk() {
        assertThat(refused(listOf(null,"camera.config.arm64_v8a"))).isTrue()
        val result = ArtifactSplitCompatibilityPolicy.check(
            apks,listOf(null,"camera","camera.config.arm64_v8a"), abis
        )
        assertThat(result.featureDependenciesUnverified).isTrue()
    }
    @Test fun featureDependencyNotProvenByName() {
        val result = ArtifactSplitCompatibilityPolicy.check(apks,listOf(null,"camera"), abis)
        assertThat(result.featureDependenciesUnverified).isTrue()
        assertThat(result.installabilityConfirmed).isFalse()
    }
    @Test fun allSupportedArchiveLabelsRemainConservative() {
        for (format in listOf(ArtifactArchivePolicy.Format.APKS,
            ArtifactArchivePolicy.Format.APKM, ArtifactArchivePolicy.Format.XAPK)) {
            val result = ArtifactSplitCompatibilityPolicy.check(format,listOf(null,"config.en"),abis)
            assertThat(result.installabilityConfirmed).isFalse()
        }
    }
}
