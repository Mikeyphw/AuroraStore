/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import com.google.common.truth.Truth.assertThat
import org.junit.Test

class ArtifactHandoffClaimPolicyTest {
    private val git = ArtifactSource.GITHUB_RELEASE
    private val githubUrl = "https://github.com/owner/repo/releases/latest"
    private val handoff = requireNotNull(ArtifactSourceHandoff.parse(githubUrl, git, false))
    private val launched = ArtifactHandoffClaimPolicy.afterSuccessfulLaunch(githubUrl, handoff)

    @Test
    fun exactBrowserSelectionRecordsOnlyDisplayClaim() {
        val claim = ArtifactHandoffClaimPolicy.selection(git, githubUrl, false, launched, "foo.apk")
        assertThat(claim.source).isEqualTo(git)
        assertThat(claim.displayOrigin).isEqualTo("github.com")
        assertThat(claim.isVerifiedPlayDelivery).isFalse()
    }

    @Test
    fun changingSourceDropsStaleBrowserOrigin() {
        val claim = ArtifactHandoffClaimPolicy.selection(
            ArtifactSource.FDROID_REPOSITORY, githubUrl, false, launched, "foo.apk"
        )
        assertThat(claim.source).isEqualTo(ArtifactSource.LOCAL_DOCUMENT)
        assertThat(claim.displayOrigin).isEqualTo("foo.apk")
    }

    @Test
    fun editingUrlInvalidatesBrowserAttribution() {
        val claim = ArtifactHandoffClaimPolicy.selection(
            git, "https://github.com/other/repo/releases", false, launched, "foo.apk"
        )
        assertThat(claim.source).isEqualTo(ArtifactSource.LOCAL_DOCUMENT)
    }

    @Test
    fun selectingWithoutLaunchingBrowserCannotClaimPublisher() {
        val claim = ArtifactHandoffClaimPolicy.selection(git, githubUrl, false, null, "foo.apk")
        assertThat(claim.source).isEqualTo(ArtifactSource.LOCAL_DOCUMENT)
    }

    @Test
    fun apkPureOptInIsRevocableEvenAfterBrowserLaunch() {
        val url = "https://apkpure.com/app/example"
        val source = ArtifactSource.APKPURE_OPT_IN
        val checked = requireNotNull(ArtifactSourceHandoff.parse(url, source, true))
        val state = ArtifactHandoffClaimPolicy.afterSuccessfulLaunch(url, checked)
        val revoked = ArtifactHandoffClaimPolicy.selection(source, url, false, state, "download.apk")
        val enabled = ArtifactHandoffClaimPolicy.selection(source, url, true, state, "download.apk")
        assertThat(revoked.source).isEqualTo(ArtifactSource.LOCAL_DOCUMENT)
        assertThat(enabled.source).isEqualTo(source)
        assertThat(enabled.isVerifiedPlayDelivery).isFalse()
    }

    @Test
    fun userSelectedDeveloperLinkDoesNotVerifyPublisher() {
        val source = ArtifactSource.DEVELOPER_WEBSITE
        val url = "https://developer.example/releases"
        val handoff = requireNotNull(ArtifactSourceHandoff.parse(url, source, false))
        val state = ArtifactHandoffClaimPolicy.afterSuccessfulLaunch(url, handoff)
        val result = ArtifactHandoffClaimPolicy.selection(source, url, false, state, "ignored.apk")
        assertThat(result.displayOrigin).isEqualTo("developer.example")
        assertThat(result.isVerifiedPlayDelivery).isFalse()
    }

    @Test
    fun noSourceNameOrRawUriPersistsForUnattributedDocument() {
        val source = ArtifactHandoffClaimPolicy.selection(
            ArtifactSource.APKPURE_OPT_IN, "", false, null, null
        )
        assertThat(source.source).isEqualTo(ArtifactSource.LOCAL_DOCUMENT)
        assertThat(source.displayOrigin).isNull()
        assertThat(source.claimedPublisher).isNull()
    }

    @Test fun expiredBrowserHandoffCannotLabelAnUnrelatedDownload() {
        val opened = ArtifactHandoffClaimPolicy.afterSuccessfulLaunch(githubUrl, handoff, nowMonotonicMs = 1000L)
        val expired = ArtifactHandoffClaimPolicy.selection(
            git, githubUrl, false, opened, "later.apk", nowMonotonicMs = 1000L + 10L * 60L * 1000L + 1L
        )
        assertThat(expired.source).isEqualTo(ArtifactSource.LOCAL_DOCUMENT)
    }

    @Test fun futureOrClockResetBrowserClaimIsRefused() {
        val opened = ArtifactHandoffClaimPolicy.afterSuccessfulLaunch(githubUrl, handoff, nowMonotonicMs = 5000L)
        val fake = ArtifactHandoffClaimPolicy.selection(
            git, githubUrl, false, opened, "file.apk", nowMonotonicMs = 4000L
        )
        assertThat(fake.source).isEqualTo(ArtifactSource.LOCAL_DOCUMENT)
    }

    @Test fun revokedAlternativeConsentClearsProviderClaim() {
        val url = "https://apkmirror.com/apk/a/b/"
        val source = ArtifactSource.APKMIRROR_BROWSER_HANDOFF
        val page = requireNotNull(ArtifactSourceHandoff.parse(url, source, false))
        val state = ArtifactHandoffClaimPolicy.afterSuccessfulLaunch(url, page)
        val revoked = ArtifactHandoffClaimPolicy.selection(
            source, url, false, state, "app.apkm", alternativeConsent = false
        )
        assertThat(revoked.source).isEqualTo(ArtifactSource.LOCAL_DOCUMENT)
    }

}
