/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import com.google.common.truth.Truth.assertThat
import java.io.FileNotFoundException
import java.io.IOException
import org.junit.Test

class ArtifactImportJourneyTest {
    @Test fun noRequestedVersionDoesNotInventProviderAvailability() {
        assertThat(ArtifactImportJourney.versionMatches("", 123L)).isTrue()
        assertThat(ArtifactImportJourney.providerHandoffMessage(
            ArtifactProviderDiscovery.Provider.GOOGLE_PLAY)).contains("UNKNOWN")
    }

    @Test fun exactRequestedVersionAllowsOnlyMatchingVerifiedVersion() {
        assertThat(ArtifactImportJourney.versionMatches("123", 123L)).isTrue()
        assertThat(ArtifactImportJourney.versionMatches("123", 124L)).isFalse()
        assertThat(ArtifactImportJourney.versionMessage("123", 124L))
            .contains("No installation approval")
    }

    @Test fun invalidReferenceAndOverflowFailClosed() {
        for (bad in listOf("0", "-1", "1.0", "+1", "abc", " 5", "9223372036854775808",
            "999999999999999999999")) {
            assertThat(ArtifactImportJourney.versionMatches(bad, 5L)).isFalse()
        }
    }

    @Test fun revokedPermissionIsSafeAndDoesNotLeakRawUri() {
        val message = ArtifactImportJourney.failureMessage(
            SecurityException("content://secret.example/id/token"))
        assertThat(message).contains("denied access")
        assertThat(message).doesNotContain("secret.example")
    }

    @Test fun missingProviderFileIsRetryableWithoutAutomaticFallback() {
        val message = ArtifactImportJourney.failureMessage(FileNotFoundException("sensitive.apk"))
        assertThat(message).contains("no longer available")
        assertThat(message).contains("no automatic provider fallback")
        assertThat(message).doesNotContain("sensitive.apk")
    }

    @Test fun ioAndMalformedFilesNeverShowAndroidSuccess() {
        for (error in listOf(IOException("network secret"), IllegalStateException("raw error"),
            RuntimeException("raw error"))) {
            val message = ArtifactImportJourney.failureMessage(error)
            assertThat(message).contains("Nothing installed")
            assertThat(message).doesNotContain("SUCCESS")
            assertThat(message).doesNotContain("raw error")
        }
    }

    @Test fun allSevenProvidersHaveManualProvenanceDisclosures() {
        for (provider in ArtifactProviderDiscovery.Provider.entries) {
            val message = ArtifactImportJourney.providerHandoffMessage(provider)
            assertThat(message).doesNotContain("APK verified")
            assertThat(message).doesNotContain("publisher authenticated")
            assertThat(message).doesNotContain("installation SUCCESS")
        }
        assertThat(ArtifactImportJourney.retryMessage()).contains("not reused")
    }
}
