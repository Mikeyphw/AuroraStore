/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

/** Identifies exactly one non-Play candidate and user-initiated import generation. */
internal data class ArtifactAttempt(
    val packageName: String,
    val versionCode: Long,
    val attemptGeneration: Long,
    val provenance: ArtifactProvenance
) {
    init {
        require(PACKAGE_PATTERN.matches(packageName))
        require(versionCode > 0L && attemptGeneration > 0L)
    }

    companion object {
        private val PACKAGE_PATTERN =
            Regex("[A-Za-z_][A-Za-z0-9_]*(\\.[A-Za-z_][A-Za-z0-9_]*)+")
    }
}

/**
 * C04-01 is a non-Play metadata/state boundary, NOT an APK verifier or installer.
 * In particular, staged bytes do not have VERIFIED, INSTALLABLE or PLAY status.
 */
internal object ArtifactAttemptPolicy {
    enum class Stage {
        CREATED,
        USER_SELECTED_DOCUMENT,
        PRIVATE_BYTES_STAGED_NOT_VERIFIED,
        FAILED,
        CANCELLED
    }

    sealed interface Event {
        val attempt: ArtifactAttempt

        data class DocumentSelected(override val attempt: ArtifactAttempt) : Event

        /** SHA-256 is a syntax-checked copy digest, NOT APK signing validation. */
        data class BytesStaged(
            override val attempt: ArtifactAttempt,
            val copiedSha256: String,
            val sizeBytes: Long
        ) : Event

        data class Failed(override val attempt: ArtifactAttempt) : Event
        data class Cancelled(override val attempt: ArtifactAttempt) : Event
    }

    data class Snapshot(
        val attempt: ArtifactAttempt,
        val stage: Stage,
        val stagedSha256: String? = null,
        val stagedSizeBytes: Long? = null
    )

    /** Returns null for stale generation, different origin, replay or illegal transitions. */
    fun reduce(active: ArtifactAttempt, previous: Snapshot?, event: Event): Snapshot? {
        if (event.attempt != active || (previous != null && previous.attempt != active)) {
            return null
        }
        val current = previous ?: Snapshot(active, Stage.CREATED)
        if (current.stage == Stage.FAILED || current.stage == Stage.CANCELLED) return null
        return when (event) {
            is Event.DocumentSelected -> {
                if (current.stage != Stage.CREATED) {
                    null
                } else {
                    Snapshot(active, Stage.USER_SELECTED_DOCUMENT)
                }
            }
            is Event.BytesStaged -> {
                if (current.stage != Stage.USER_SELECTED_DOCUMENT || event.sizeBytes <= 0L ||
                    !SHA256_PATTERN.matches(event.copiedSha256)
                ) {
                    null
                } else {
                    Snapshot(
                        active,
                        Stage.PRIVATE_BYTES_STAGED_NOT_VERIFIED,
                        event.copiedSha256,
                        event.sizeBytes
                    )
                }
            }
            is Event.Failed -> Snapshot(active, Stage.FAILED)
            is Event.Cancelled -> Snapshot(active, Stage.CANCELLED)
        }
    }

    private val SHA256_PATTERN = Regex("[0-9a-f]{64}")
}
