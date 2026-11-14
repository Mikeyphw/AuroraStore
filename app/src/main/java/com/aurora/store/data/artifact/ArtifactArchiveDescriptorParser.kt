/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.artifact

import com.aurora.store.data.installer.verification.ApkVerificationException
import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction
import org.json.JSONObject

/** Parse *bounded* untrusted package-index JSON. It can reject, never authenticate. */
internal object ArtifactArchiveDescriptorParser {
    private const val MAX_INDEX_BYTES = 64 * 1024
    private const val MAX_INDEX_ITEMS = ArtifactArchivePolicy.MAX_APKS

    fun parse(format: ArtifactArchivePolicy.Format, raw: ByteArray?):
        ArtifactArchiveDescriptorPolicy.Claim? {
        if (raw == null) return null
        if (raw.isEmpty() || raw.size > MAX_INDEX_BYTES) {
            throw ApkVerificationException("Archive index size invalid")
        }
        val content = try {
            Charsets.UTF_8.newDecoder()
                .onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT)
                .decode(ByteBuffer.wrap(raw)).toString()
        } catch (_: Exception) {
            throw ApkVerificationException("Archive metadata is not UTF-8")
        }
        val json = try { JSONObject(content) } catch (_: Exception) {
            throw ApkVerificationException("Archive metadata is not valid JSON")
        }
        val packageKey: String
        val versionKey: String
        when (format) {
            ArtifactArchivePolicy.Format.APKM -> {
                packageKey = "pname"; versionKey = "versioncode"
            }
            ArtifactArchivePolicy.Format.XAPK -> {
                packageKey = "package_name"; versionKey = "version_code"
            }
            else -> throw ApkVerificationException("Unexpected archive descriptor")
        }
        val pkg = json.optString(packageKey, "").trim()
        // Accept only an integer in decimal notation, either JSON number or string.
        val versionText = json.opt(versionKey)?.toString().orEmpty()
        if (!Regex("[1-9][0-9]{0,18}").matches(versionText)) {
            throw ApkVerificationException("Archive descriptor version is invalid")
        }
        val version = versionText.toLongOrNull()
            ?: throw ApkVerificationException("Archive descriptor version overflows")
        if (pkg.isBlank()) throw ApkVerificationException("Archive descriptor package is missing")
        if (format == ArtifactArchivePolicy.Format.XAPK &&
            json.optJSONArray("expansions")?.length()?.let { it > 0 } == true
        ) throw ApkVerificationException("XAPK OBB expansion assets require separate authorization")

        var splitIds: Map<String, String?>? = null
        if (format == ArtifactArchivePolicy.Format.XAPK && json.has("split_apks")) {
            val array = json.optJSONArray("split_apks")
                ?: throw ApkVerificationException("XAPK split index is not an array")
            if (array.length() !in 1..MAX_INDEX_ITEMS) {
                throw ApkVerificationException("XAPK split index count invalid")
            }
            val result = LinkedHashMap<String, String?>()
            for (i in 0 until array.length()) {
                val record = array.optJSONObject(i)
                    ?: throw ApkVerificationException("XAPK split index element invalid")
                val file = record.optString("file", "")
                val split = record.optString("id", "")
                if (file.isBlank() || split.isBlank() || file.startsWith('/') ||
                    '\\' in file || file.split('/').any { it.isBlank() || it == "." || it == ".." }
                ) throw ApkVerificationException("XAPK split index path invalid")
                if (result.containsKey(file)) {
                    throw ApkVerificationException("Duplicate XAPK split index path")
                }
                result[file] = if (split == "base") null else split
            }
            splitIds = result
        }
        return ArtifactArchiveDescriptorPolicy.Claim(format, pkg, version, splitIds)
    }
}
