/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.model

import com.aurora.gplayapi.PlayException
import java.io.IOException

/** No Play exception, including a 404, independently proves exact-version unavailability. */
internal object PlayDeliveryFailureClassifier {
    fun classify(error: Throwable): PlayExactVersionOutcomePolicy.Failure? = when (error) {
        is PlayException.RequiresAccount -> PlayExactVersionOutcomePolicy.Failure.ACCOUNT_REQUIRED
        is PlayException.AppNotPurchased -> PlayExactVersionOutcomePolicy.Failure.ACCESS_DENIED
        is PlayException.Unauthorized ->
            PlayExactVersionOutcomePolicy.Failure.AUTHENTICATION_FAILURE
        is PlayException.RateLimited -> PlayExactVersionOutcomePolicy.Failure.RATE_LIMITED
        is PlayException.ServerError ->
            PlayExactVersionOutcomePolicy.Failure.TEMPORARY_SERVER_ERROR
        is PlayException.AppNotSupported,
        is PlayException.NotFound,
        is PlayException.AppRemoved,
        is PlayException.NoFilesAvailable,
        is PlayException.Unknown ->
            PlayExactVersionOutcomePolicy.Failure.AMBIGUOUS_PLAY_REJECTION
        is PlayException -> PlayExactVersionOutcomePolicy.Failure.AMBIGUOUS_PLAY_REJECTION
        is IOException -> PlayExactVersionOutcomePolicy.Failure.NETWORK_TIMEOUT
        else -> null
    }
}
