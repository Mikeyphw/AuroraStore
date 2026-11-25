/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.model

import com.aurora.gplayapi.PlayException
import com.google.common.truth.Truth.assertThat
import java.io.IOException
import org.junit.Test

class PlayDeliveryFailureClassifierTest {
    private fun expect(error: Throwable, failure: PlayExactVersionOutcomePolicy.Failure) {
        assertThat(PlayDeliveryFailureClassifier.classify(error)).isEqualTo(failure)
    }

    @Test
    fun accountRequiredIsNotVersionUnavailable() {
        expect(
            PlayException.RequiresAccount("download"),
            PlayExactVersionOutcomePolicy.Failure.ACCOUNT_REQUIRED
        )
    }

    @Test
    fun notPurchasedIsAccessDeniedNotVersionUnavailable() {
        expect(
            PlayException.AppNotPurchased(403),
            PlayExactVersionOutcomePolicy.Failure.ACCESS_DENIED
        )
    }

    @Test
    fun unauthorizedIsAuthenticationFailure() {
        expect(
            PlayException.Unauthorized(401),
            PlayExactVersionOutcomePolicy.Failure.AUTHENTICATION_FAILURE
        )
    }

    @Test
    fun rateLimitedIsDistinctFromNetworkFailure() {
        expect(
            PlayException.RateLimited(),
            PlayExactVersionOutcomePolicy.Failure.RATE_LIMITED
        )
    }

    @Test
    fun serverFailureIsTransientNotAbsent() {
        expect(
            PlayException.ServerError(503),
            PlayExactVersionOutcomePolicy.Failure.TEMPORARY_SERVER_ERROR
        )
    }

    @Test
    fun appNotSupportedIsNotHistoricalVersionUnavailable() {
        expect(
            PlayException.AppNotSupported(9),
            PlayExactVersionOutcomePolicy.Failure.AMBIGUOUS_PLAY_REJECTION
        )
    }

    @Test
    fun notFoundDoesNotProveThisVersionUnavailable() {
        expect(
            PlayException.NotFound(404),
            PlayExactVersionOutcomePolicy.Failure.AMBIGUOUS_PLAY_REJECTION
        )
    }

    @Test
    fun removedAppDoesNotProveExactHistoricalVersion() {
        expect(
            PlayException.AppRemoved(7),
            PlayExactVersionOutcomePolicy.Failure.AMBIGUOUS_PLAY_REJECTION
        )
    }

    @Test
    fun emptyFileListDoesNotProveExactHistoricalVersion() {
        expect(
            PlayException.NoFilesAvailable(-1),
            PlayExactVersionOutcomePolicy.Failure.AMBIGUOUS_PLAY_REJECTION
        )
    }

    @Test
    fun unknownPlayErrorDoesNotProveExactVersion() {
        expect(
            PlayException.Unknown(-1),
            PlayExactVersionOutcomePolicy.Failure.AMBIGUOUS_PLAY_REJECTION
        )
    }

    @Test
    fun networkFailureIsNeverExactVersionUnavailable() {
        expect(
            IOException("offline"),
            PlayExactVersionOutcomePolicy.Failure.NETWORK_TIMEOUT
        )
    }

    @Test
    fun unrelatedWorkerErrorsAreNotRecordedAsPlayEvidence() {
        assertThat(PlayDeliveryFailureClassifier.classify(IllegalStateException("disk")))
            .isNull()
    }
}
