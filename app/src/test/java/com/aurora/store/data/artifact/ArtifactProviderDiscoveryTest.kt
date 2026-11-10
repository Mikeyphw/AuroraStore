/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import com.google.common.truth.Truth.assertThat
import org.junit.Test

class ArtifactProviderDiscoveryTest {
    private val policy = ArtifactProviderDiscovery
    private val play = ArtifactProviderDiscovery.Provider.GOOGLE_PLAY
    private val mirror = ArtifactProviderDiscovery.Provider.APKMIRROR
    private fun plan(
        provider: ArtifactProviderDiscovery.Provider,
        input: String = "https://apkmirror.com/apk/author/app/",
        allowed: Boolean = false,
        apkPureEnabled: Boolean = false,
        foss: Boolean = false
    ) = policy.decide(provider, input, allowed, apkPureEnabled, foss)

    @Test fun playIsNotAThirdPartyArtifactSource() {
        val result = plan(play, "org.example.demo") as ArtifactProviderDiscovery.Outcome.Ready
        assertThat(result.route).isEqualTo(ArtifactProviderDiscovery.Route.PLAY_LISTING)
        assertThat(result.url.toString()).isEqualTo("https://play.google.com/store/apps/details?id=org.example.demo")
        assertThat(result.claimedSource).isNull()
    }

    @Test fun arbitraryPlayQueryOrHostCannotBeInjected() {
        for (bad in listOf("", "demo", "org.bad?x=1", "https://play.google.com/store/apps", "org.app/evil", "org.app#x", "org..app", " org.app")) {
            assertThat(plan(play, bad) is ArtifactProviderDiscovery.Outcome.Refused).isTrue()
        }
    }

    @Test fun localPickerCarriesNoBrowserClaim() {
        val result = plan(ArtifactProviderDiscovery.Provider.LOCAL_DOCUMENT) as ArtifactProviderDiscovery.Outcome.Ready
        assertThat(result.route).isEqualTo(ArtifactProviderDiscovery.Route.NATIVE_FILE_PICKER)
        assertThat(result.url).isNull()
        assertThat(result.claimedSource).isNull()
    }

    @Test fun apkmirrorIsOnlyAnExplicitOfficialWebHandoff() {
        assertThat(plan(mirror) is ArtifactProviderDiscovery.Outcome.Refused).isTrue()
        val result = plan(mirror, allowed = true) as ArtifactProviderDiscovery.Outcome.Ready
        assertThat(result.route).isEqualTo(ArtifactProviderDiscovery.Route.EXTERNAL_PROVIDER_PAGE)
        assertThat(result.claimedSource).isEqualTo(ArtifactSource.APKMIRROR_BROWSER_HANDOFF)
        assertThat(result.url!!.host).isEqualTo("apkmirror.com")
    }

    @Test fun lookalikeApkmirrorIsAlwaysRefused() {
        assertThat(plan(mirror, "https://apkmirror.com.evil.example/apk/x", allowed = true)
            is ArtifactProviderDiscovery.Outcome.Refused).isTrue()
    }

    @Test fun githubReleasePageAcceptedWithoutPublisherAuthentication() {
        val result = plan(
            ArtifactProviderDiscovery.Provider.GITHUB_RELEASE,
            "https://github.com/org/repo/releases/latest"
        ) as ArtifactProviderDiscovery.Outcome.Ready
        assertThat(result.claimedSource).isEqualTo(ArtifactSource.GITHUB_RELEASE)
        assertThat(result.url!!.host).isEqualTo("github.com")
        assertThat(policy.status(ArtifactProviderDiscovery.Provider.GITHUB_RELEASE)).contains("not authenticated")
    }

    @Test fun githubAssetOrUntrustedHostIsRefused() {
        for (link in listOf("https://github.com/org/repo/releases/download/v1/file.apk", "https://github.com.evil.com/org/repo/releases", "http://github.com/org/repo/releases")) {
            assertThat(plan(ArtifactProviderDiscovery.Provider.GITHUB_RELEASE, link)
                is ArtifactProviderDiscovery.Outcome.Refused).isTrue()
        }
    }

    @Test fun arbitraryDeveloperHttpsPageIsOnlyAClaim() {
        val result = plan(ArtifactProviderDiscovery.Provider.DEVELOPER_WEBSITE, "https://example.org/releases") as ArtifactProviderDiscovery.Outcome.Ready
        assertThat(result.claimedSource).isEqualTo(ArtifactSource.DEVELOPER_WEBSITE)
        assertThat(policy.status(ArtifactProviderDiscovery.Provider.DEVELOPER_WEBSITE)).contains("not authenticated")
    }

    @Test fun fdroidRequiresFossAcknowledgementAndExplicitVisit() {
        val source = ArtifactProviderDiscovery.Provider.FDROID
        val url = "https://f-droid.org/en/packages/org.example.app/"
        assertThat(plan(source, url, true, foss = false) is ArtifactProviderDiscovery.Outcome.Refused).isTrue()
        assertThat(plan(source, url, false, foss = true) is ArtifactProviderDiscovery.Outcome.Refused).isTrue()
        val result = plan(source, url, true, foss = true) as ArtifactProviderDiscovery.Outcome.Ready
        assertThat(result.claimedSource).isEqualTo(ArtifactSource.FDROID_REPOSITORY)
    }

    @Test fun apkPureRequiresBothOptInAndOneVisitConsent() {
        val source = ArtifactProviderDiscovery.Provider.APKPURE
        val url = "https://apkpure.com/app/example"
        assertThat(plan(source, url, false, true) is ArtifactProviderDiscovery.Outcome.Refused).isTrue()
        assertThat(plan(source, url, true, false) is ArtifactProviderDiscovery.Outcome.Refused).isTrue()
        assertThat(plan(source, url, true, true) is ArtifactProviderDiscovery.Outcome.Ready).isTrue()
    }

    @Test fun noSourceClaimsDownloadOrSigningVerification() {
        for (provider in ArtifactProviderDiscovery.Provider.entries) {
            val status = policy.status(provider)
            assertThat(status).doesNotContain("APK verified")
            assertThat(status).doesNotContain("Download available")
        }
    }

    @Test fun noAutomaticFallbackPathExists() {
        val choices = ArtifactProviderDiscovery.Provider.entries
        assertThat(choices.size).isEqualTo(7)
        assertThat(choices.first()).isEqualTo(play)
        assertThat(choices.count { it.source == null }).isEqualTo(1)
        assertThat(choices.any { it == ArtifactProviderDiscovery.Provider.APKPURE && it.isAlternative }).isTrue()
    }
}
