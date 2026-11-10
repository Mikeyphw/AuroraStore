/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

/** ZIP names are untrusted labels. Extract to newly generated, flat private file names only. */
internal object ArtifactArchivePolicy {
    const val MAX_SOURCE_BYTES = 512L * 1024 * 1024
    const val MAX_TOTAL_APK_BYTES = 512L * 1024 * 1024
    const val MAX_APK_BYTES = 256L * 1024 * 1024
    const val MAX_ITEMS = 128
    const val MAX_APKS = 32
    const val MAX_RATIO = 150L

    enum class Format { APK, APKS, APKM, XAPK }
    enum class Entry { APK, METADATA, DIRECTORY }

    fun format(name: String): Format? = when (name.substringAfterLast('.', "").lowercase()) {
        "apk" -> Format.APK
        "apks" -> Format.APKS
        "apkm" -> Format.APKM
        "xapk" -> Format.XAPK
        else -> null
    }

    fun classify(name: String, directory: Boolean): Entry? {
        if (name.isBlank() || name.length > 240 || name.startsWith('/') ||
            name.contains('\\') || name.any(Char::isISOControl) ||
            name.split('/').any { it.isEmpty() || it == "." || it == ".." }
        ) return null
        if (directory) return Entry.DIRECTORY
        val extension = name.substringAfterLast('.', "").lowercase()
        return when (extension) {
            "apk" -> Entry.APK
            "xml", "json", "png", "jpg", "jpeg", "txt", "webp" -> Entry.METADATA
            // Bundletool APK sets carry toc.pb. Treat it as opaque checked bytes,
            // NEVER a trusted split selector or provenance claim.
            "pb" -> if (name == "toc.pb") Entry.METADATA else null
            else -> null // includes OBB, DEX, EXE, symlinks disguised as scripts
        }
    }

    fun safeSize(size: Long, compressed: Long, apk: Boolean): Boolean {
        if (size < 0 || compressed < 0 || size > if (apk) MAX_APK_BYTES else 2 * 1024 * 1024L) {
            return false
        }
        if (size > 0L && compressed == 0L) return false
        // Exact ratio comparison, without overflow from compressed * MAX_RATIO.
        if (compressed > 0L &&
            (size / compressed > MAX_RATIO ||
                (size / compressed == MAX_RATIO && size % compressed != 0L))
        ) return false
        return true
    }
}
