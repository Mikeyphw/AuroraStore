/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import com.aurora.store.data.installer.verification.ApkVerificationException
import java.util.Locale

/**
 * Conservative pre-install topology filter for a *single* signed APK set.
 * This cannot replace Android PackageInstaller or authenticated bundletool
 * targeting: archives with multiple architecture/density variants are REFUSED
 * rather than installing all variants or guessing which ones to discard.
 *
 * Operates on signed manifest split IDs, never ZIP filenames or toc.pb labels.
 * The caller re-evaluates the policy immediately before session creation.
 */
internal object ArtifactSplitCompatibilityPolicy {
    private val supportedAbiTokens = setOf(
        "arm64_v8a", "armeabi_v7a", "armeabi", "x86", "x86_64", "riscv64"
    )
    private val densityTokens = setOf(
        "ldpi", "mdpi", "tvdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi", "nodpi", "anydpi"
    )
    private val localeQualifier = Regex("[a-z]{2,3}(?:_r[A-Z]{2}|_[A-Za-z]{4})?")

    data class Assessment(
        val splitCount: Int,
        val selectedAbiQualifier: String?,
        val selectedDensityQualifier: String?,
        val featureDependenciesUnverified: Boolean,
        /** Deliberately never inferred from an archive's metadata. */
        val installabilityConfirmed: Boolean = false
    )

    fun check(
        format: ArtifactArchivePolicy.Format,
        splitNames: List<String?>,
        deviceAbis: List<String>
    ): Assessment {
        if (splitNames.isEmpty() || splitNames.count { it == null } != 1 ||
            splitNames.filterNotNull().distinct().size != splitNames.size - 1
        ) throw ApkVerificationException("APK set base/split topology is ambiguous")
        if (format == ArtifactArchivePolicy.Format.APK && splitNames.size != 1) {
            throw ApkVerificationException("Standalone APK cannot contain multiple staged splits")
        }
        if (splitNames.size > ArtifactArchivePolicy.MAX_APKS) {
            throw ApkVerificationException("APK set exceeds bounded split count")
        }
        val names = splitNames.filterNotNull()
        val abi = mutableSetOf<String>()
        val densities = mutableSetOf<String>()
        var features = false
        for (name in names) {
            val separator = name.indexOf(".config.")
            val isConfig = name.startsWith("config.") || separator >= 0
            if (!isConfig) {
                // Feature split dependencies require a proper bundletool manifest
                // parser; a filename or signed split ID cannot prove completeness.
                features = true
                continue
            }
            val owner = if (separator >= 0) name.substring(0, separator) else null
            val qualifier = if (separator >= 0) name.substring(separator + 8)
                else name.removePrefix("config.")
            if (qualifier.isBlank() || qualifier.contains('.') ||
                (owner != null && (owner.isBlank() || owner !in names))
            ) throw ApkVerificationException("Split qualifier/dependency is ambiguous")
            when {
                qualifier in supportedAbiTokens -> abi.add(qualifier)
                qualifier in densityTokens -> densities.add(qualifier)
                localeQualifier.matches(qualifier) -> Unit // language assets may coexist
                else -> throw ApkVerificationException(
                    "Unqualified split targeting requires verified bundletool selection"
                )
            }
        }
        if (abi.size > 1 || densities.size > 1) {
            throw ApkVerificationException(
                "Multiple APK variant targets need an authenticated split selector"
            )
        }
        if (abi.isNotEmpty()) {
            val available = deviceAbis.map { it.lowercase(Locale.ROOT).replace('-', '_') }.toSet()
            if (available.isEmpty() || abi.single() !in available) {
                throw ApkVerificationException("APK set targets an unsupported device ABI")
            }
        }
        return Assessment(
            splitCount = names.size,
            selectedAbiQualifier = abi.singleOrNull(),
            selectedDensityQualifier = densities.singleOrNull(),
            featureDependenciesUnverified = features
        )
    }
}
