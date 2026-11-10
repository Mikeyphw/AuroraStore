/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

/**
 * Browser launch attribution is only a *user-reported source claim*.
 * It must never be promoted to signing, publisher or Google Play evidence.
 */
internal object ArtifactHandoffClaimPolicy {
    /** Volatile UI state; never serialize raw browser URLs or document URIs. */
    data class BrowserLaunch internal constructor(
        val source: ArtifactSource,
        val host: String,
        val exactInput: String
    )

    fun afterSuccessfulLaunch(input: String, handoff: ArtifactSourceHandoff.Handoff): BrowserLaunch =
        BrowserLaunch(handoff.source, handoff.host, input)

    fun selection(
        selected: ArtifactSource,
        enteredUrl: String,
        apkPureOptIn: Boolean,
        launched: BrowserLaunch?,
        untrustedFilename: String?
    ): ArtifactProvenance {
        if (launched != null && launched.source == selected && launched.exactInput == enteredUrl &&
            (selected != ArtifactSource.APKPURE_OPT_IN || apkPureOptIn) &&
            selected != ArtifactSource.LOCAL_DOCUMENT
        ) {
            // Only the navigation host survives; no URL, grant, token or download claim.
            return ArtifactProvenance(selected, launched.host)
        }
        return ArtifactProvenance(ArtifactSource.LOCAL_DOCUMENT, untrustedFilename)
    }
}
