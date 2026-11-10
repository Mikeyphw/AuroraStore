/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

/** Untrusted SAF document name is display text only; never source authentication. */
internal object ArtifactPickerPolicy {
    fun safeDisplayLabel(displayName: String): String? {
        if (displayName.contains("://") || displayName.contains('?') ||
            displayName.any(Char::isISOControl)
        ) return null
        val label = displayName.substringAfterLast('/').take(150)
        return label.takeIf {
            it.isNotBlank() && it == it.trim() &&
                !it.any(Char::isISOControl) &&
                !it.contains("://") && !it.contains('?')
        }
    }
}
