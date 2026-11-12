/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.artifact

import org.junit.Assert.*
import org.junit.Test

/** Source-bound read-only policy tests. No real PackageInstaller or device data writes. */
class ArtifactR3DP01P02PolicyTest {
    private val history = ArtifactHistoricalVersionPolicy
    private val safety = ArtifactDowngradeSafetyPolicy

    @Test fun p01ReferenceRequiresExactUnsignedBoundedVersion() {
        assertEquals(21L, history.parseVersion("00021"))
        for (bad in listOf("", "0", "-1", "+1", " 1", "1 ", "1.0", "https://x", "9223372036854775808", "9".repeat(40))) {
            assertNull(history.parseVersion(bad))
        }
    }

    @Test fun p01ProviderReferenceCannotMintPublisherPlayOrAvailability() {
        for (source in ArtifactSource.entries) {
            val record = history.reference("org.example.app", "42", source)!!
            assertFalse(record.availabilityConfirmed)
            assertFalse(record.publisherAuthenticated)
            assertFalse(record.playDeliveryVerified)
            assertFalse(record.installationApproved)
        }
        assertNull(history.reference("fake", "42", ArtifactSource.GITHUB_RELEASE))
    }

    @Test fun p01UnverifiedReferenceCannotBePromotedToVerifiedFile() {
        assertEquals(ArtifactHistoricalVersionPolicy.Match.UNVERIFIED_REFERENCE,
            history.compare("42", null).match)
        assertEquals(ArtifactHistoricalVersionPolicy.Match.REFUSED,
            history.compare("42", 43).match)
        assertEquals(ArtifactHistoricalVersionPolicy.Match.VERIFIED_MATCH,
            history.compare("42", 42).match)
        assertFalse(history.compare("42", 42).publisherAuthenticated)
        assertFalse(history.compare("42", 42).installationApproved)
        assertFalse(history.compare("42", 42).availabilityConfirmed)
    }

    @Test fun p01ManualReferenceMustMatchSignedVersionAtConsentTime() {
        assertTrue(ArtifactImportJourney.versionMatches("", 42))
        assertTrue(ArtifactImportJourney.versionMatches("00042", 42))
        assertFalse(ArtifactImportJourney.versionMatches("41", 42))
        assertFalse(ArtifactImportJourney.versionMatches("42.0", 42))
        assertFalse(ArtifactImportJourney.versionMatches("9999999999999999999999", 42))
    }

    @Test fun p01ShortlistRejectsCrossPackageAndConflictingVersionSources() {
        val local = history.reference("org.example.app", "12", ArtifactSource.LOCAL_DOCUMENT)!!
        val other = history.reference("org.other.app", "10", ArtifactSource.GITHUB_RELEASE)!!
        val same = history.reference("org.example.app", "12", ArtifactSource.APKMIRROR_BROWSER_HANDOFF)!!
        val older = history.reference("org.example.app", "8", ArtifactSource.GITHUB_RELEASE)!!
        assertTrue(history.shortlist("org.example.app", listOf(local, other)).isEmpty())
        assertTrue(history.shortlist("org.example.app", listOf(local, same)).isEmpty())
        assertEquals(listOf(12L, 8L), history.shortlist("org.example.app", listOf(older, local))
            .map { it.versionCode })
    }

    @Test fun p02DowngradeRequiresPositiveActiveSignerAndSeparateApproval() {
        val plan = safety.assess(4, 8, true)
        assertEquals(ArtifactDowngradeSafetyPolicy.Relation.DOWNGRADE, plan.relation)
        assertTrue(plan.separateDowngradeConsentRequired)
        assertFalse(plan.installedIdentityBlocked)
        assertFalse(plan.dataPreservationGuaranteed)
        assertFalse(plan.silentUninstallAllowed)
        assertFalse(plan.privilegedBypassAllowed)
    }

    @Test fun p02InstalledSignerMismatchCannotBeOverriddenByConsent() {
        for (signer in listOf(false, null)) {
            val verdict = safety.assess(4, 8, signer)
            assertTrue(verdict.installedIdentityBlocked)
            val review = review(4, 8, signer, approvedDowngrade = true)
            assertTrue(ArtifactImportDecision.Blocker.SIGNER_MISMATCH in
                ArtifactImportDecision.blockers(review))
        }
    }

    @Test fun p02MissingConsentBlockedEvenWhenSignerMatches() {
        assertTrue(ArtifactImportDecision.Blocker.DOWNGRADE_CONSENT_REQUIRED in
            ArtifactImportDecision.blockers(review(4, 8, true, approvedDowngrade = false)))
        assertFalse(ArtifactImportDecision.Blocker.DOWNGRADE_CONSENT_REQUIRED in
            ArtifactImportDecision.blockers(review(4, 8, true, approvedDowngrade = true)))
    }

    @Test fun p02InvalidInstalledStateNeverGrantsConsent() {
        assertTrue(safety.assess(5, null, true).installedIdentityBlocked)
        assertTrue(safety.assess(5, 0, true).installedIdentityBlocked)
        assertTrue(safety.assess(0, 5, true).installedIdentityBlocked)
        assertEquals(ArtifactDowngradeSafetyPolicy.Relation.NOT_INSTALLED,
            safety.assess(5, null, null).relation)
    }

