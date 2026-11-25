/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.model

/**
 * Conservative status for a historical version. A version listed by Exodus is not an APK.
 * All proof is scoped to the *exact* version code; no latest-version metadata is inherited.
 * The package manager remains the final authority on ABI, install and downgrade policy.
 */
internal object HistoricalAvailabilityPolicy {
    enum class Delivery { UNKNOWN, UNAVAILABLE, VERIFIED_BYTES }
    enum class Compatibility { UNKNOWN, SDK_BOUNDS_PASSED, SDK_TOO_OLD, SDK_TOO_NEW }
    enum class Decision {
        INVALID_SELECTION,
        UNAVAILABLE,
        SDK_INCOMPATIBLE,
        DOWNGRADE_CONSENT_REQUIRED,
        MAY_REQUEST_EXACT_DELIVERY
    }

    data class Evidence(
        val requestedVersion: Long,
        val currentListingVersion: Long,
        val installedVersion: Long = 0L,
        /** Exodus history entry, NEVER proof of delivery. */
        val historicalReportVersion: Long? = null,
        /** Only an explicit response for requestedVersion may mark unavailable. */
        val unavailableVersion: Long? = null,
        /** Only after R3B verified the exact downloaded APK set, never merely a URL. */
        val verifiedApkVersion: Long? = null,
        /** SDK limits from the requested APK's manifest, not the current Play listing. */
        val manifestVersion: Long? = null,
        val manifestMinSdk: Int? = null,
        val manifestMaxSdk: Int? = null,
        val deviceSdk: Int,
        val downgradeConsent: Boolean = false
    )

    data class Assessment(
        val delivery: Delivery,
        val compatibility: Compatibility,
        val decision: Decision,
        val isHistorical: Boolean,
        val isDowngrade: Boolean,
        val appearsInHistory: Boolean
    ) {
        /** Trying delivery does not promise a Play APK or a successful Android installation. */
        val mayAttemptExactDelivery: Boolean
            get() = decision == Decision.MAY_REQUEST_EXACT_DELIVERY
    }

    fun assess(evidence: Evidence): Assessment {
        val version = evidence.requestedVersion
        val historical = version != evidence.currentListingVersion
        val downgrade = version > 0L && evidence.installedVersion > version
        val reported = evidence.historicalReportVersion == version

        val delivery = when {
            version <= 0L -> Delivery.UNKNOWN
            evidence.unavailableVersion == version -> Delivery.UNAVAILABLE
            evidence.verifiedApkVersion == version -> Delivery.VERIFIED_BYTES
            else -> Delivery.UNKNOWN
        }

        // Stale/missing metadata is UNKNOWN. Android's installer still checks all APKs.
        val matchingManifest = evidence.manifestVersion == version && version > 0L
        val minSdk = evidence.manifestMinSdk?.takeIf { it > 0 }
        val maxSdk = evidence.manifestMaxSdk?.takeIf { it > 0 }
        val compatibility = when {
            !matchingManifest || evidence.deviceSdk <= 0 -> Compatibility.UNKNOWN
            minSdk != null && evidence.deviceSdk < minSdk -> Compatibility.SDK_TOO_OLD
            maxSdk != null && evidence.deviceSdk > maxSdk -> Compatibility.SDK_TOO_NEW
            minSdk != null || maxSdk != null -> Compatibility.SDK_BOUNDS_PASSED
            else -> Compatibility.UNKNOWN
        }

        val decision = when {
            version <= 0L -> Decision.INVALID_SELECTION
            delivery == Delivery.UNAVAILABLE -> Decision.UNAVAILABLE
            compatibility == Compatibility.SDK_TOO_OLD ||
                compatibility == Compatibility.SDK_TOO_NEW -> Decision.SDK_INCOMPATIBLE
            downgrade && !evidence.downgradeConsent -> Decision.DOWNGRADE_CONSENT_REQUIRED
            else -> Decision.MAY_REQUEST_EXACT_DELIVERY
        }
        return Assessment(delivery, compatibility, decision, historical, downgrade, reported)
    }
}
