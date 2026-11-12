/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

/** Independent, fail-closed installation consent. Never mints Google Play evidence. */
internal object ArtifactImportDecision {
    enum class Blocker {
        INVALID_IDENTITY,
        UNVERIFIED_SIGNATURE,
        SIGNER_MISMATCH,
        EXPLICIT_INSTALL_CONSENT_REQUIRED,
        UNANCHORED_PUBLISHER_CONSENT_REQUIRED,
        DOWNGRADE_CONSENT_REQUIRED,
        DOWNGRADE_DATA_LOSS_RISK_ACK_REQUIRED
    }

    data class Review(
        val packageName: String,
        val versionCode: Long,
        val signerVerified: Boolean,
        val installedSignerMatches: Boolean?,
        val installedVersion: Long?,
        val trustedPublisherAnchor: Boolean,
        val userApprovedInstall: Boolean,
        val userAcceptedUnknownPublisher: Boolean,
        val userApprovedDowngrade: Boolean,
        val userAcknowledgedDataLossRisk: Boolean = false
    )

    fun blockers(review: Review): Set<Blocker> = buildSet {
        if (!Regex("[A-Za-z_][A-Za-z0-9_]*(\\.[A-Za-z_][A-Za-z0-9_]*)+")
                .matches(review.packageName) || review.versionCode <= 0L
        ) add(Blocker.INVALID_IDENTITY)
        if (!review.signerVerified) add(Blocker.UNVERIFIED_SIGNATURE)
        // Installed identity must be positively verified at the exact selection time.
        // "unknown" is not equivalent to "no installed app" and user consent cannot
        // override missing or mismatched installed signing evidence.
        val downgradeSafety = ArtifactDowngradeSafetyPolicy.assess(
            review.versionCode, review.installedVersion, review.installedSignerMatches)
        if (downgradeSafety.installedIdentityBlocked) add(Blocker.SIGNER_MISMATCH)
        if (!review.userApprovedInstall) add(Blocker.EXPLICIT_INSTALL_CONSENT_REQUIRED)
        if (review.installedSignerMatches == null && !review.trustedPublisherAnchor &&
            !review.userAcceptedUnknownPublisher
        ) add(Blocker.UNANCHORED_PUBLISHER_CONSENT_REQUIRED)
        if (downgradeSafety.separateDowngradeConsentRequired &&
            !review.userApprovedDowngrade
        ) add(Blocker.DOWNGRADE_CONSENT_REQUIRED)
        if (downgradeSafety.separateDataRiskAcknowledgementRequired &&
            !review.userAcknowledgedDataLossRisk
        ) add(Blocker.DOWNGRADE_DATA_LOSS_RISK_ACK_REQUIRED)
    }
}