    @Test fun p02UpgradeAndSameVersionNeedNoDowngradeConsent() {
        assertFalse(safety.assess(9, 8, true).separateDowngradeConsentRequired)
        assertFalse(safety.assess(8, 8, true).separateDowngradeConsentRequired)
        assertFalse(safety.assess(9, null, null).separateDowngradeConsentRequired)
    }

    @Test fun p02DisplayNeverPromisesDataPreservationOrRootBypass() {
        val text = safety.notice(4, 8, true)
        assertTrue(text.contains("Back up important app data"))
        assertTrue(text.contains("Data preservation is NOT guaranteed"))
        assertTrue(text.contains("Android may refuse"))
        assertTrue(text.contains("No automatic uninstall, data wipe or root bypass"))
    }

    @Test fun p02ReviewDisplaysVersionComparisonAndSignerGate() {
        val facts = ArtifactReviewPresentation.VerifiedFacts(
            ArtifactProvenance(ArtifactSource.LOCAL_DOCUMENT), 1L,
            listOf("a".repeat(64)), "org.example.app", 4L, 1,
            128L, "b".repeat(64), setOf("c".repeat(64)),
            8L, true, ArtifactTrustTier.INSTALLED_SIGNER_CONTINUITY)
        val review = ArtifactReviewPresentation.summary(facts)
        assertTrue(review.contains("Historical version: downgrade"))
        assertTrue(review.contains("Data preservation is NOT guaranteed"))
        assertTrue(ArtifactReviewPresentation.verification(facts)
            .contains("Back up important app data"))
    }

    @Test fun p01PackageReferenceMustMatchIndependentlySignedManifest() {
        assertTrue(history.matchesVerifiedPackage("", "org.example.app"))
        assertTrue(history.matchesVerifiedPackage("org.example.app", "org.example.app"))
        assertFalse(history.matchesVerifiedPackage("org.attacker.app", "org.example.app"))
        assertFalse(history.matchesVerifiedPackage("org.example.app ", "org.example.app"))
        assertFalse(history.matchesVerifiedPackage("org.example.app", "not-a-package"))
    }

    @Test fun p01ManualReferenceOriginMustBeBoundedAndNeverBeARawUrl() {
        val ok = history.reference("org.example.app", "7", ArtifactSource.GITHUB_RELEASE,
            "example.org")!!
        assertEquals("example.org", ok.originLabel)
        assertFalse(ok.publisherAuthenticated)
        assertFalse(ok.availabilityConfirmed)
        for (bad in listOf("https://host/path", "user@host", "query?token=x", "org/path",
                "a".repeat(201), "a\n", " edge ", "")) {
            assertNull(history.reference("org.example.app", "7", ArtifactSource.GITHUB_RELEASE, bad))
        }
    }

    @Test fun p01ManualDiscoveryIsDeterministicAndNeverFetchesOrApproves() {
        val refs = (1..64).map {
            history.reference("org.example.app", "$it", ArtifactSource.GITHUB_RELEASE)!!
        }
        val sorted = history.shortlist("org.example.app", refs.reversed())
        assertEquals(64, sorted.size)
        assertEquals(64L, sorted.first().versionCode)
        assertEquals(1L, sorted.last().versionCode)
        assertTrue(history.shortlist("org.example.app", refs + refs.first()).isEmpty())
        assertTrue(sorted.none { it.availabilityConfirmed || it.installationApproved })
    }

    @Test fun p01KnownUnsupportedMinSdkIsIncompatible() {
        val result = history.preflight(37, 36, null, listOf("arm64-v8a"), true)
        assertEquals(ArtifactHistoricalVersionPolicy.Compatibility.INCOMPATIBLE,
            result.compatibility)
        assertFalse(result.finalAndroidInstallConfirmed)
        assertFalse(result.dataPreservationGuaranteed)
    }

    @Test fun p01KnownIncompatibleAbiIsIncompatible() {
        val result = history.preflight(25, 36, "x86_64", listOf("arm64-v8a"), true)
        assertEquals(ArtifactHistoricalVersionPolicy.Compatibility.INCOMPATIBLE,
            result.compatibility)
    }

    @Test fun p01MissingMetadataNeverPretendsInstallability() {
        val missingSdk = history.preflight(null, 36, null, listOf("arm64-v8a"), true)
        val uncheckedSplits = history.preflight(26, 36, null, listOf("arm64-v8a"), false)
        assertEquals(ArtifactHistoricalVersionPolicy.Compatibility.UNKNOWN, missingSdk.compatibility)
        assertEquals(ArtifactHistoricalVersionPolicy.Compatibility.UNKNOWN, uncheckedSplits.compatibility)
        assertTrue(history.displayPreflight(missingSdk).contains("UNKNOWN"))
    }

