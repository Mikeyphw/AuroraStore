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

    fun onlyOfficialGithubReleasePagesAccepted() {
        val src = ArtifactSource.GITHUB_RELEASE
        assertThat(parse("https://github.com/owner/repo/releases/tag/v1", src)).isNotNull()
        assertThat(parse("https://github.com/owner/repo/issues", src)).isNull()
        assertThat(parse("https://github.com.evil.example/owner/repo/releases", src)).isNull()
        assertThat(parse("https://raw.githubusercontent.com/owner/repo/releases", src)).isNull()
    }

    @Test

    fun mirrorAndFossHandoffsAreBrowserOnly() {
        assertThat(parse("https://www.apkmirror.com/apk/example", ArtifactSource.APKMIRROR_BROWSER_HANDOFF))
            .isNotNull()
        assertThat(parse("https://f-droid.org/packages/org.example", ArtifactSource.FDROID_REPOSITORY))
            .isNotNull()
        assertThat(parse("https://fdroid.org/packages/org.example", ArtifactSource.FDROID_REPOSITORY))
            .isNull()
    }

    @Test

    fun apkPureRequiresSeparateOptIn() {
        assertThat(parse("https://apkpure.com/app", ArtifactSource.APKPURE_OPT_IN)).isNull()
        assertThat(parse("https://apkpure.com/app", ArtifactSource.APKPURE_OPT_IN, true)).isNotNull()
    }

    @Test

    fun credentialsQueriesAndUnsecureSchemesRejected() {
        val src = ArtifactSource.DEVELOPER_WEBSITE
        for (url in listOf("http://developer.example/releases", "file:///tmp/foo.apk",
            "https://user:secret@developer.example/file", "https://developer.example/file?token=x",
            "https://developer.example/file#secret", "https://developer.example:4443/file",
            "https://localhost/test", "https://developer.example/file\n")) {
            assertThat(parse(url, src)).isNull()
        }
    }

    @Test

    fun localDocumentCannotPretendToBeBrowserProvenance() {
        assertThat(parse("https://developer.example/download", ArtifactSource.LOCAL_DOCUMENT))
            .isNull()
    }
}
