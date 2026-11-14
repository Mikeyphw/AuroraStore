/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import com.google.common.truth.Truth.assertThat
import org.junit.Test
import java.io.File

/** Contract-level tests: fabricated test fixtures are NOT proof of cryptographic signature verification. */
class ArtifactOriginBoundaryTest {
    private fun verified(
        source: ArtifactSource = ArtifactSource.LOCAL_DOCUMENT,
        version: Long = 42L,
        generation: Long = 317L,
        installedVersion: Long? = null,
        continuity: Boolean? = null,
        tier: ArtifactTrustTier = ArtifactTrustTier.APK_SIGNER_VALID_PUBLISHER_UNANCHORED,
        sha: String = "a".repeat(64)
    ): ArtifactApkVerifier.VerifiedImport {
        val apks = listOf(
            ArtifactPrivateStager.CopiedApk(File("part-000.apk"), sha, 101L),
            ArtifactPrivateStager.CopiedApk(File("part-001.apk"), "b".repeat(64), 103L)
        )
        val staged = ArtifactPrivateStager.Staged(
            File("fake-private-cache"), ArtifactArchivePolicy.Format.APKS, apks,
            "c".repeat(64), 204L
        )
        val attempt = ArtifactAttempt("org.example.safe", version, generation,
            ArtifactProvenance(source, "selected.apks"))
        return ArtifactApkVerifier.VerifiedImport(
            staged, attempt, setOf("d".repeat(64)), tier,
            installedVersion, continuity, listOf(null, "config.en"), 204L,
            signedFeatureDependencies = listOf<String?>(null, null)
        )
    }

    @Test fun everyNonPlaySourceIsSeparatelyClassified() {
        val expected = mapOf(
            ArtifactSource.LOCAL_DOCUMENT to ArtifactOriginFamily.LOCAL_IMPORT,
            ArtifactSource.DEVELOPER_WEBSITE to ArtifactOriginFamily.DEVELOPER_RELEASE,
            ArtifactSource.GITHUB_RELEASE to ArtifactOriginFamily.GITHUB_RELEASE,
            ArtifactSource.APKMIRROR_BROWSER_HANDOFF to ArtifactOriginFamily.APKMIRROR_BROWSER,
            ArtifactSource.FDROID_REPOSITORY to ArtifactOriginFamily.FDROID_BROWSER,
            ArtifactSource.APKPURE_OPT_IN to ArtifactOriginFamily.APKPURE_OPT_IN_BROWSER
        )
        for ((src, family) in expected) {
            assertThat(ArtifactOriginBoundary.family(src)).isEqualTo(family)
            assertThat(ArtifactOriginBoundary.claimOnly(src))
                .isEqualTo(ArtifactOriginAssurance.UNVERIFIED_SOURCE_CLAIM)
        }
        assertThat(expected.values).doesNotContain(ArtifactOriginFamily.GOOGLE_PLAY)
    }

    @Test fun developerBrowserClaimNeverBecomesOfficialPublisherProof() {
        val r = ArtifactIndependentEvidence.fromVerifiedImport(verified(ArtifactSource.DEVELOPER_WEBSITE))
        assertThat(r.distribution).isEqualTo(ArtifactOriginFamily.DEVELOPER_RELEASE)
        assertThat(r.assurance).isEqualTo(ArtifactOriginAssurance.SIGNED_APK_PUBLISHER_UNANCHORED)
        assertThat(r.hasPublisherAttestation).isFalse()
        assertThat(r.isPlayEvidence).isFalse()
    }

    @Test fun githubBrowserClaimNeverBecomesAuthenticatedReleaseProof() {
        val r = ArtifactIndependentEvidence.fromVerifiedImport(verified(ArtifactSource.GITHUB_RELEASE))
        assertThat(r.distribution).isEqualTo(ArtifactOriginFamily.GITHUB_RELEASE)
        assertThat(r.hasPublisherAttestation).isFalse()
        assertThat(r.isPlayEvidence).isFalse()
    }

    @Test fun exactPackageVersionGenerationAndDigestsAreRetained() {
        val r = ArtifactIndependentEvidence.fromVerifiedImport(verified(generation=123L, version=23L))
        assertThat(r.packageName).isEqualTo("org.example.safe")
        assertThat(r.versionCode).isEqualTo(23L)
        assertThat(r.attemptGeneration).isEqualTo(123L)
        assertThat(r.selectedFileSha256).isEqualTo("c".repeat(64))
        assertThat(r.apkSha256).containsExactly("a".repeat(64), "b".repeat(64)).inOrder()
        assertThat(r.signingCertificateSha256).containsExactly("d".repeat(64))
    }

    @Test fun installedContinuityDoesNotProvePublisherOrPlay() {
        val r = ArtifactIndependentEvidence.fromVerifiedImport(verified(
            installedVersion=30L, continuity=true,
            tier=ArtifactTrustTier.INSTALLED_SIGNER_CONTINUITY
        ))
        assertThat(r.assurance).isEqualTo(ArtifactOriginAssurance.INSTALLED_CERTIFICATE_CONTINUITY)
        assertThat(r.hasPublisherAttestation).isFalse()
        assertThat(r.isPlayEvidence).isFalse()
    }

    @Test fun forgedVerifiedPublisherTierIsRejected() {
        assertThat(runCatching { ArtifactIndependentEvidence.fromVerifiedImport(verified(
            tier=ArtifactTrustTier.VERIFIED_PUBLISHER_IDENTITY
        )) }.isFailure).isTrue()
    }

    @Test fun unknownTrustCannotMintSignerEvidence() {
        assertThat(runCatching { ArtifactIndependentEvidence.fromVerifiedImport(verified(
            tier=ArtifactTrustTier.UNKNOWN
        )) }.isFailure).isTrue()
    }

    @Test fun invalidPerApkHashIsRejected() {
        assertThat(runCatching { ArtifactIndependentEvidence.fromVerifiedImport(verified(
            sha="0".repeat(63)
        )) }.isFailure).isTrue()
    }

    @Test fun impossibleSignerContinuityIsRejected() {
        assertThat(runCatching { ArtifactIndependentEvidence.fromVerifiedImport(verified(
            installedVersion=10L, continuity=false
        )) }.isFailure).isTrue()
        assertThat(runCatching { ArtifactIndependentEvidence.fromVerifiedImport(verified(
            installedVersion=10L, continuity=true
        )) }.isFailure).isTrue()
        assertThat(runCatching { ArtifactIndependentEvidence.fromVerifiedImport(verified(
            installedVersion=null, continuity=true
        )) }.isFailure).isTrue()
    }

    @Test fun independentTrustedConstructorsAreNotExposedToBrowserClaims() {
        for (clazz in listOf(
            AuthenticatedArtifactOrigin.GooglePlayVerified::class.java,
            AuthenticatedArtifactOrigin.OfficialDeveloperVerified::class.java,
            AuthenticatedArtifactOrigin.GitHubReleaseVerified::class.java,
            ArtifactIndependentEvidence::class.java
        )) assertThat(clazz.constructors.any { !it.isSynthetic }).isFalse()
    }

    @Test fun forgedSignedBytesCannotBeReinterpretedAsPlayProof() {
        for (source in ArtifactSource.entries) {
            val r = ArtifactIndependentEvidence.fromVerifiedImport(verified(source))
            assertThat(r.isPlayEvidence).isFalse()
            assertThat(r.assurance).isNotEqualTo(ArtifactOriginAssurance.PLAY_DELIVERY_VERIFIED)
        }
    }
}
