/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import com.google.common.truth.Truth.assertThat
import org.junit.Test

class ArtifactProviderDisclosureTest {
    private val providers = ArtifactProviderDiscovery.Provider.entries

    @Test fun everyProviderReportsUnknownExactVersion() {
        for (provider in providers) {
            val facts = ArtifactProviderDisclosure.beforeSelection(provider)
            assertThat(facts.availability).isEqualTo(ArtifactProviderDisclosure.Availability.UNKNOWN)
            assertThat(facts.downloadedBytes).isEqualTo(ArtifactProviderDisclosure.DownloadedBytes.NOT_SELECTED)
        }
    }

    @Test fun noBrowserHandoffMintsSigningPublisherOrInstallEvidence() {
        for (provider in providers) {
            val facts = ArtifactProviderDisclosure.beforeSelection(provider)
            assertThat(facts.signature).isEqualTo(ArtifactProviderDisclosure.Signature.NOT_VERIFIED)
            assertThat(facts.publisher).isEqualTo(ArtifactProviderDisclosure.Publisher.NOT_AUTHENTICATED)
            assertThat(facts.compatibility).isEqualTo(ArtifactProviderDisclosure.Compatibility.NOT_ASSESSED)
            assertThat(facts.installResult).isEqualTo(ArtifactProviderDisclosure.InstallResult.NOT_REQUESTED)
        }
    }

    @Test fun onlyLocalPickerHasNoProviderListing() {
        val local = ArtifactProviderDiscovery.Provider.LOCAL_DOCUMENT
        assertThat(ArtifactProviderDisclosure.beforeSelection(local).listing)
            .isEqualTo(ArtifactProviderDisclosure.Listing.NOT_APPLICABLE)
        for (provider in providers.filter { it != local }) {
            assertThat(ArtifactProviderDisclosure.beforeSelection(provider).listing)
                .isEqualTo(ArtifactProviderDisclosure.Listing.NOT_CHECKED)
        }
    }

    @Test fun settingsVisibleStatusesDoNotClaimAvailabilityOrAuthenticatedPublisher() {
        for (provider in providers) {
            val label = ArtifactProviderDiscovery.status(provider)
            assertThat(label).contains("Exact-version availability: UNKNOWN")
            assertThat(label).contains("APK signature: NOT VERIFIED")
            assertThat(label).contains("Publisher identity: not authenticated")
            assertThat(label).contains("Android install result: NOT REQUESTED")
            assertThat(label).doesNotContain("Download available")
            assertThat(label).doesNotContain("APK verified")
            assertThat(label).doesNotContain("Android reported installation SUCCESS")
        }
    }

    @Test fun optionalApkPureRemainsDisabledWithoutPreference() {
        val pure = ArtifactProviderDiscovery.Provider.APKPURE
        assertThat(ArtifactProviderDiscovery.status(pure)).contains("disabled by default")
        assertThat(ArtifactProviderDiscovery.decide(pure, "https://apkpure.com/app/demo", true, false, true)
            is ArtifactProviderDiscovery.Outcome.Refused).isTrue()
    }
}
