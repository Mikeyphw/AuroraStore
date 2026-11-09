/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.model

/**
 * R3C-03: attempt-scoped evidence for Google Play's exact-version delivery.
 *
 * This is an immutable reducer, not a network probe or a trust source. Callers must
 * check the persisted WorkManager/Room attempt before accepting or exposing a result.
 * Neither URL discovery nor receiving bytes constitutes a verified APK set.
 */
internal object PlayExactVersionOutcomePolicy {
    enum class Source {
        GOOGLE_PLAY
    }

    enum class State {
        UNKNOWN,
        REQUIRES_ACCOUNT,
        ACCESS_DENIED,
        NETWORK_OR_AUTH_FAILURE,
        DELIVERY_REJECTED_NOT_PROVEN_UNAVAILABLE,
        EXACT_VERSION_UNAVAILABLE,
        URLS_RESOLVED_NOT_VERIFIED,
        BYTES_DOWNLOADED_NOT_VERIFIED,
        VERIFIED_SET,
        SDK_INCOMPATIBLE,
        ABI_OR_SPLIT_INCOMPATIBLE,
        INSTALL_FAILED
    }

    /** A generation belongs to one exact selection and one account/session identity. */
    data class RequestKey(
        val packageName: String,
        val versionCode: Long,
        val attemptGeneration: Long,
        val accountBinding: String? = null,
        val variant: String? = null,
        val source: Source = Source.GOOGLE_PLAY
    ) {
        init {
            require(packageName.isNotBlank() && !packageName.any(Char::isWhitespace))
            require(versionCode > 0L)
            require(attemptGeneration > 0L)
            require(accountBinding?.isNotBlank() != false)
            require(variant?.isNotBlank() != false)
        }
    }

    enum class Failure {
        ACCOUNT_REQUIRED,
        ACCESS_DENIED,
        NETWORK_TIMEOUT,
        RATE_LIMITED,
        AUTHENTICATION_FAILURE,
        TEMPORARY_SERVER_ERROR,
        AMBIGUOUS_PLAY_REJECTION
    }

    /** Only a version-scoped, authoritative Play delivery refusal may use this reason. */
    enum class UnavailabilityProof {
        EXPLICIT_EXACT_VERSION_DELIVERY_REFUSAL
    }

    sealed interface Event {
        val key: RequestKey

        data class Failed(
            override val key: RequestKey,
            val reason: Failure
        ) : Event

        data class ExactVersionRefused(
            override val key: RequestKey,
            val refusedVersion: Long,
            val proof: UnavailabilityProof
        ) : Event

        data class UrlsResolved(
            override val key: RequestKey,
            val resolvedVersion: Long,
            val fileCount: Int
        ) : Event

        data class BytesDownloaded(
            override val key: RequestKey,
            val downloadedVersion: Long,
            val fileCount: Int
        ) : Event

        /** Caller must emit this only *after* R3B verifies the exact staged APK set. */
        data class R3bVerifiedSet(
            override val key: RequestKey,
            val verifiedVersion: Long,
            val verifiedFileCount: Int
        ) : Event

        /** Manifest evidence must be read from the exact verified APK, never latest listing. */
        data class VerifiedManifestSdkIncompatible(
            override val key: RequestKey,
            val manifestVersion: Long
        ) : Event

        data class VerifiedSplitOrAbiIncompatible(
            override val key: RequestKey,
            val verifiedVersion: Long
        ) : Event

        data class InstallFailed(
            override val key: RequestKey,
            val attemptedVersion: Long
        ) : Event
    }

    data class Snapshot(
        val key: RequestKey,
        val state: State,
        /** Only non-null for a verified set accepted by the strict transition. */
        val verifiedApkVersion: Long? = null,
        /** Only non-null on an authoritative exact-version refusal. */
        val unavailableVersion: Long? = null,
        val resolvedFileCount: Int = 0
    )

    /**
     * Returns null (rather than a success-like state) for a stale, foreign or invalid
     * event. A new attempt must explicitly clear any old snapshot first.
     */
    fun reduce(active: RequestKey, previous: Snapshot?, event: Event): Snapshot? {
        if (event.key != active || (previous != null && previous.key != active)) return null
        val current = previous ?: Snapshot(active, State.UNKNOWN)
        val version = active.versionCode
        return when (event) {
            is Event.Failed -> {
                val state = when (event.reason) {
                    Failure.ACCOUNT_REQUIRED -> State.REQUIRES_ACCOUNT
                    Failure.ACCESS_DENIED -> State.ACCESS_DENIED
                    Failure.AMBIGUOUS_PLAY_REJECTION ->
                        State.DELIVERY_REJECTED_NOT_PROVEN_UNAVAILABLE
                    Failure.NETWORK_TIMEOUT,
                    Failure.RATE_LIMITED,
                    Failure.AUTHENTICATION_FAILURE,
                    Failure.TEMPORARY_SERVER_ERROR -> State.NETWORK_OR_AUTH_FAILURE
                }
                Snapshot(active, state)
            }

            is Event.ExactVersionRefused -> {
                if (event.refusedVersion != version ||
                    event.proof != UnavailabilityProof.EXPLICIT_EXACT_VERSION_DELIVERY_REFUSAL ||
                    current.state == State.VERIFIED_SET
                ) {
                    null
                } else {
                    Snapshot(active, State.EXACT_VERSION_UNAVAILABLE, unavailableVersion = version)
                }
            }

            is Event.UrlsResolved -> {
                if (event.resolvedVersion != version || event.fileCount <= 0) {
                    null
                } else {
                    Snapshot(active, State.URLS_RESOLVED_NOT_VERIFIED,
                        resolvedFileCount = event.fileCount)
                }
            }

            is Event.BytesDownloaded -> {
                if (event.downloadedVersion != version ||
                    event.fileCount <= 0 ||
                    current.state != State.URLS_RESOLVED_NOT_VERIFIED ||
                    current.resolvedFileCount != event.fileCount
                ) {
                    null
                } else {
                    current.copy(state = State.BYTES_DOWNLOADED_NOT_VERIFIED)
                }
            }

            is Event.R3bVerifiedSet -> {
                if (event.verifiedVersion != version ||
                    event.verifiedFileCount <= 0 ||
                    current.state != State.BYTES_DOWNLOADED_NOT_VERIFIED ||
                    current.resolvedFileCount != event.verifiedFileCount
                ) {
                    null
                } else {
                    current.copy(state = State.VERIFIED_SET, verifiedApkVersion = version)
                }
            }

            is Event.VerifiedManifestSdkIncompatible -> {
                if (event.manifestVersion != version ||
                    current.verifiedApkVersion != version
                ) {
                    null
                } else {
                    current.copy(state = State.SDK_INCOMPATIBLE)
                }
            }

            is Event.VerifiedSplitOrAbiIncompatible -> {
                if (event.verifiedVersion != version ||
                    current.verifiedApkVersion != version
                ) {
                    null
                } else {
                    current.copy(state = State.ABI_OR_SPLIT_INCOMPATIBLE)
                }
            }

            is Event.InstallFailed -> {
                if (event.attemptedVersion != version ||
                    current.verifiedApkVersion != version
                ) {
                    null
                } else {
                    current.copy(state = State.INSTALL_FAILED)
                }
            }
        }
    }
}
