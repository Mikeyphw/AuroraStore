/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

/** Untrusted SAF document name is display text only; never source authentication. */
internal object ArtifactPickerPolicy {
    /** An Android ACTION_OPEN_DOCUMENT result should be an opaque content URI. */
    fun acceptsPickerScheme(scheme: String?): Boolean = scheme == "content"

    /** Never trust a provider's display name as a path or store a provider URI. */
    fun safeDocumentName(name: String?): String? = name?.takeIf {
        it.isNotBlank() && it.length <= 240 && it == it.trim() &&
            !it.any(Char::isISOControl) && !it.contains("://") && !it.contains('?') &&
            !it.contains('\\') && '/' !in it
    }

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
