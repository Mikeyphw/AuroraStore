/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

/**
 * C04-01: independent sources of candidate artifacts. None is Google Play delivery.
 * A browser handoff records where the user found a file, not who signed/published it.
 */
internal enum class ArtifactSource {
    LOCAL_DOCUMENT,
    DEVELOPER_WEBSITE,
    GITHUB_RELEASE,
    APKMIRROR_BROWSER_HANDOFF,
    FDROID_REPOSITORY,
    APKPURE_OPT_IN;

    val isPlayDelivery: Boolean
        get() = false
}

/** Claims shown to a user; never an authentication or signer-verification receipt. */
internal data class ArtifactProvenance(
    val source: ArtifactSource,
    val displayOrigin: String? = null,
    val claimedPublisher: String? = null
) {
    init {
        // Do not persist document URIs, access tokens, redirect URLs or credentials here.
        for (label in listOfNotNull(displayOrigin, claimedPublisher)) {
            require(label.isNotBlank() && label.length <= 200)
            require(label == label.trim() && !label.any(Char::isISOControl))
            require("://" !in label && "?" !in label)
        }
    }

    /** A download link, repository name or user label cannot establish Google Play proof. */
    val isVerifiedPlayDelivery: Boolean
        get() = false
}

/** Trust is assessed from signed bytes and an independent anchor, not from the source. */
internal enum class ArtifactTrustTier {
    UNKNOWN,
    APK_SIGNER_VALID_PUBLISHER_UNANCHORED,
    INSTALLED_SIGNER_CONTINUITY,
    VERIFIED_PUBLISHER_IDENTITY
}
