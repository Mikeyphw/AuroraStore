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
        DOWNGRADE_CONSENT_REQUIRED
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
        val userApprovedDowngrade: Boolean
    )

    fun blockers(review: Review): Set<Blocker> = buildSet {
        if (!Regex("[A-Za-z_][A-Za-z0-9_]*(\\.[A-Za-z_][A-Za-z0-9_]*)+")
                .matches(review.packageName) || review.versionCode <= 0L
        ) add(Blocker.INVALID_IDENTITY)
        if (!review.signerVerified) add(Blocker.UNVERIFIED_SIGNATURE)
        // Installed identity must be positively verified at the exact selection time.
        // "unknown" is not equivalent to "no installed app" and user consent cannot
        // override missing or mismatched installed signing evidence.
        if ((review.installedVersion != null && review.installedSignerMatches != true) ||
            (review.installedVersion == null && review.installedSignerMatches != null) ||
            (review.installedVersion != null && review.installedVersion <= 0L)
        ) add(Blocker.SIGNER_MISMATCH)
        if (!review.userApprovedInstall) add(Blocker.EXPLICIT_INSTALL_CONSENT_REQUIRED)
        if (review.installedSignerMatches == null && !review.trustedPublisherAnchor &&
            !review.userAcceptedUnknownPublisher
        ) add(Blocker.UNANCHORED_PUBLISHER_CONSENT_REQUIRED)
        if (review.installedVersion != null && review.installedVersion > review.versionCode &&
            !review.userApprovedDowngrade
        ) add(Blocker.DOWNGRADE_CONSENT_REQUIRED)
    }
}
