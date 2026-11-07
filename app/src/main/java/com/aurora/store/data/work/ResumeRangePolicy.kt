/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.work

/** Full HTTP Content-Range validation shared by production and emulator acceptance. */
internal object ResumeRangePolicy {
    private val pattern = Regex("""bytes (\d+)-(\d+)/(\d+|\*)""")

    fun matches(contentRange: String?, expectedStart: Long): Boolean {
        if (expectedStart < 0L) return false
        val groups = pattern.matchEntire(contentRange?.trim().orEmpty()) ?: return false
        val start = groups.groupValues[1].toLongOrNull() ?: return false
        val end = groups.groupValues[2].toLongOrNull() ?: return false
        val totalText = groups.groupValues[3]
        val total = if (totalText == "*") null else totalText.toLongOrNull() ?: return false
        return start == expectedStart && end >= start &&
            (total == null || (total > 0L && end < total))
    }

    fun requiresRestart(statusCode: Int, existingBytes: Long): Boolean =
        statusCode == 416 && existingBytes > 0L
}
