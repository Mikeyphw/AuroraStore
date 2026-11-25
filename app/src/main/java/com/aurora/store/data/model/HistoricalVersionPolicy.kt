/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.model

/** Version codes are untrusted text supplied by the user or an external history report. */
internal object HistoricalVersionPolicy {
    fun parseVersionCode(value: String): Long? {
        if (value.isEmpty() || value.any { it !in '0'..'9' }) return null
        return value.toLongOrNull()?.takeIf { it > 0L }
    }

    /** Canonical decimal text prevents duplicate IDs such as 7 and 0007. */
    fun canonicalVersionCode(value: String): String? = parseVersionCode(value)?.toString()

    /** Never confirm against an app version that changed while the dialog was open. */
    fun mayConfirmDowngrade(
        requestedVersion: Long,
        confirmedInstalledVersion: Long,
        currentInstalledVersion: Long,
        input: String
    ): Boolean {
        if (!isDowngrade(requestedVersion, confirmedInstalledVersion)) return false
        if (confirmedInstalledVersion != currentInstalledVersion) return false
        return parseVersionCode(input) == requestedVersion
    }

    fun knownVersions(rawCodes: List<String>): List<Long> =
        rawCodes.mapNotNull(::parseVersionCode).distinct().sortedDescending()

    fun isDowngrade(requestedVersion: Long, installedVersion: Long): Boolean =
        requestedVersion > 0L && installedVersion > requestedVersion
}
