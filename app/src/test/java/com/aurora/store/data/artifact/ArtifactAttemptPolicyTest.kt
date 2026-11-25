/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import com.aurora.store.data.artifact.ArtifactAttemptPolicy.Event
import com.aurora.store.data.artifact.ArtifactAttemptPolicy.Stage
import com.google.common.truth.Truth.assertThat
import org.junit.Test

class ArtifactAttemptPolicyTest {
    private val source = ArtifactProvenance(ArtifactSource.LOCAL_DOCUMENT, "download.apk")
    private val attempt = ArtifactAttempt("org.example.release", 123L, 9001L, source)

    @Test
    fun allSourcesRemainOutsideGooglePlayProof() {
        assertThat(ArtifactSource.entries.any { it.name == "GOOGLE_PLAY" }).isFalse()
        for (candidate in ArtifactSource.entries) {
            assertThat(candidate.isPlayDelivery).isFalse()
            assertThat(ArtifactProvenance(candidate).isVerifiedPlayDelivery).isFalse()
        }
    }

    @Test
    fun claimedPublisherIsNotTrustEvidence() {
        val source = ArtifactProvenance(ArtifactSource.GITHUB_RELEASE, "owner/repo", "Example Inc")
        assertThat(source.claimedPublisher).isEqualTo("Example Inc")
        assertThat(source.isVerifiedPlayDelivery).isFalse()
        assertThat(ArtifactTrustTier.UNKNOWN)
            .isNotEqualTo(ArtifactTrustTier.VERIFIED_PUBLISHER_IDENTITY)
    }

    @Test
    fun rawUrisAndSecretsAreNotStoredInLabels() {
        val unsafe = listOf(
            "content://picked/item",
            "https://site/file.apk",
            "repo?token=secret",
            "x\n"
        )
        for (label in unsafe) {
            assertThat(runCatching { source.copy(displayOrigin = label) }.isFailure).isTrue()
        }
    }

    @Test
    fun invalidPackageVersionAndGenerationAreRejected() {
        for (pkg in listOf("", "foo", "foo..bar", "bad/name", "org.example name")) {
            assertThat(runCatching { attempt.copy(packageName = pkg) }.isFailure).isTrue()
        }
        assertThat(runCatching { attempt.copy(versionCode = 0) }.isFailure).isTrue()
        assertThat(runCatching { attempt.copy(attemptGeneration = 0) }.isFailure).isTrue()
    }

    @Test
    fun byteCopyCannotSkipUserSelection() {
        val event = Event.BytesStaged(attempt, "a".repeat(64), 300)
        assertThat(ArtifactAttemptPolicy.reduce(attempt, null, event)).isNull()
    }

    @Test
    fun validSelectionThenCopyRemainsUnverified() {
        val chosen = ArtifactAttemptPolicy.reduce(attempt, null, Event.DocumentSelected(attempt))
        val staged = ArtifactAttemptPolicy.reduce(
            attempt,
            chosen,
            Event.BytesStaged(attempt, "a".repeat(64), 300)
        )
        assertThat(chosen?.stage).isEqualTo(Stage.USER_SELECTED_DOCUMENT)
        assertThat(staged?.stage).isEqualTo(Stage.PRIVATE_BYTES_STAGED_NOT_VERIFIED)
        assertThat(staged?.stagedSha256).isEqualTo("a".repeat(64))
        assertThat(staged?.stagedSizeBytes).isEqualTo(300L)
        assertThat(Stage.entries.none { it.name == "VERIFIED_SET" }).isTrue()
    }

    @Test
    fun badDigestOrEmptyCopyIsRejected() {
        val selected = ArtifactAttemptPolicy.reduce(attempt, null, Event.DocumentSelected(attempt))
        for (sha in listOf("", "A".repeat(64), "f".repeat(63), "g".repeat(64))) {
            assertThat(
                ArtifactAttemptPolicy.reduce(
                    attempt,
                    selected,
                    Event.BytesStaged(attempt, sha, 42)
                )
            ).isNull()
        }
        assertThat(
            ArtifactAttemptPolicy.reduce(
                attempt,
                selected,
                Event.BytesStaged(attempt, "a".repeat(64), 0)
            )
        ).isNull()
    }

