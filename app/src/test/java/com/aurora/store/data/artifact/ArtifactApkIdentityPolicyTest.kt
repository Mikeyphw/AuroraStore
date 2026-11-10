/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import com.google.common.truth.Truth.assertThat
import org.junit.Test

/** Pure decisions: they do NOT fabricate Android signing or APK verification. */
class ArtifactApkIdentityPolicyTest {
    private val policy = ArtifactApkIdentityPolicy
    private val validPackage = "org.example.myapp"

    @Test fun canonicalBaseAndConfigSplitsAreAccepted() {
        for (name in listOf(null, "feature", "config.en", "config.arm64_v8a", "feature-name")) {
            policy.requireManifestIdentity(validPackage, 1024L, name)
        }
    }

    @Test fun invalidSplitNamesCannotMasqueradeAsBase() {
        for (name in listOf("", " ", "base", "config", ".hidden", "config.",
            "a..b", "a--b", "../base", "\\base", "config/en", "config en", "😎")) {
            assertThat(runCatching { policy.requireManifestIdentity(validPackage, 7, name) }.isFailure).isTrue()
        }
    }

    @Test fun longSplitNamesAndControlCharactersAreRejected() {
        for (name in listOf("a".repeat(129), "foo\nbar", "foo\u0000bar")) {
            assertThat(runCatching { policy.requireManifestIdentity(validPackage, 9, name) }.isFailure).isTrue()
        }
    }

    @Test fun packageAndVersionMustBeExactAndPositive() {
        for (name in listOf("", "org", "org..app", "org/app", "a.b ")) {
            assertThat(runCatching { policy.requireManifestIdentity(name, 1, null) }.isFailure).isTrue()
        }
        for (version in listOf(-1L, 0L)) {
            assertThat(runCatching { policy.requireManifestIdentity(validPackage, version, null) }.isFailure).isTrue()
        }
    }

    @Test fun baseRequiresAndroidArchiveParse() {
        assertThat(runCatching {
            policy.requirePlatformAgreement(validPackage, 42L, true, null, null)
        }.isFailure).isTrue()
    }

    @Test fun basePlatformIdentityMatchesExactly() {
        policy.requirePlatformAgreement(validPackage, 42L, true, validPackage, 42L)
        assertThat(runCatching {
            policy.requirePlatformAgreement(validPackage, 42L, true, "org.example.other", 42L)
        }.isFailure).isTrue()
        assertThat(runCatching {
            policy.requirePlatformAgreement(validPackage, 42L, true, validPackage, 43L)
        }.isFailure).isTrue()
    }

    @Test fun splitPlatformIdentityCannotContradictSignedManifest() {
        policy.requirePlatformAgreement(validPackage, 42L, false, null, null)
        policy.requirePlatformAgreement(validPackage, 42L, false, validPackage, 42L)
        assertThat(runCatching {
            policy.requirePlatformAgreement(validPackage, 42L, false, validPackage, 43L)
        }.isFailure).isTrue()
        assertThat(runCatching {
            policy.requirePlatformAgreement(validPackage, 42L, false, "org.evil.app", 42L)
        }.isFailure).isTrue()
        assertThat(runCatching {
            policy.requirePlatformAgreement(validPackage, 42L, false, null, 42L)
        }.isFailure).isTrue()
    }

    @Test fun exactlyMatchingActiveInstalledSignersAreAccepted() {
        val digests = setOf("a".repeat(64), "b".repeat(64))
        assertThat(policy.installedSignerStatus(digests, digests, digests))
            .isEqualTo(ArtifactApkIdentityPolicy.InstalledSignerStatus.ACTIVE_MATCH)
    }

    @Test fun historyOnlySignerIsNotAcceptedAsActiveContinuity() {
        val prior = "a".repeat(64)
        val current = "b".repeat(64)
        assertThat(policy.installedSignerStatus(setOf(prior), setOf(current), setOf(prior, current)))
            .isEqualTo(ArtifactApkIdentityPolicy.InstalledSignerStatus.HISTORY_ONLY_UNVERIFIED)
    }

    @Test fun newUnrelatedSignerCannotReplaceInstalledSigner() {
        assertThat(policy.installedSignerStatus(setOf("a"), setOf("b"), emptySet()))
            .isEqualTo(ArtifactApkIdentityPolicy.InstalledSignerStatus.MISMATCH)
    }

    @Test fun signerSetPartialOverlapIsNotContinuity() {
        assertThat(policy.installedSignerStatus(setOf("a", "b"), setOf("a"), setOf("a", "b")))
            .isEqualTo(ArtifactApkIdentityPolicy.InstalledSignerStatus.MISMATCH)
    }

    @Test fun emptySignerEvidenceCannotBeTrusted() {
        assertThat(policy.installedSignerStatus(emptySet(), setOf("a"), setOf("a")))
            .isEqualTo(ArtifactApkIdentityPolicy.InstalledSignerStatus.MISMATCH)
        assertThat(policy.installedSignerStatus(setOf("a"), emptySet(), setOf("a")))
            .isEqualTo(ArtifactApkIdentityPolicy.InstalledSignerStatus.MISMATCH)
    }

    @Test fun uniqueBaseAndManifestSplitSetIsRequired() {
        policy.requireUniqueSplitNames(listOf(null, "config.en", "config.arm64_v8a"))
    }

    @Test fun duplicateManifestSplitIdentitiesAreRejectedEvenWhenFilenamesDiffer() {
        assertThat(runCatching {
            policy.requireUniqueSplitNames(listOf(null, "config.en", "config.en"))
        }.isFailure).isTrue()
    }

    @Test fun missingOrMultipleBaseManifestsAreRejected() {
        for (names in listOf(listOf("feature"), listOf(null, null), emptyList<String?>())) {
            assertThat(runCatching { policy.requireUniqueSplitNames(names) }.isFailure).isTrue()
        }
    }
}
