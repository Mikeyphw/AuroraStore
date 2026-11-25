/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.model

import com.aurora.store.data.model.PlayExactVersionOutcomePolicy.Event
import com.aurora.store.data.model.PlayExactVersionOutcomePolicy.Failure
import com.aurora.store.data.model.PlayExactVersionOutcomePolicy.RequestKey
import com.aurora.store.data.model.PlayExactVersionOutcomePolicy.State
import com.aurora.store.data.model.PlayExactVersionOutcomePolicy.UnavailabilityProof
import com.google.common.truth.Truth.assertThat
import org.junit.Test

class PlayExactVersionOutcomePolicyTest {
    private val key = RequestKey("org.example.safe", 42L, 1001L, "account-a", "universal")

    @Test
    fun invalidVersionOrGenerationIsRejected() {
        val version = runCatching { key.copy(versionCode = 0) }
        val generation = runCatching { key.copy(attemptGeneration = 0) }
        assertThat(version.isFailure).isTrue()
        assertThat(generation.isFailure).isTrue()
    }

    @Test
    fun emptyPackageAndAccountAreRejected() {
        assertThat(runCatching { key.copy(packageName = "  ") }.isFailure).isTrue()
        assertThat(runCatching { key.copy(accountBinding = "") }.isFailure).isTrue()
    }

    @Test
    fun staleVersionResultsAreDropped() {
        val event = Event.UrlsResolved(key.copy(versionCode = 41L), 41L, 1)
        assertThat(PlayExactVersionOutcomePolicy.reduce(key, null, event)).isNull()
    }

    @Test
    fun staleAttemptGenerationIsDropped() {
        val event = Event.Failed(key.copy(attemptGeneration = 1000L), Failure.NETWORK_TIMEOUT)
        assertThat(PlayExactVersionOutcomePolicy.reduce(key, null, event)).isNull()
    }

    @Test
    fun changedAccountAndVariantAreDropped() {
        val wrongAccount = Event.UrlsResolved(key.copy(accountBinding = "account-b"), 42, 1)
        val wrongVariant = Event.UrlsResolved(key.copy(variant = "arm64"), 42, 1)
        assertThat(PlayExactVersionOutcomePolicy.reduce(key, null, wrongAccount)).isNull()
        assertThat(PlayExactVersionOutcomePolicy.reduce(key, null, wrongVariant)).isNull()
    }

    @Test
    fun oldSnapshotCannotBeReusedForNewAttempt() {
        val old = PlayExactVersionOutcomePolicy.Snapshot(key, State.UNKNOWN)
        val newer = key.copy(attemptGeneration = 1002L)
        assertThat(
            PlayExactVersionOutcomePolicy.reduce(newer, old, Event.UrlsResolved(newer, 42, 1))
        ).isNull()
    }

    @Test
    fun timeoutNeverProvesUnavailable() {
        val result = PlayExactVersionOutcomePolicy.reduce(
            key,
            null,
            Event.Failed(key, Failure.NETWORK_TIMEOUT)
        )
        assertThat(result?.state).isEqualTo(State.NETWORK_OR_AUTH_FAILURE)
        assertThat(result?.unavailableVersion).isNull()
    }

    @Test
    fun rateLimitAndAuthErrorsNeverProveUnavailable() {
        for (reason in listOf(Failure.RATE_LIMITED, Failure.AUTHENTICATION_FAILURE)) {
            val result = PlayExactVersionOutcomePolicy.reduce(key, null, Event.Failed(key, reason))
            assertThat(result?.state).isEqualTo(State.NETWORK_OR_AUTH_FAILURE)
            assertThat(result?.unavailableVersion).isNull()
        }
    }

    @Test
    fun accountRequiredIsDistinctFromAccessDenied() {
        val required = PlayExactVersionOutcomePolicy.reduce(
            key,
            null,
            Event.Failed(key, Failure.ACCOUNT_REQUIRED)
        )
        val denied = PlayExactVersionOutcomePolicy.reduce(
            key,
            null,
            Event.Failed(key, Failure.ACCESS_DENIED)
        )
        assertThat(required?.state).isEqualTo(State.REQUIRES_ACCOUNT)
        assertThat(denied?.state).isEqualTo(State.ACCESS_DENIED)
    }

    @Test
    fun ambiguousPlayRejectionIsNotUnavailable() {
        val result = PlayExactVersionOutcomePolicy.reduce(
            key,
            null,
            Event.Failed(key, Failure.AMBIGUOUS_PLAY_REJECTION)
        )
        assertThat(result?.state).isEqualTo(State.DELIVERY_REJECTED_NOT_PROVEN_UNAVAILABLE)
    }

    @Test
    fun onlyExactVersionRefusalCreatesUnavailableEvidence() {
        val wrong = PlayExactVersionOutcomePolicy.reduce(
            key,
            null,
            Event.ExactVersionRefused(
                key,
                41L,
                UnavailabilityProof.EXPLICIT_EXACT_VERSION_DELIVERY_REFUSAL
            )
        )
        val exact = PlayExactVersionOutcomePolicy.reduce(
            key,
            null,
            Event.ExactVersionRefused(
                key,
                42L,
                UnavailabilityProof.EXPLICIT_EXACT_VERSION_DELIVERY_REFUSAL
            )
        )
        assertThat(wrong).isNull()
        assertThat(exact?.state).isEqualTo(State.EXACT_VERSION_UNAVAILABLE)
        assertThat(exact?.unavailableVersion).isEqualTo(42L)
    }