    @Test
    fun staleGenerationsAndVersionsAreRejected() {
        val old = attempt.copy(attemptGeneration = 9000)
        val wrongVersion = attempt.copy(versionCode = 124)
        assertThat(
            ArtifactAttemptPolicy.reduce(
                attempt,
                null,
                Event.DocumentSelected(old)
            )
        ).isNull()
        assertThat(
            ArtifactAttemptPolicy.reduce(
                attempt,
                null,
                Event.DocumentSelected(wrongVersion)
            )
        ).isNull()
    }

    @Test
    fun foreignSourceCannotBorrowThisGeneration() {
        val foreign = attempt.copy(
            provenance = ArtifactProvenance(ArtifactSource.APKMIRROR_BROWSER_HANDOFF)
        )
        assertThat(
            ArtifactAttemptPolicy.reduce(
                attempt,
                null,
                Event.DocumentSelected(foreign)
            )
        ).isNull()
        val wrongSnapshot = ArtifactAttemptPolicy.Snapshot(foreign, Stage.USER_SELECTED_DOCUMENT)
        assertThat(
            ArtifactAttemptPolicy.reduce(
                attempt,
                wrongSnapshot,
                Event.DocumentSelected(attempt)
            )
        ).isNull()
    }

    @Test
    fun duplicateSelectionOrStagingCannotReplay() {
        val selected = ArtifactAttemptPolicy.reduce(attempt, null, Event.DocumentSelected(attempt))
        assertThat(
            ArtifactAttemptPolicy.reduce(
                attempt,
                selected,
                Event.DocumentSelected(attempt)
            )
        ).isNull()
        val staged = ArtifactAttemptPolicy.reduce(
            attempt,
            selected,
            Event.BytesStaged(attempt, "a".repeat(64), 300)
        )
        assertThat(
            ArtifactAttemptPolicy.reduce(
                attempt,
                staged,
                Event.BytesStaged(attempt, "b".repeat(64), 300)
            )
        ).isNull()
    }

    @Test
    fun cancellationIsTerminal() {
        val selected = ArtifactAttemptPolicy.reduce(attempt, null, Event.DocumentSelected(attempt))
        val cancelled = ArtifactAttemptPolicy.reduce(attempt, selected, Event.Cancelled(attempt))
        assertThat(cancelled?.stage).isEqualTo(Stage.CANCELLED)
        assertThat(
            ArtifactAttemptPolicy.reduce(
                attempt,
                cancelled,
                Event.DocumentSelected(attempt)
            )
        ).isNull()
        assertThat(
            ArtifactAttemptPolicy.reduce(
                attempt,
                cancelled,
                Event.BytesStaged(attempt, "a".repeat(64), 300)
            )
        ).isNull()
    }

    @Test
    fun failureIsTerminalAndNeverProvesAnything() {
        val failed = ArtifactAttemptPolicy.reduce(attempt, null, Event.Failed(attempt))
        assertThat(failed?.stage).isEqualTo(Stage.FAILED)
        assertThat(failed?.stagedSha256).isNull()
        assertThat(
            ArtifactAttemptPolicy.reduce(
                attempt,
                failed,
                Event.DocumentSelected(attempt)
            )
        ).isNull()
    }

    @Test
    fun provenanceClaimsCannotCreateAuthenticatedPlayOrGithubIdentity() {
        for (source in ArtifactSource.entries) {
            assertThat(ArtifactOriginBoundary.claimOnly(source))
                .isEqualTo(ArtifactOriginAssurance.UNVERIFIED_SOURCE_CLAIM)
            assertThat(ArtifactOriginBoundary.family(source))
                .isNotEqualTo(ArtifactOriginFamily.GOOGLE_PLAY)
        }
    }

    @Test
    fun reservedPublisherIdentityIsNotAnInstallCredential() {
        assertThat(
            AuthenticatedArtifactOrigin.OfficialDeveloperVerified::class.java.constructors
        ).isEmpty()
        assertThat(
            AuthenticatedArtifactOrigin.GitHubReleaseVerified::class.java.constructors
        ).isEmpty()
    }

    @Test
    fun noPublicVerifiedApkSetConstructorOrFactory() {
        assertThat(VerifiedApkSet::class.java.constructors).isEmpty()
        assertThat(VerifiedApkSet::class.java.methods.any { it.name.startsWith("from") }).isFalse()
    }
}
