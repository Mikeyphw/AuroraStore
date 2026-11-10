/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

/** Distribution identity is separate from signing, publisher identity and verification. */
internal enum class ArtifactOriginFamily {
    GOOGLE_PLAY,
    DEVELOPER_RELEASE,
    GITHUB_RELEASE,
    LOCAL_IMPORT,
    APKMIRROR_BROWSER,
    FDROID_BROWSER,
    APKPURE_OPT_IN_BROWSER
}

/** Never infer any of these levels from a URL, source selector or filename. */
internal enum class ArtifactOriginAssurance {
    UNVERIFIED_SOURCE_CLAIM,
    SIGNED_APK_PUBLISHER_UNANCHORED,
    INSTALLED_CERTIFICATE_CONTINUITY,
    INDEPENDENT_PUBLISHER_VERIFIED,
    PLAY_DELIVERY_VERIFIED
}

/**
 * Intentionally not constructible by any C04 importer/browser adapter. These are
 * reserved for future independent publisher/host attestations and for R3B/C03's
 * Play receipt boundary respectively, not source-selection privileges.
 */
internal sealed class AuthenticatedArtifactOrigin protected constructor() {
    class GooglePlayVerified private constructor() : AuthenticatedArtifactOrigin()
    class OfficialDeveloperVerified private constructor() : AuthenticatedArtifactOrigin()
    class GitHubReleaseVerified private constructor() : AuthenticatedArtifactOrigin()
}

internal object ArtifactOriginBoundary {
    /** Google Play has its own R3B proof + C03 Room store; it is not an ArtifactSource. */
    fun family(source: ArtifactSource): ArtifactOriginFamily = when (source) {
        ArtifactSource.LOCAL_DOCUMENT -> ArtifactOriginFamily.LOCAL_IMPORT
        ArtifactSource.DEVELOPER_WEBSITE -> ArtifactOriginFamily.DEVELOPER_RELEASE
        ArtifactSource.GITHUB_RELEASE -> ArtifactOriginFamily.GITHUB_RELEASE
        ArtifactSource.APKMIRROR_BROWSER_HANDOFF -> ArtifactOriginFamily.APKMIRROR_BROWSER
        ArtifactSource.FDROID_REPOSITORY -> ArtifactOriginFamily.FDROID_BROWSER
        ArtifactSource.APKPURE_OPT_IN -> ArtifactOriginFamily.APKPURE_OPT_IN_BROWSER
    }

    fun claimOnly(source: ArtifactSource): ArtifactOriginAssurance {
        // Calling this on GitHub Releases or an alleged official developer host
        // can NEVER promote a browser navigation to publisher authentication.
        family(source)
        return ArtifactOriginAssurance.UNVERIFIED_SOURCE_CLAIM
    }
}

/**
 * A read-only, source-bound projection of C04-03's actual verified import.
 * Created only from a VerifiedImport, never from a browser claim or raw fields.
 * Not an OS install success, Play evidence or a verified publisher credential.
 */
internal class ArtifactIndependentEvidence private constructor(
    val attempt: ArtifactAttempt,
    val distribution: ArtifactOriginFamily,
    val selectedFileSha256: String,
    val apkSha256: List<String>,
    val signingCertificateSha256: Set<String>,
    val assurance: ArtifactOriginAssurance,
    val installedVersion: Long?,
    val signerMatchesInstalled: Boolean?
) {
    val packageName: String get() = attempt.packageName
    val versionCode: Long get() = attempt.versionCode
    val attemptGeneration: Long get() = attempt.attemptGeneration
    val provenance: ArtifactProvenance get() = attempt.provenance
    val isPlayEvidence: Boolean get() = false
    val hasPublisherAttestation: Boolean get() = false

    companion object {
        private val hex = Regex("[0-9a-f]{64}")

        /** C04-03 verifier owns cryptographic verification of the staged bytes. */
        fun fromVerifiedImport(imported: ArtifactApkVerifier.VerifiedImport): ArtifactIndependentEvidence {
            val attempt = imported.attempt
            require(attempt.attemptGeneration > 0L && attempt.versionCode > 0L)
            require(imported.staged.originalSize > 0L)
            require(hex.matches(imported.staged.originalSha256))
            val apks = imported.files
            require(apks.isNotEmpty() && apks.size == imported.splitNames.size)
            require(apks.all { it.byteCount > 0L && hex.matches(it.sha256) })
            require(apks.sumOf { it.byteCount } == imported.totalApkBytes)
            require(imported.signerSha256.isNotEmpty() && imported.signerSha256.all(hex::matches))
            require(imported.installedVersion == null || imported.installedVersion > 0L)
            require((imported.installedVersion == null) == (imported.signerMatchesInstalled == null))
            require(imported.signerMatchesInstalled != false)
            // C04 browser claims have no independently checked publisher identity.
            // A future authenticated release path requires its own proof producer.
            val assurance = when (imported.trustTier) {
                ArtifactTrustTier.INSTALLED_SIGNER_CONTINUITY -> {
                    require(imported.signerMatchesInstalled == true)
                    ArtifactOriginAssurance.INSTALLED_CERTIFICATE_CONTINUITY
                }
                ArtifactTrustTier.APK_SIGNER_VALID_PUBLISHER_UNANCHORED -> {
                    require(imported.signerMatchesInstalled != true)
                    ArtifactOriginAssurance.SIGNED_APK_PUBLISHER_UNANCHORED
                }
                else -> error("C04 cannot mint unknown or authenticated publisher evidence")
            }
            return ArtifactIndependentEvidence(
                attempt,
                ArtifactOriginBoundary.family(attempt.provenance.source),
                imported.staged.originalSha256,
                apks.map { it.sha256 }.toList(),
                imported.signerSha256.toSet(),
                assurance,
                imported.installedVersion,
                imported.signerMatchesInstalled
            )
        }
    }
}
