/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.model

import com.google.common.truth.Truth.assertThat
import org.junit.Test

class HistoricalAvailabilityPolicyTest {
    private fun evidence(version: Long = 73L) = HistoricalAvailabilityPolicy.Evidence(
        requestedVersion = version,
        currentListingVersion = 80L,
        deviceSdk = 36
    )

    @Test
    fun noVersionCannotStartDelivery() {
        val result = HistoricalAvailabilityPolicy.assess(evidence(0L))
        assertThat(result.decision)
            .isEqualTo(HistoricalAvailabilityPolicy.Decision.INVALID_SELECTION)
        assertThat(result.mayAttemptExactDelivery).isFalse()
    }

    @Test
    fun exodusHistoryDoesNotProvePlayDelivery() {
        val result = HistoricalAvailabilityPolicy.assess(
            evidence().copy(historicalReportVersion = 73L)
        )
        assertThat(result.appearsInHistory).isTrue()
        assertThat(result.delivery)
            .isEqualTo(HistoricalAvailabilityPolicy.Delivery.UNKNOWN)
        assertThat(result.mayAttemptExactDelivery).isTrue()
    }

    @Test
    fun explicitVersionUnavailableRefusesTheAttempt() {
        val result = HistoricalAvailabilityPolicy.assess(
            evidence().copy(unavailableVersion = 73L)
        )
        assertThat(result.delivery)
            .isEqualTo(HistoricalAvailabilityPolicy.Delivery.UNAVAILABLE)
        assertThat(result.mayAttemptExactDelivery).isFalse()
    }

    @Test
    fun staleUnavailabilityForOtherVersionIsIgnored() {
        val result = HistoricalAvailabilityPolicy.assess(
            evidence().copy(unavailableVersion = 80L)
        )
        assertThat(result.delivery)
            .isEqualTo(HistoricalAvailabilityPolicy.Delivery.UNKNOWN)
    }

    @Test
    fun verifiedBytesMustMatchRequestedVersionExactly() {
        val exact = HistoricalAvailabilityPolicy.assess(
            evidence().copy(verifiedApkVersion = 73L)
        )
        val stale = HistoricalAvailabilityPolicy.assess(
            evidence().copy(verifiedApkVersion = 80L)
        )
        assertThat(exact.delivery)
            .isEqualTo(HistoricalAvailabilityPolicy.Delivery.VERIFIED_BYTES)
        assertThat(stale.delivery)
            .isEqualTo(HistoricalAvailabilityPolicy.Delivery.UNKNOWN)
    }

    @Test
    fun currentPlayMetadataCannotProveHistoricalCompatibility() {
        val result = HistoricalAvailabilityPolicy.assess(
            evidence().copy(manifestVersion = 80L, manifestMinSdk = 37)
        )
        assertThat(result.compatibility)
            .isEqualTo(HistoricalAvailabilityPolicy.Compatibility.UNKNOWN)
    }

    @Test
    fun exactManifestWithHigherMinSdkIsIncompatible() {
        val result = HistoricalAvailabilityPolicy.assess(
            evidence().copy(manifestVersion = 73L, manifestMinSdk = 37)
        )
        assertThat(result.compatibility)
            .isEqualTo(HistoricalAvailabilityPolicy.Compatibility.SDK_TOO_OLD)
        assertThat(result.mayAttemptExactDelivery).isFalse()
    }

    @Test
    fun exactManifestWithLowerMaxSdkIsIncompatible() {
        val result = HistoricalAvailabilityPolicy.assess(
            evidence().copy(manifestVersion = 73L, manifestMaxSdk = 35)
        )
        assertThat(result.compatibility)
            .isEqualTo(HistoricalAvailabilityPolicy.Compatibility.SDK_TOO_NEW)
        assertThat(result.mayAttemptExactDelivery).isFalse()
    }

    @Test
    fun exactSdkLimitsPassingStillDoNotProveInstallability() {
        val result = HistoricalAvailabilityPolicy.assess(
            evidence().copy(manifestVersion = 73L, manifestMinSdk = 23)
        )
        assertThat(result.compatibility)
            .isEqualTo(HistoricalAvailabilityPolicy.Compatibility.SDK_BOUNDS_PASSED)
        assertThat(result.delivery)
            .isEqualTo(HistoricalAvailabilityPolicy.Delivery.UNKNOWN)
        assertThat(result.mayAttemptExactDelivery).isTrue()
    }

    @Test
    fun missingOrNonsensicalSdkBoundsRemainUnknown() {
        val result = HistoricalAvailabilityPolicy.assess(
            evidence().copy(manifestVersion = 73L, manifestMinSdk = -10)
        )
        assertThat(result.compatibility)
            .isEqualTo(HistoricalAvailabilityPolicy.Compatibility.UNKNOWN)
    }

    @Test
    fun downgradeRequiresConsentEvenWhenBytesAreVerified() {
        val result = HistoricalAvailabilityPolicy.assess(
            evidence().copy(installedVersion = 80L, verifiedApkVersion = 73L)
        )
        assertThat(result.isDowngrade).isTrue()
        assertThat(result.decision)
            .isEqualTo(HistoricalAvailabilityPolicy.Decision.DOWNGRADE_CONSENT_REQUIRED)
    }

    @Test
    fun consentPermitsAttemptButNeverGuaranteesDowngrade() {
        val result = HistoricalAvailabilityPolicy.assess(
            evidence().copy(installedVersion = 80L, downgradeConsent = true)
        )
        assertThat(result.mayAttemptExactDelivery).isTrue()
        assertThat(result.delivery)
            .isEqualTo(HistoricalAvailabilityPolicy.Delivery.UNKNOWN)
    }

    @Test
    fun availableBytesDoNotOverrideKnownSdkIncompatibility() {
        val result = HistoricalAvailabilityPolicy.assess(
            evidence().copy(
                verifiedApkVersion = 73L,
                manifestVersion = 73L,
                manifestMinSdk = 37
            )
        )
        assertThat(result.decision)
            .isEqualTo(HistoricalAvailabilityPolicy.Decision.SDK_INCOMPATIBLE)
    }
}
