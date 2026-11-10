/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import com.aurora.store.data.installer.verification.ApkVerificationException

/** Fail-closed local-import identity contract. This is not a cryptographic verifier. */
internal object ArtifactApkIdentityPolicy {
    enum class InstalledSignerStatus { ACTIVE_MATCH, HISTORY_ONLY_UNVERIFIED, MISMATCH }

    private val packagePattern = Regex("[A-Za-z_][A-Za-z0-9_]*(\\.[A-Za-z_][A-Za-z0-9_]*)+")
    // Android feature/config split IDs may contain dots, hyphens and underscores.
    private val splitPattern = Regex("[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}")

    fun requireManifestIdentity(packageName: String, versionCode: Long, splitName: String?) {
        if (!packagePattern.matches(packageName) || versionCode <= 0L) {
            throw ApkVerificationException("Signed APK has an invalid package or version identity")
        }
        if (splitName != null && (!splitPattern.matches(splitName) ||
                splitName == "base" || splitName == "config" ||
                splitName.startsWith(".") || splitName.endsWith(".") ||
                splitName.contains("..") || splitName.contains("--")
            )) {
            throw ApkVerificationException("Signed APK has an invalid or ambiguous split identity")
        }
    }

    /** Exactly one base and unique *manifest* split IDs, not merely unique ZIP filenames. */
    fun requireUniqueSplitNames(names: List<String?>) {
        if (names.count { it == null } != 1 ||
            names.filterNotNull().distinct().size != names.size - 1
        ) throw ApkVerificationException("APK set has missing base or duplicate manifest splits")
        for (name in names.filterNotNull()) {
            if (!splitPattern.matches(name) || name.startsWith(".") ||
                name.endsWith(".") || name.contains("..") ||
                name == "base" || name == "config" || name.contains("--")
            ) throw ApkVerificationException("APK set has invalid split identity")
        }
    }

    /**
     * Cross-check the independently parsed signed manifest with Android's package
     * archive parser. The base MUST be parsed; Android may not expose a standalone
     * PackageInfo for feature/config splits, so an absent split view cannot grant
     * trust, but an available contradictory view always refuses the import.
     */
    fun requirePlatformAgreement(
        packageName: String, versionCode: Long, isBase: Boolean,
        platformPackage: String?, platformVersion: Long?
    ) {
        if ((platformPackage == null) != (platformVersion == null) ||
            (isBase && platformPackage == null)
        ) throw ApkVerificationException("Android could not confirm base APK identity")
        if (platformPackage != null &&
            (packageName != platformPackage || versionCode != platformVersion)
        ) throw ApkVerificationException("Signed manifest differs from Android archive identity")
    }

    /**
     * Presence in signingCertificateHistory is NOT by itself proof that Android
     * authorizes a rollback/upgrade. Until an audited lineage-capabilities check
     * is available, local imports require equality with the installed ACTIVE set.
     * Play/R3B policy is deliberately unchanged.
     */
    fun installedSignerStatus(
        candidate: Set<String>, installedActive: Set<String>, installedHistory: Set<String>
    ): InstalledSignerStatus {
        if (candidate.isEmpty() || installedActive.isEmpty()) return InstalledSignerStatus.MISMATCH
        if (candidate == installedActive) return InstalledSignerStatus.ACTIVE_MATCH
        return if (candidate.size == 1 && installedActive.size == 1 &&
            candidate.single() in installedHistory
        ) InstalledSignerStatus.HISTORY_ONLY_UNVERIFIED else InstalledSignerStatus.MISMATCH
    }
}
