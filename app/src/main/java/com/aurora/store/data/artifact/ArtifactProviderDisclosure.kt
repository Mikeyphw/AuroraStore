/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

/**
 * R3C07 P03A: the pre-import provider chooser reports independent, deliberately
 * unqualified facts. A browser navigation is not Play availability, an APK
 * signature, publisher authentication, device compatibility, or OS success.
 *
 * This projection is ONLY for the state *before a document has been selected*.
 * Verified bytes must instead use ArtifactReviewPresentation.VerifiedFacts,
 * populated by the independent verifier, never by a provider preference.
 */
internal object ArtifactProviderDisclosure {
    enum class Listing { NOT_CHECKED, NOT_APPLICABLE }
    enum class Availability { UNKNOWN }
    enum class DownloadedBytes { NOT_SELECTED }
    enum class Signature { NOT_VERIFIED }
    enum class Publisher { NOT_AUTHENTICATED }
    enum class Compatibility { NOT_ASSESSED }
    enum class InstallResult { NOT_REQUESTED }

    data class BeforeSelection(
        val listing: Listing,
        val availability: Availability,
        val downloadedBytes: DownloadedBytes,
        val signature: Signature,
        val publisher: Publisher,
        val compatibility: Compatibility,
        val installResult: InstallResult
    )

    fun beforeSelection(provider: ArtifactProviderDiscovery.Provider): BeforeSelection =
        BeforeSelection(
            listing = if (provider == ArtifactProviderDiscovery.Provider.LOCAL_DOCUMENT) {
                Listing.NOT_APPLICABLE
            } else {
                Listing.NOT_CHECKED
            },
            availability = Availability.UNKNOWN,
            downloadedBytes = DownloadedBytes.NOT_SELECTED,
            signature = Signature.NOT_VERIFIED,
            publisher = Publisher.NOT_AUTHENTICATED,
            compatibility = Compatibility.NOT_ASSESSED,
            installResult = InstallResult.NOT_REQUESTED
        )

    fun summary(provider: ArtifactProviderDiscovery.Provider): String {
        val facts = beforeSelection(provider)
        val listing = when (facts.listing) {
            Listing.NOT_APPLICABLE -> "No provider listing for local files"
            Listing.NOT_CHECKED -> "Provider listing: NOT CHECKED by Aurora"
        }
        return buildString {
            append("$listing\n")
            append("Exact-version availability: ${facts.availability}\n")
            append("Downloaded bytes: NOT SELECTED; APK signature: NOT VERIFIED\n")
            append("Publisher identity: not authenticated\n")
            append("Device compatibility: NOT ASSESSED\n")
            append("Android install result: NOT REQUESTED")
        }
    }
}
