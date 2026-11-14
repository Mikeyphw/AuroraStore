/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.artifact

import com.aurora.store.data.installer.verification.ApkVerificationException

/** Archive-side metadata is an UNTRUSTED constraint, never a source or signing proof.
 * Every reference is checked against a privately staged, cryptographically verified APK.
 * A metadata claim can only veto an import; it cannot select an APK or grant trust.
 */
internal object ArtifactArchiveDescriptorPolicy {
    data class Claim(
        val format: ArtifactArchivePolicy.Format,
        val packageName: String,
        val versionCode: Long,
        val splitIdsByEntry: Map<String, String?>? = null
    )

    private val packagePattern = Regex("[A-Za-z_][A-Za-z0-9_]*(\\.[A-Za-z_][A-Za-z0-9_]*)+")
    private val splitPattern = Regex("[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}")
    private val apkmSignatureEntries = setOf(
        "META-INF/MANIFEST.MF", "META-INF/APKMIRRO.SF", "META-INF/APKMIRRO.RSA"
    )

    /** Applied *after* the ZIP preflight's generic safe-entry classification. */
    fun allowsMetadata(format: ArtifactArchivePolicy.Format, path: String): Boolean {
        val common = setOf("icon.png", "icon.webp", "icon.jpg", "icon.jpeg")
        return when (format) {
            ArtifactArchivePolicy.Format.APK -> false
            ArtifactArchivePolicy.Format.APKS -> path == "toc.pb" ||
                (path.endsWith(".json") && path.startsWith("metadata/"))
            ArtifactArchivePolicy.Format.APKM -> path in common || path == "info.json" ||
                path == "APKM_installer.url" || path in apkmSignatureEntries
            ArtifactArchivePolicy.Format.XAPK -> path in common || path == "manifest.json"
        }
    }

    /** If any APKMirror JAR signature metadata appears, require its complete trio.
     * This checks structure, not JAR signature validity or APKMirror ownership.
     */
    fun checkMemberLayout(format: ArtifactArchivePolicy.Format, members: List<String>) {
        if (members.distinct().size != members.size) {
            throw ApkVerificationException("Duplicate archive metadata paths")
        }
        val included = members.filter { it in apkmSignatureEntries }.toSet()
        if (format == ArtifactArchivePolicy.Format.APKM && included.isNotEmpty() &&
            included != apkmSignatureEntries
        ) throw ApkVerificationException("Incomplete APKM outer signature metadata")
        if (format != ArtifactArchivePolicy.Format.APKM && included.isNotEmpty()) {
            throw ApkVerificationException("Unexpected APKM signature metadata")
        }
        for (path in members) {
            if (!allowsMetadata(format, path)) {
                throw ApkVerificationException("Unexpected metadata for archive format")
            }
        }
    }

    fun checkAgainstSignedApks(
        claim: Claim?, format: ArtifactArchivePolicy.Format,
        packageName: String, versionCode: Long,
        archiveEntryNames: List<String>, signedSplitNames: List<String?>
    ) {
        if (claim == null) return // Unsigned toc.pb never supplies a selection.
        if (claim.format != format || !packagePattern.matches(claim.packageName) ||
            claim.versionCode <= 0L || claim.packageName != packageName ||
            claim.versionCode != versionCode
        ) throw ApkVerificationException("Unsigned archive metadata contradicts signed APK identity")
        val ids = claim.splitIdsByEntry ?: return
        if (format != ArtifactArchivePolicy.Format.XAPK ||
            archiveEntryNames.size != signedSplitNames.size ||
            ids.size != archiveEntryNames.size || ids.keys != archiveEntryNames.toSet()
        ) throw ApkVerificationException("XAPK split index does not match archived APK files")
        for ((position, name) in archiveEntryNames.withIndex()) {
            val id = ids[name]
            if (id != null && (!splitPattern.matches(id) || id == "base")) {
                throw ApkVerificationException("Invalid XAPK split declaration")
            }
            if (id != signedSplitNames[position]) {
                throw ApkVerificationException("XAPK split ID contradicts signed manifest")
            }
        }
    }
}
