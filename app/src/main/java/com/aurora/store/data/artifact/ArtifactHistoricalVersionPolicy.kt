/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.artifact

import java.util.Locale

/**
 * R3D P01: manually discovered historical-version REFERENCES only. A version
 * listed by a user or browser is NOT signed APK metadata, availability, a
 * publisher attestation, Google Play delivery, or installation authorization.
 * No network, scraping, file I/O, persisted URLs, or privileged installer work.
 */
internal object ArtifactHistoricalVersionPolicy {
    enum class Match { NO_REFERENCE, UNVERIFIED_REFERENCE, VERIFIED_MATCH, REFUSED }
    enum class Compatibility { INCOMPATIBLE, LIMITED_PREFLIGHT_ONLY, UNKNOWN }

    data class Reference internal constructor(
        val packageName: String,
        val versionCode: Long,
        val claimedSource: ArtifactSource,
        val originLabel: String? = null
    ) {
        val availabilityConfirmed: Boolean get() = false
        val publisherAuthenticated: Boolean get() = false
        val playDeliveryVerified: Boolean get() = false
        val installationApproved: Boolean get() = false
    }

    data class Assessment(
        val match: Match,
        val claimedVersion: Long?,
        val signedVersion: Long?,
        val availabilityConfirmed: Boolean = false,
        val publisherAuthenticated: Boolean = false,
        val installationApproved: Boolean = false
    )

    /** Never infer a target from a filename, web page or unverified device profile. */
    data class DevicePreflight(
        val compatibility: Compatibility,
        val declaredMinSdk: Int?,
        val deviceSdk: Int,
        val selectedAbi: String?,
        val checkedSignedSplitLayout: Boolean,
        val finalAndroidInstallConfirmed: Boolean = false,
        val dataPreservationGuaranteed: Boolean = false
    )

    private val packagePattern = Regex("[A-Za-z_][A-Za-z0-9_]*(\\.[A-Za-z_][A-Za-z0-9_]*)+")
    private val digits = Regex("[0-9]{1,19}")

    fun validPackageName(text: String): Boolean =
        text.length <= 255 && packagePattern.matches(text)

    /** Exact decimal version code; no signs, whitespace, Unicode numerals or overflow. */
    fun parseVersion(text: String): Long? =
        if (digits.matches(text)) text.toLongOrNull()?.takeIf { it > 0L } else null

    private fun safeOrigin(label: String?): Boolean = label == null ||
        (label.isNotBlank() && label.length <= 200 && label == label.trim() &&
            label.none(Char::isISOControl) && "://" !in label && "?" !in label &&
            "#" !in label && "@" !in label && "/" !in label && "\\" !in label)

    fun reference(packageName: String, version: String, source: ArtifactSource,
                  originLabel: String? = null): Reference? {
        if (!validPackageName(packageName) || !safeOrigin(originLabel)) return null
        return Reference(packageName, parseVersion(version) ?: return null, source, originLabel)
    }

    /** No reference is not a source lookup, and no match authenticates its publisher. */
    fun compare(requested: String, signedVersion: Long?): Assessment {
        if (requested.isEmpty()) return Assessment(Match.NO_REFERENCE, null, signedVersion)
        val version = parseVersion(requested)
            ?: return Assessment(Match.REFUSED, null, signedVersion)
        if (signedVersion == null) return Assessment(Match.UNVERIFIED_REFERENCE, version, null)
        if (signedVersion <= 0L || signedVersion != version) {
            return Assessment(Match.REFUSED, version, signedVersion)
        }
        return Assessment(Match.VERIFIED_MATCH, version, signedVersion)
    }

    fun matchesVerified(requested: String, signedVersion: Long): Boolean =
        compare(requested, signedVersion).match in setOf(Match.NO_REFERENCE, Match.VERIFIED_MATCH)

    /** Optional user package claim must match the independently signed manifest exactly. */
    fun matchesVerifiedPackage(requested: String, signedPackageName: String): Boolean =
        validPackageName(signedPackageName) &&
            (requested.isEmpty() || (validPackageName(requested) && requested == signedPackageName))

    /**
     * Bounded in-memory manual shortlist. Reject mixed packages and competing
     * claims for one version instead of silently choosing a provider.
     */
    fun shortlist(packageName: String, entries: List<Reference>): List<Reference> {
        if (entries.size > 64 || !validPackageName(packageName)) return emptyList()
        if (entries.any { it.packageName != packageName }) return emptyList()
        if (entries.map { it.versionCode }.distinct().size != entries.size) return emptyList()
        return entries.sortedByDescending { it.versionCode }
    }

    /**
     * Read-only SDK/ABI preflight from a previously signature-verified private
     * APK set, never provider text. Unknown evidence stays UNKNOWN; even a pass
     * cannot predict Android policy, split targeting, sessions, or data retention.
     */
    fun preflight(declaredMinSdk: Int?, deviceSdk: Int,
                  selectedAbi: String?, deviceAbis: List<String>,
                  checkedSignedSplitLayout: Boolean): DevicePreflight {
        val minSdk = declaredMinSdk?.takeIf { it > 0 }
        val normalizedAbis = deviceAbis.map { it.lowercase(Locale.ROOT).replace('-', '_') }
        val abi = selectedAbi?.lowercase(Locale.ROOT)?.replace('-', '_')
        val result = when {
            deviceSdk <= 0 -> Compatibility.UNKNOWN
            minSdk != null && minSdk > deviceSdk -> Compatibility.INCOMPATIBLE
            !checkedSignedSplitLayout -> Compatibility.UNKNOWN
            abi != null && normalizedAbis.isNotEmpty() && abi !in normalizedAbis ->
                Compatibility.INCOMPATIBLE
            minSdk == null || (abi != null && normalizedAbis.isEmpty()) -> Compatibility.UNKNOWN
            else -> Compatibility.LIMITED_PREFLIGHT_ONLY
        }
        return DevicePreflight(result, minSdk, deviceSdk, abi, checkedSignedSplitLayout)
    }

    fun displayPreflight(result: DevicePreflight?): String = when (result?.compatibility) {
        Compatibility.INCOMPATIBLE ->
            "Read-only device compatibility: KNOWN INCOMPATIBLE (SDK or ABI). " +
                "Do not request installation; Android has final authority.\n"
        Compatibility.LIMITED_PREFLIGHT_ONLY ->
            "Read-only device compatibility: basic signed-file SDK/ABI checks passed. " +
                "Final installability and app data retention are NOT confirmed.\n"
        else -> "Read-only device compatibility: UNKNOWN or incomplete metadata. " +
            "An unverified provider listing cannot establish compatibility.\n"
    }

    fun displayReference(packageName: String, reference: Reference): String =
        if (reference.packageName != packageName) "REFUSED cross-package reference" else
            "${reference.versionCode} — ${reference.claimedSource.name} " +
                "(unverified reference; availability UNKNOWN)"
}
