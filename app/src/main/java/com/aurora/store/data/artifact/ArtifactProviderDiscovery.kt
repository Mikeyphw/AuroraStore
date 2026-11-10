/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import java.net.URI

/**
 * R3C-05 source discovery is an explicit user-directed *navigation*, never a download
 * API, publisher attestation, Play receipt, or installation permission.
 *
 * An authenticated developer/release capability cannot be minted by this model:
 * the current app has no independent developer-origin attestations. Even HTTPS and
 * a valid GitHub Releases page are NOT proof of the APK's publisher.
 */
internal object ArtifactProviderDiscovery {
    enum class Provider(
        val title: String,
        val explanation: String,
        val source: ArtifactSource?
    ) {
        GOOGLE_PLAY(
            "Google Play (separate official listing)",
            "Open the exact package listing in Google Play. This does not prove that " +
                "a historical version is available, or produce a Play verification receipt.", null
        ),
        LOCAL_DOCUMENT(
            "Local APK or bundle (Android document picker)",
            "Choose an APK/APKS/APKM/XAPK with Android's file picker. Local files never inherit Play verification.",
            ArtifactSource.LOCAL_DOCUMENT
        ),
        DEVELOPER_WEBSITE(
            "Developer website (identity unverified)",
            "Open a user-supplied HTTPS page. No developer identity or publisher signing key is authenticated.",
            ArtifactSource.DEVELOPER_WEBSITE
        ),
        GITHUB_RELEASE(
            "GitHub Releases (identity unverified)",
            "Only GitHub release pages are allowed. The account or release is not authenticated as the app's developer.",
            ArtifactSource.GITHUB_RELEASE
        ),
        APKMIRROR(
            "APKMirror (browser only, manual consent)",
            "Official site handoff only: no scraping, automatic download or APKMirror signature trust.",
            ArtifactSource.APKMIRROR_BROWSER_HANDOFF
        ),
        FDROID(
            "F-Droid (FOSS only, signing may differ)",
            "Use only for a FOSS app you are entitled to obtain. F-Droid may re-sign builds; installed signer checks still apply.",
            ArtifactSource.FDROID_REPOSITORY
        ),
        APKPURE(
            "APKPure (opt-in disabled by default)",
            "Secondary browser handoff; requires prior opt-in and this attempt's consent. No protected downloads or XAPK bypass.",
            ArtifactSource.APKPURE_OPT_IN
        );

        val isAlternative: Boolean get() = this in setOf(APKMIRROR, FDROID, APKPURE)
    }

    enum class Route { NATIVE_FILE_PICKER, PLAY_LISTING, EXTERNAL_PROVIDER_PAGE }
    sealed interface Outcome {
        data class Ready(
            val route: Route,
            val url: URI? = null,
            val claimedSource: ArtifactSource? = null
        ) : Outcome
        data class Refused(val explanation: String) : Outcome
    }

    private val packageName = Regex("[A-Za-z_][A-Za-z0-9_]*(\\.[A-Za-z_][A-Za-z0-9_]*)+")

    /**
     * No network call, no server availability or provenance claim. The caller must
     * make a separate, explicit browser launch and import via the system picker.
     */
    fun decide(
        provider: Provider,
        userInput: String,
        allowAlternativeThisTime: Boolean,
        apkPureEnabled: Boolean,
        fossEligibilityAcknowledged: Boolean
    ): Outcome {
        if (provider == Provider.LOCAL_DOCUMENT) {
            return Outcome.Ready(Route.NATIVE_FILE_PICKER)
        }
        if (provider == Provider.GOOGLE_PLAY) {
            if (!packageName.matches(userInput) || userInput.length > 255) {
                return Outcome.Refused("Enter an exact package ID for Google Play (for example, org.example.app).")
            }
            // A Play listing is NOT a URL offered as a non-Play artifact source.
            return Outcome.Ready(
                Route.PLAY_LISTING,
                URI("https://play.google.com/store/apps/details?id=$userInput")
            )
        }
        if (provider.isAlternative && !allowAlternativeThisTime) {
            return Outcome.Refused("Approve this alternative provider for this browser visit first.")
        }
        if (provider == Provider.APKPURE && !apkPureEnabled) {
            return Outcome.Refused("APKPure is disabled; enable its optional setting first.")
        }
        if (provider == Provider.FDROID && !fossEligibilityAcknowledged) {
            return Outcome.Refused("Confirm that this is an appropriate FOSS app and that signing can differ.")
        }
        val source = provider.source ?: return Outcome.Refused("Unknown provider")
        val handoff = ArtifactSourceHandoff.parse(userInput, source, apkPureEnabled)
            ?: return Outcome.Refused("Enter an allowed HTTPS provider page. Links are not verified publisher proof.")
        return Outcome.Ready(Route.EXTERNAL_PROVIDER_PAGE, handoff.uri, source)
    }

    /** Explicit statuses. No UNKNOWN condition may be displayed as positive availability. */
    fun status(provider: Provider): String = when (provider) {
        Provider.GOOGLE_PLAY -> "Google Play listing only; exact-version availability is UNKNOWN here"
        Provider.LOCAL_DOCUMENT -> "Local file not selected or verified"
        Provider.DEVELOPER_WEBSITE, Provider.GITHUB_RELEASE ->
            "Publisher not authenticated; open a page manually and verify the downloaded APK"
        Provider.APKMIRROR -> "Listing not checked; official browser handoff only"
        Provider.FDROID -> "FOSS eligibility not independently verified; APK signer may differ"
        Provider.APKPURE -> "Optional provider; disabled by default, no availability assertion"
    }
}