    @Test fun p01LimitedPreflightNeverClaimsAndroidInstallation() {
        val pass = history.preflight(26, 36, "arm64_v8a", listOf("arm64-v8a"), true)
        assertEquals(ArtifactHistoricalVersionPolicy.Compatibility.LIMITED_PREFLIGHT_ONLY,
            pass.compatibility)
        assertFalse(pass.finalAndroidInstallConfirmed)
        assertFalse(pass.dataPreservationGuaranteed)
        assertTrue(history.displayPreflight(pass).contains("NOT confirmed"))
    }

    @Test fun p01HistoricalDiscoveryDisplayIsExplicitlyUntrusted() {
        val ref = history.reference("org.example.app", "12", ArtifactSource.FDROID_REPOSITORY)!!
        val text = history.displayReference("org.example.app", ref)
        assertTrue(text.contains("unverified reference"))
        assertTrue(text.contains("availability UNKNOWN"))
        assertTrue(history.displayReference("org.other.app", ref).contains("REFUSED"))
    }

    @Test fun p01ReviewSurfacesCompatibilityWithoutPublisherClaims() {
        val snapshot = history.preflight(36, 36, null, listOf("arm64-v8a"), true)
        val facts = ArtifactReviewPresentation.VerifiedFacts(
            ArtifactProvenance(ArtifactSource.LOCAL_DOCUMENT), 1L,
            listOf("a".repeat(64)), "org.example.app", 4L, 1,
            128L, "b".repeat(64), setOf("c".repeat(64)),
            null, null, ArtifactTrustTier.APK_SIGNER_VALID_PUBLISHER_UNANCHORED,
            snapshot)
        val body = ArtifactReviewPresentation.summary(facts)
        assertTrue(body.contains("basic signed-file SDK/ABI checks passed"))
        assertTrue(body.contains("Publisher identity"))
        assertTrue(ArtifactReviewPresentation.verification(facts).contains("read-only"))
    }

    @Test fun p02DataRiskAcknowledgementIndependentFromDowngradeConsent() {
        val riskMissing = review(4, 8, true, approvedDowngrade = true)
        val blocks = ArtifactImportDecision.blockers(riskMissing)
        assertTrue(ArtifactImportDecision.Blocker.DOWNGRADE_DATA_LOSS_RISK_ACK_REQUIRED in blocks)
        assertFalse(ArtifactImportDecision.Blocker.DOWNGRADE_CONSENT_REQUIRED in blocks)
        val consentMissing = review(4, 8, true, approvedDowngrade = false, approvedRisk = true)
        assertTrue(ArtifactImportDecision.Blocker.DOWNGRADE_CONSENT_REQUIRED in
            ArtifactImportDecision.blockers(consentMissing))
        val both = review(4, 8, true, approvedDowngrade = true, approvedRisk = true)
        assertFalse(ArtifactImportDecision.Blocker.DOWNGRADE_DATA_LOSS_RISK_ACK_REQUIRED in
            ArtifactImportDecision.blockers(both))
        assertTrue(ArtifactImportDecision.blockers(both).isEmpty())
    }

    @Test fun p02AckCannotOverrideUnknownOrMismatchedInstalledSigner() {
        for (signer in listOf(false, null)) {
            val blocks = ArtifactImportDecision.blockers(
                review(4, 8, signer, approvedDowngrade = true, approvedRisk = true))
            assertTrue(ArtifactImportDecision.Blocker.SIGNER_MISMATCH in blocks)
        }
        assertTrue(ArtifactDowngradeSafetyPolicy.assess(4, 8, null).installedIdentityBlocked)
    }

    @Test fun p02RiskGateAppliesOnlyToActualDowngrades() {
        assertTrue(safety.assess(4, 8, true).separateDataRiskAcknowledgementRequired)
        for (candidate in listOf(8L, 9L)) {
            assertFalse(safety.assess(candidate, 8, true).separateDataRiskAcknowledgementRequired)
            assertFalse(ArtifactImportDecision.Blocker.DOWNGRADE_DATA_LOSS_RISK_ACK_REQUIRED in
                ArtifactImportDecision.blockers(review(candidate, 8, true, approvedDowngrade = false)))
        }
        assertFalse(safety.assess(1, null, null).separateDataRiskAcknowledgementRequired)
    }

    @Test fun p02NoticeDoesNotPretendBackupExistsOrAndroidWillInstall() {
        val notice = safety.notice(4, 8, true)
        assertTrue(notice.contains("AuroraStore has NOT verified any backup"))
        assertTrue(notice.contains("Data preservation is NOT guaranteed"))
        assertTrue(notice.contains("Android may refuse"))
        assertFalse(safety.assess(4, 8, true).dataPreservationGuaranteed)
    }

    private fun review(version: Long, installed: Long?, matches: Boolean?,
                       approvedDowngrade: Boolean,
                       approvedRisk: Boolean = false): ArtifactImportDecision.Review =
        ArtifactImportDecision.Review("org.example.app", version,
            signerVerified = true, installedSignerMatches = matches,
            installedVersion = installed, trustedPublisherAnchor = false,
            userApprovedInstall = true, userAcceptedUnknownPublisher = true,
            userApprovedDowngrade = approvedDowngrade,
            userAcknowledgedDataLossRisk = approvedRisk)
}
