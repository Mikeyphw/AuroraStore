/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

/**
 * Browser launch attribution is only a *user-reported source claim*.
 * It must never be promoted to signing, publisher or Google Play evidence.
 */
internal object ArtifactHandoffClaimPolicy {
    private const val MAX_CLAIM_AGE_MS = 10L * 60L * 1000L

    /** Volatile UI state; never serialize raw browser URLs or document URIs. */
    data class BrowserLaunch internal constructor(
        val source: ArtifactSource,
        val host: String,
        val exactInput: String,
        val openedAtMonotonicMs: Long
    )

    fun afterSuccessfulLaunch(
        input: String, handoff: ArtifactSourceHandoff.Handoff,
        nowMonotonicMs: Long = System.nanoTime() / 1_000_000L
    ): BrowserLaunch = BrowserLaunch(handoff.source, handoff.host, input, nowMonotonicMs)

    fun selection(
        selected: ArtifactSource,
        enteredUrl: String,
        apkPureOptIn: Boolean,
        launched: BrowserLaunch?,
        untrustedFilename: String?,
        alternativeConsent: Boolean = true,
        nowMonotonicMs: Long = System.nanoTime() / 1_000_000L
    ): ArtifactProvenance {
        if (launched != null && launched.source == selected && launched.exactInput == enteredUrl &&
            (selected != ArtifactSource.APKPURE_OPT_IN || apkPureOptIn) &&
            selected != ArtifactSource.LOCAL_DOCUMENT &&
            (selected !in setOf(ArtifactSource.APKMIRROR_BROWSER_HANDOFF,
                ArtifactSource.FDROID_REPOSITORY, ArtifactSource.APKPURE_OPT_IN) ||
                alternativeConsent) &&
            nowMonotonicMs >= launched.openedAtMonotonicMs &&
            nowMonotonicMs - launched.openedAtMonotonicMs <= MAX_CLAIM_AGE_MS
        ) {
            // Only the navigation host survives; no URL, grant, token or download claim.
            return ArtifactProvenance(selected, launched.host)
        }
        return ArtifactProvenance(ArtifactSource.LOCAL_DOCUMENT, untrustedFilename)
    }
}
