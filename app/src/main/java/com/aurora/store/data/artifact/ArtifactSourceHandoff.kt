/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import java.net.URI
import java.util.Locale

/**
 * Only permits an HTTPS page to be opened in the user's external browser.
 * A URL is an untrusted *navigation hint*; neither downloading nor a publisher
 * identity is authenticated by this parser. Never fetch URLs inside the app.
 */
internal object ArtifactSourceHandoff {
    data class Handoff(val uri: URI, val source: ArtifactSource, val host: String)

    private val dnsLabel = Regex("[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
    private val repoPart = Regex("[A-Za-z0-9_.-]+")
    private val encodedControl = Regex("%(?:0[0-9a-f]|1[0-9a-f]|7f|2f|5c)", RegexOption.IGNORE_CASE)

    fun parse(raw: String, source: ArtifactSource, apkPureOptIn: Boolean): Handoff? {
        if (source == ArtifactSource.LOCAL_DOCUMENT ||
            (source == ArtifactSource.APKPURE_OPT_IN && !apkPureOptIn) ||
            raw.length !in 10..1500 || raw != raw.trim() ||
            raw.any { it.code < 0x21 || it.code > 0x7e || it == '\\' }
        ) return null
        val uri = runCatching { URI(raw) }.getOrNull() ?: return null
        if (!uri.scheme.equals("https", ignoreCase = true) || uri.isOpaque ||
            uri.rawUserInfo != null || uri.port != -1 ||
            uri.rawQuery != null || uri.rawFragment != null ||
            uri.rawAuthority.isNullOrBlank() ||
            uri.rawAuthority?.contains('%') == true ||
            encodedControl.containsMatchIn(raw)
        ) return null
        val host = uri.host?.lowercase(Locale.ROOT) ?: return null
        val labels = host.split('.')
        if (host.length !in 4..253 || labels.size < 2 ||
            labels.any { it.length > 63 || !dnsLabel.matches(it) || it.startsWith("xn--") } ||
            !labels.last().matches(Regex("[a-z]{2,63}")) ||
            host.endsWith(".local") || host.endsWith(".localhost") ||
            host.endsWith(".internal") || host.endsWith(".lan") ||
            host.endsWith(".onion")
        ) return null
        val path = uri.rawPath.orEmpty()
        if (path.contains("//") || path.split('/').any { it == "." || it == ".." } ||
            uri.normalize().rawPath != path
        ) return null
        val segments = path.split('/').filter(String::isNotBlank)
        val allowed = when (source) {
            ArtifactSource.DEVELOPER_WEBSITE -> true // user-entered, not authenticated
            ArtifactSource.GITHUB_RELEASE ->
                host == "github.com" && segments.size >= 3 &&
                    segments[0].matches(repoPart) && segments[0] !in setOf(".", "..") &&
                    segments[1].matches(repoPart) && segments[1] !in setOf(".", "..") &&
                    segments[2] == "releases" && when (segments.size) {
                        3 -> true // /owner/repo/releases
                        4 -> segments[3] == "latest"
                        5 -> segments[3] == "tag" && segments[4].isNotBlank() &&
                            !segments[4].contains('%')
                        else -> false
                    }
            ArtifactSource.APKMIRROR_BROWSER_HANDOFF ->
                host in setOf("apkmirror.com", "www.apkmirror.com") &&
                    (segments.isEmpty() || segments.first() == "apk")
            ArtifactSource.FDROID_REPOSITORY ->
                host in setOf("f-droid.org", "www.f-droid.org") &&
                    (segments.isEmpty() || segments.first() == "packages" ||
                        (segments.size >= 2 && segments[0] in setOf("en", "pt", "de", "fr", "es") &&
                            segments[1] == "packages"))
            ArtifactSource.APKPURE_OPT_IN ->
                apkPureOptIn && host in setOf("apkpure.com", "www.apkpure.com")
            ArtifactSource.LOCAL_DOCUMENT -> false
        }
        return if (allowed) Handoff(uri, source, host) else null
    }
}
