/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.installer.verification

/** Validated metadata, not an assertion that an artifact originated from Google Play. */
data class ApkIdentity(
    val name: String,
    val packageName: String,
    val versionCode: Long,
    val isBase: Boolean,
    val signerDigests: Set<String>
)

class ApkVerificationException(message: String) : IllegalStateException(message)

/** Pure contract shared by JVM tests and the Android package-archive verifier. */
object ApkSetPolicy {
    fun check(expectedPackage: String, expectedVersion: Long, entries: List<ApkIdentity>) {
        if (expectedPackage.isBlank() || expectedVersion <= 0L || entries.isEmpty()) {
            throw ApkVerificationException("No complete APK set is available for installation")
        }
        if (entries.count { it.isBase } != 1) {
            throw ApkVerificationException("APK set needs exactly one base APK")
        }
        if (entries.map { it.name }.toSet().size != entries.size) {
            throw ApkVerificationException("APK set contains duplicate split names")
        }
        val baseSigners = entries.single { it.isBase }.signerDigests
        if (baseSigners.isEmpty()) {
            throw ApkVerificationException("APK signer could not be verified")
        }
        for (entry in entries) {
            if (entry.packageName != expectedPackage) {
                throw ApkVerificationException(
                    "APK package differs from requested $expectedPackage"
                )
            }
            if (entry.versionCode != expectedVersion) {
                throw ApkVerificationException(
                    "APK version differs from requested $expectedVersion"
                )
            }
            if (entry.signerDigests.isEmpty() || entry.signerDigests != baseSigners) {
                throw ApkVerificationException("APK split certificates do not match the base APK")
            }
        }
    }

    fun compatibleInstalledSigners(
        archiveSigners: Set<String>,
        installedSigners: Set<String>,
        installedSignerHistory: Set<String>
    ): Boolean {
        if (archiveSigners.isEmpty() || installedSigners.isEmpty()) return false
        if (archiveSigners == installedSigners) return true
        // Rotation only makes sense for a single signing identity. Android is the final
        // authority on lineage capabilities, rollback and platform downgrade policy.
        return archiveSigners.size == 1 &&
            installedSigners.size == 1 &&
            archiveSigners.single() in installedSignerHistory
    }
}
