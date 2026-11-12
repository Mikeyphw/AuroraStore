/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.artifact

/**
 * R3D P02: one conservative, read-only installed-version and signer assessment.
 * Android remains the final installer authority. A downgrade may be rejected,
 * and application data cannot be guaranteed preserved by a metadata check.
 */
internal object ArtifactDowngradeSafetyPolicy {
    enum class Relation { INVALID, NOT_INSTALLED, SAME_VERSION, UPGRADE, DOWNGRADE }
    data class Assessment(
        val relation: Relation,
        val installedIdentityBlocked: Boolean,
        val separateDowngradeConsentRequired: Boolean,
        val separateDataRiskAcknowledgementRequired: Boolean = false,
        val dataPreservationGuaranteed: Boolean = false,
        val silentUninstallAllowed: Boolean = false,
        val privilegedBypassAllowed: Boolean = false
    )

    fun assess(
        candidateVersionCode: Long,
        installedVersionCode: Long?,
        installedSignerMatches: Boolean?
    ): Assessment {
        if (candidateVersionCode <= 0L ||
            (installedVersionCode == null && installedSignerMatches != null) ||
            (installedVersionCode != null && installedVersionCode <= 0L)
        ) return Assessment(Relation.INVALID, true, false)
        if (installedVersionCode == null) {
            return Assessment(Relation.NOT_INSTALLED, false, false)
        }
        val kind = when {
            candidateVersionCode < installedVersionCode -> Relation.DOWNGRADE
            candidateVersionCode == installedVersionCode -> Relation.SAME_VERSION
            else -> Relation.UPGRADE
        }
        // A historical signing certificate is not permission to replace an installed app.
        // Require positive ACTIVE signer continuity; no user checkbox can override this.
        return Assessment(
            kind, installedSignerMatches != true,
            kind == Relation.DOWNGRADE, kind == Relation.DOWNGRADE
        )
    }

    fun notice(candidateVersionCode: Long, installedVersionCode: Long?,
               installedSignerMatches: Boolean?): String {
        val status = assess(candidateVersionCode, installedVersionCode, installedSignerMatches)
        return when {
            status.installedIdentityBlocked ->
                "Installed package or signing identity cannot be confirmed. Installation is blocked. " +
                    "Historical listings and consent cannot override a signer mismatch.\n"
            status.relation == Relation.DOWNGRADE ->
                "Historical version: downgrade from installed version $installedVersionCode " +
                    "to verified version $candidateVersionCode. Back up important app data first: " +
                    "downgrading may fail or risk app data. Data preservation is NOT guaranteed. AuroraStore has NOT verified any backup. " +
                    "Separate approval is required; Android may refuse. " +
                    "No automatic uninstall, data wipe or root bypass.\n"
            status.relation == Relation.UPGRADE ->
                "Version comparison: verified update from $installedVersionCode " +
                    "to $candidateVersionCode; Android compatibility remains unconfirmed.\n"
            status.relation == Relation.SAME_VERSION ->
                "Version comparison: selected and installed version codes match; " +
                    "Android installation outcome remains unconfirmed.\n"
            status.relation == Relation.NOT_INSTALLED ->
                "Version comparison: no installed package; publisher identity is NOT authenticated.\n"
            else -> "Version comparison invalid; no installation authorization.\n"
        }
    }
}
