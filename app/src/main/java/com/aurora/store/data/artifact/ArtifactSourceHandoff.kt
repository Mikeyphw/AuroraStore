/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import java.net.URI

/** User-supplied HTTPS browser locations. Handoff NEVER proves publisher authenticity. */
internal object ArtifactSourceHandoff {
    data class Handoff(val uri: URI, val source: ArtifactSource, val host: String)

    fun parse(raw: String, source: ArtifactSource, apkPureOptIn: Boolean): Handoff? {
        if (raw.length !in 10..1500 || raw != raw.trim() || source == ArtifactSource.LOCAL_DOCUMENT) {
            return null
        }
        val uri = runCatching { URI(raw) }.getOrNull() ?: return null
        if (!uri.scheme.equals("https", true) || uri.isOpaque || uri.rawUserInfo != null ||
            uri.port != -1 || uri.rawQuery != null || uri.rawFragment != null
        ) return null
        val host = uri.host?.lowercase() ?: return null
        if (!host.matches(Regex("[a-z0-9-]+(\\.[a-z0-9-]+)+")) ||
            host.startsWith("xn--") || host.endsWith(".local") ||
            host == "localhost" || host.endsWith(".localhost")
        ) return null
        val segments = uri.path.orEmpty().split('/').filter(String::isNotBlank)
        val allowed = when (source) {
            ArtifactSource.DEVELOPER_WEBSITE -> true // Untrusted user-entered link, NOT verified publisher
            ArtifactSource.GITHUB_RELEASE ->
                host == "github.com" && segments.size >= 3 &&
                    segments[2] == "releases" &&
                    segments[0].matches(Regex("[A-Za-z0-9_.-]+")) &&
                    segments[1].matches(Regex("[A-Za-z0-9_.-]+"))
            ArtifactSource.APKMIRROR_BROWSER_HANDOFF ->
                host == "apkmirror.com" || host == "www.apkmirror.com"
            ArtifactSource.FDROID_REPOSITORY -> host == "f-droid.org" || host == "www.f-droid.org"
            ArtifactSource.APKPURE_OPT_IN -> apkPureOptIn &&
                (host == "apkpure.com" || host == "www.apkpure.com")
            ArtifactSource.LOCAL_DOCUMENT -> false
        }
        return if (allowed) Handoff(uri, source, host) else null
    }
}
