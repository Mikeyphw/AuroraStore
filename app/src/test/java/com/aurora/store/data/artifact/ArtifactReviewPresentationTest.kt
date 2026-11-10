/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import com.google.common.truth.Truth.assertThat
import org.junit.Test

class ArtifactReviewPresentationTest {
    private fun facts(
        source: ArtifactProvenance = ArtifactProvenance(ArtifactSource.LOCAL_DOCUMENT, "selected.apks"),
        installedVersion: Long? = null,
        matches: Boolean? = null,
        trust: ArtifactTrustTier = ArtifactTrustTier.APK_SIGNER_VALID_PUBLISHER_UNANCHORED
    ) = ArtifactReviewPresentation.VerifiedFacts(
        source, 1234L, listOf("c".repeat(64), "d".repeat(64)),
        "org.example.app", 32L, 2, 111L, "a".repeat(64),
        setOf("b".repeat(64)), installedVersion, matches, trust
    )

    @Test fun verifiedBytesAreNotReportedAsInstalled() {
        val display = ArtifactReviewPresentation.verification(facts())
        assertThat(display).contains("VERIFIED APK FILES — NOT INSTALLED")
        assertThat(display).contains("SHA-256")
        assertThat(display).contains("org.example.app")
        assertThat(display).contains("unverified reference: selected.apks")
        assertThat(display).contains("NOT independently verified")
        assertThat(display).contains("no Play or publisher proof")
        assertThat(display).contains("Attempt generation: 1234")
        assertThat(display).contains("#1: ${"c".repeat(64)}")
        assertThat(display).contains("Distribution: LOCAL_IMPORT")
    }

    @Test fun browserClaimDoesNotBecomeAuthenticatedDownload() {
        val display = ArtifactReviewPresentation.verification(facts(
            source = ArtifactProvenance(ArtifactSource.GITHUB_RELEASE, "github.com")
        ))
        assertThat(display).contains("GitHub Releases (browser claim)")
        assertThat(display).contains("unverified reference: github.com")
        assertThat(display).doesNotContain("Verified GitHub publisher")
    }

    @Test fun installedContinuityIsNotPublisherProof() {
        val f = facts(installedVersion = 31L, matches = true,
            trust = ArtifactTrustTier.INSTALLED_SIGNER_CONTINUITY)
        assertThat(ArtifactReviewPresentation.consentNeedsUnknownPublisher(f)).isFalse()
        assertThat(ArtifactReviewPresentation.trust(f))
            .contains("does not independently prove who published")
        assertThat(ArtifactReviewPresentation.consentNeedsDowngrade(f)).isFalse()
    }

    @Test fun downgradeIsSeparateFromPublisherAcknowledgement() {
        val f = facts(installedVersion = 40L, matches = true,
            trust = ArtifactTrustTier.INSTALLED_SIGNER_CONTINUITY)
        assertThat(ArtifactReviewPresentation.consentNeedsDowngrade(f)).isTrue()
        assertThat(ArtifactReviewPresentation.verification(f)).contains("Separate approval required")
    }

    @Test fun unanchoredNewInstallationNeedsPublisherConsent() {
        assertThat(ArtifactReviewPresentation.consentNeedsUnknownPublisher(facts())).isTrue()
        assertThat(ArtifactReviewPresentation.consentNeedsDowngrade(facts())).isFalse()
    }

    @Test fun mismatchCannotBePresentedAsTrust() {
        val display = ArtifactReviewPresentation.verification(facts(installedVersion = 40L, matches = false))
        assertThat(display).contains("MISMATCH — blocked")
        assertThat(ArtifactReviewPresentation.trust(facts(installedVersion=40L,matches=false)))
            .contains("installation must be blocked")
    }

    @Test fun humanReadableConsentBlockersMapToSeparateControls() {
        val text = ArtifactReviewPresentation.blockerDescription(setOf(
            ArtifactImportDecision.Blocker.EXPLICIT_INSTALL_CONSENT_REQUIRED,
            ArtifactImportDecision.Blocker.UNANCHORED_PUBLISHER_CONSENT_REQUIRED,
            ArtifactImportDecision.Blocker.DOWNGRADE_CONSENT_REQUIRED
        ))
        assertThat(text).contains("Approve installation")
        assertThat(text).contains("Acknowledge unverified publisher")
        assertThat(text).contains("Approve version downgrade separately")
    }

    @Test fun pendingAndroidStateMustNeverBeSuccess() {
        for (state in listOf(
            ArtifactSessionReceiptPolicy.State.AWAITING_ANDROID,
            ArtifactSessionReceiptPolicy.State.AWAITING_USER_APPROVAL,
            ArtifactSessionReceiptPolicy.State.APPROVAL_UI_UNAVAILABLE
        )) {
            assertThat(ArtifactReviewPresentation.androidResult(state)).contains("NOT confirmed")
            assertThat(ArtifactReviewPresentation.androidResult(state)).doesNotContain("SUCCESS")
        }
        assertThat(ArtifactReviewPresentation.androidResult(
            ArtifactSessionReceiptPolicy.State.INSTALLED_BY_ANDROID)).contains("SUCCESS")
        assertThat(ArtifactReviewPresentation.androidResult(
            ArtifactSessionReceiptPolicy.State.ANDROID_REJECTED)).contains("REJECTED")
    }

    @Test fun androidFailureReasonsAreReadable() {
        assertThat(ArtifactReviewPresentation.androidFailureReason(2)).contains("policy blocked")
        assertThat(ArtifactReviewPresentation.androidFailureReason(6)).contains("Insufficient storage")
        assertThat(ArtifactReviewPresentation.androidFailureReason(-1)).contains("Unknown")
    }

    @Test fun noReceiptIsNotClaimedAsSuccessful() {
        assertThat(ArtifactReviewPresentation.androidResult(null))
            .contains("No authenticated Android install outcome")
    }
    @Test fun claimedVerifiedPublisherEnumCannotHideUnknownPublisherConsent() {
        val f = facts(trust = ArtifactTrustTier.VERIFIED_PUBLISHER_IDENTITY)
        assertThat(ArtifactReviewPresentation.consentNeedsUnknownPublisher(f)).isTrue()
        assertThat(ArtifactReviewPresentation.trust(f)).contains("attestation unavailable")
    }
}
