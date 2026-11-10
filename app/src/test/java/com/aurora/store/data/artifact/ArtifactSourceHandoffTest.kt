/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import com.google.common.truth.Truth.assertThat
import org.junit.Test

class ArtifactSourceHandoffTest {
    private fun parse(url: String, source: ArtifactSource, optIn: Boolean = false) =
        ArtifactSourceHandoff.parse(url, source, optIn)

    @Test
    fun officialGithubReleasePagesAccepted() {
        val source = ArtifactSource.GITHUB_RELEASE
        for (url in listOf(
            "https://github.com/owner/repo/releases",
            "https://github.com/owner/repo/releases/latest",
            "https://github.com/owner/repo/releases/tag/v1.2.3"
        )) assertThat(parse(url, source)).isNotNull()
    }

    @Test
    fun githubDoesNotAcceptArbitraryPathsOrAssets() {
        val source = ArtifactSource.GITHUB_RELEASE
        for (url in listOf(
            "https://github.com/owner/repo/issues",
            "https://github.com/owner/repo/releases/download/v1/app.apk",
            "https://github.com/owner/repo/releases/tag/v1/extra",
            "https://github.com/owner/repo/releases/tag/",
            "https://github.com/owner/repo/releases/../issues",
            "https://github.com/owner/repo/releases/%2Fother",
            "https://github.com.evil.example/owner/repo/releases",
            "https://raw.githubusercontent.com/owner/repo/releases"
        )) assertThat(parse(url, source)).isNull()
    }

    @Test
    fun apkmirrorAndFdroidOpenBrowserPagesNotDownloadProof() {
        assertThat(parse("https://www.apkmirror.com/apk/example", ArtifactSource.APKMIRROR_BROWSER_HANDOFF)).isNotNull()
        assertThat(parse("https://f-droid.org/packages/org.example", ArtifactSource.FDROID_REPOSITORY)).isNotNull()
        assertThat(parse("https://f-droid.org/en/packages/org.example", ArtifactSource.FDROID_REPOSITORY)).isNotNull()
        assertThat(parse("https://fdroid.org/packages/org.example", ArtifactSource.FDROID_REPOSITORY)).isNull()
        assertThat(parse("https://apkmirror.com.evil.example/apk/app", ArtifactSource.APKMIRROR_BROWSER_HANDOFF)).isNull()
        assertThat(parse("https://f-droid.org/login", ArtifactSource.FDROID_REPOSITORY)).isNull()
    }

    @Test
    fun apkPureBrowserHandoffRequiresFreshExplicitOptIn() {
        val url = "https://apkpure.com/app"
        assertThat(parse(url, ArtifactSource.APKPURE_OPT_IN)).isNull()
        assertThat(parse(url, ArtifactSource.APKPURE_OPT_IN, true)).isNotNull()
        assertThat(parse("https://apkpure.com.evil.example/app", ArtifactSource.APKPURE_OPT_IN, true)).isNull()
    }

    @Test
    fun unsafeSchemesAndSecretsNeverReachBrowser() {
        val source = ArtifactSource.DEVELOPER_WEBSITE
        for (url in listOf(
            "http://developer.example/releases", "file:///tmp/foo.apk",
            "https://user:secret@developer.example/file",
            "https://developer.example/file?token=x",
            "https://developer.example/file#secret",
            "https://developer.example:4443/file",
            "https://localhost/test", "https://developer.example/file\n",
            "https://developer.example/%0d%0aBad", "https://developer.example/a%2Fb",
            "https://developer.example/file\\evil",
            "https://127.0.0.1/release",
            "https://router.internal/release",
            "https://xn--fake-developer.example/releases",
            "https://app.xn--fake-developer.example/releases"
        )) assertThat(parse(url, source)).isNull()
    }

    @Test
    fun untrustedLocalDocumentCannotPretendToBeBrowserSource() {
        assertThat(parse("https://developer.example/download", ArtifactSource.LOCAL_DOCUMENT)).isNull()
    }

    @Test
    fun normalDeveloperPagesRemainUserEnteredClaims() {
        val h = parse("https://developer.example/releases", ArtifactSource.DEVELOPER_WEBSITE)
        assertThat(h).isNotNull()
        assertThat(h?.host).isEqualTo("developer.example")
    }
}
