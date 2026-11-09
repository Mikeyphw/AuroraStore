/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import com.google.common.truth.Truth.assertThat
import org.junit.Test

class ArtifactImportDecisionTest {
    private fun review() = ArtifactImportDecision.Review(
        packageName = "org.example.test", versionCode = 42L,
        signerVerified = true, installedSignerMatches = null,
        installedVersion = null, trustedPublisherAnchor = false,
        userApprovedInstall = true, userAcceptedUnknownPublisher = true,
        userApprovedDowngrade = false
    )

    @Test

    fun validUnanchoredInstallRequiresExplicitUserConsent() {
        assertThat(ArtifactImportDecision.blockers(review())).isEmpty()
        assertThat(ArtifactImportDecision.blockers(review().copy(userApprovedInstall = false)))
            .contains(ArtifactImportDecision.Blocker.EXPLICIT_INSTALL_CONSENT_REQUIRED)
        assertThat(ArtifactImportDecision.blockers(review().copy(userAcceptedUnknownPublisher = false)))
            .contains(ArtifactImportDecision.Blocker.UNANCHORED_PUBLISHER_CONSENT_REQUIRED)
    }

    @Test

    fun invalidOrUnverifiedApkIsNeverInstallable() {
        for (invalid in listOf("", "com", "com..evil", "evil/file")) {
            assertThat(ArtifactImportDecision.blockers(review().copy(packageName = invalid)))
                .contains(ArtifactImportDecision.Blocker.INVALID_IDENTITY)
        }
        assertThat(ArtifactImportDecision.blockers(review().copy(versionCode = 0)))
            .contains(ArtifactImportDecision.Blocker.INVALID_IDENTITY)
        assertThat(ArtifactImportDecision.blockers(review().copy(signerVerified = false)))
            .contains(ArtifactImportDecision.Blocker.UNVERIFIED_SIGNATURE)
    }

    @Test

    fun installedSignerMismatchIsAlwaysBlocked() {
        assertThat(ArtifactImportDecision.blockers(review().copy(installedSignerMatches = false)))
            .contains(ArtifactImportDecision.Blocker.SIGNER_MISMATCH)
    }

    @Test

    fun installedSignerContinuityDoesNotRequireUnanchoredConsent() {
        assertThat(ArtifactImportDecision.blockers(review().copy(
            installedSignerMatches = true, userAcceptedUnknownPublisher = false
        ))).isEmpty()
    }

    @Test

    fun downgradeNeedsSeparateConsentEvenWithSignerContinuity() {
        assertThat(ArtifactImportDecision.blockers(review().copy(
            installedVersion = 43L, installedSignerMatches = true
        ))).contains(ArtifactImportDecision.Blocker.DOWNGRADE_CONSENT_REQUIRED)
        assertThat(ArtifactImportDecision.blockers(review().copy(
            installedVersion = 43L, installedSignerMatches = true,
            userApprovedDowngrade = true
        ))).isEmpty()
    }

    @Test

    fun claimedDeveloperAnchorIsNotAutomaticallyEstablished() {
        assertThat(ArtifactImportDecision.blockers(review().copy(
            installedSignerMatches = null, trustedPublisherAnchor = false,
            userAcceptedUnknownPublisher = false
        ))).contains(ArtifactImportDecision.Blocker.UNANCHORED_PUBLISHER_CONSENT_REQUIRED)
    }
}