    @Test
    fun urlsAreNeverVerifiedBytes() {
        val result = PlayExactVersionOutcomePolicy.reduce(key, null, Event.UrlsResolved(key, 42, 2))
        assertThat(result?.state).isEqualTo(State.URLS_RESOLVED_NOT_VERIFIED)
        assertThat(result?.verifiedApkVersion).isNull()
    }

    @Test
    fun mismatchedUrlVersionOrEmptyListIsRejected() {
        assertThat(
            PlayExactVersionOutcomePolicy.reduce(key, null, Event.UrlsResolved(key, 43, 2))
        ).isNull()
        assertThat(
            PlayExactVersionOutcomePolicy.reduce(key, null, Event.UrlsResolved(key, 42, 0))
        ).isNull()
    }

    @Test
    fun bytesCannotSkipResolvedUrls() {
        assertThat(
            PlayExactVersionOutcomePolicy.reduce(key, null, Event.BytesDownloaded(key, 42, 2))
        ).isNull()
    }

    @Test
    fun bytesWithDifferentFileCountAreRejected() {
        val urls = PlayExactVersionOutcomePolicy.reduce(key, null, Event.UrlsResolved(key, 42, 2))
        assertThat(
            PlayExactVersionOutcomePolicy.reduce(key, urls, Event.BytesDownloaded(key, 42, 1))
        ).isNull()
    }

    @Test
    fun downloadedBytesStillAreNotVerified() {
        val urls = PlayExactVersionOutcomePolicy.reduce(key, null, Event.UrlsResolved(key, 42, 2))
        val bytes = PlayExactVersionOutcomePolicy.reduce(
            key,
            urls,
            Event.BytesDownloaded(key, 42, 2)
        )
        assertThat(bytes?.state).isEqualTo(State.BYTES_DOWNLOADED_NOT_VERIFIED)
        assertThat(bytes?.verifiedApkVersion).isNull()
    }

    @Test
    fun verificationCannotSkipDownloadOrUseOtherVersion() {
        val urls = PlayExactVersionOutcomePolicy.reduce(key, null, Event.UrlsResolved(key, 42, 2))
        val bytes = PlayExactVersionOutcomePolicy.reduce(
            key,
            urls,
            Event.BytesDownloaded(key, 42, 2)
        )
        assertThat(
            PlayExactVersionOutcomePolicy.reduce(key, null, Event.R3bVerifiedSet(key, 42, 2))
        ).isNull()
        assertThat(
            PlayExactVersionOutcomePolicy.reduce(key, bytes, Event.R3bVerifiedSet(key, 43, 2))
        ).isNull()
        assertThat(
            PlayExactVersionOutcomePolicy.reduce(key, bytes, Event.R3bVerifiedSet(key, 42, 1))
        ).isNull()
    }

    @Test
    fun verifiedSetIsOnlyReachedAfterExactSequence() {
        val urls = PlayExactVersionOutcomePolicy.reduce(key, null, Event.UrlsResolved(key, 42, 2))
        val bytes = PlayExactVersionOutcomePolicy.reduce(
            key,
            urls,
            Event.BytesDownloaded(key, 42, 2)
        )
        val verified = PlayExactVersionOutcomePolicy.reduce(
            key,
            bytes,
            Event.R3bVerifiedSet(key, 42, 2)
        )
        assertThat(verified?.state).isEqualTo(State.VERIFIED_SET)
        assertThat(verified?.verifiedApkVersion).isEqualTo(42L)
    }

    @Test
    fun manifestFailureNeedsPreviouslyVerifiedExactBytes() {
        val event = Event.VerifiedManifestSdkIncompatible(key, 42)
        assertThat(PlayExactVersionOutcomePolicy.reduce(key, null, event)).isNull()
        val urls = PlayExactVersionOutcomePolicy.reduce(key, null, Event.UrlsResolved(key, 42, 1))
        val bytes = PlayExactVersionOutcomePolicy.reduce(
            key,
            urls,
            Event.BytesDownloaded(key, 42, 1)
        )
        val verified = PlayExactVersionOutcomePolicy.reduce(
            key,
            bytes,
            Event.R3bVerifiedSet(key, 42, 1)
        )
        assertThat(PlayExactVersionOutcomePolicy.reduce(key, verified, event)?.state)
            .isEqualTo(State.SDK_INCOMPATIBLE)
    }

    @Test
    fun abiFailureNeedsVerifiedIdentity() {
        assertThat(
            PlayExactVersionOutcomePolicy.reduce(
                key,
                null,
                Event.VerifiedSplitOrAbiIncompatible(key, 42)
            )
        ).isNull()
    }

    @Test
    fun installationFailureCannotPrecedeVerification() {
        assertThat(
            PlayExactVersionOutcomePolicy.reduce(key, null, Event.InstallFailed(key, 42))
        ).isNull()
    }

    @Test
    fun refusalCannotOverrideVerifiedSet() {
        val urls = PlayExactVersionOutcomePolicy.reduce(key, null, Event.UrlsResolved(key, 42, 1))
        val bytes = PlayExactVersionOutcomePolicy.reduce(
            key,
            urls,
            Event.BytesDownloaded(key, 42, 1)
        )
        val verified = PlayExactVersionOutcomePolicy.reduce(
            key,
            bytes,
            Event.R3bVerifiedSet(key, 42, 1)
        )
        assertThat(
            PlayExactVersionOutcomePolicy.reduce(
                key,
                verified,
                Event.ExactVersionRefused(
                    key,
                    42,
                    UnavailabilityProof.EXPLICIT_EXACT_VERSION_DELIVERY_REFUSAL
                )
            )
        ).isNull()
    }
}
