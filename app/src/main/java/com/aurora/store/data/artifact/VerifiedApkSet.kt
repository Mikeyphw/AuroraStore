/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

/**
 * Reserved C04-03 verification capability. Intentionally unmintable in C04-01:
 * no constructor or factory is exposed to picker, provenance or source adapters.
 *
 * As of C04-03, the *actual* proof producer returns
 * ArtifactApkVerifier.VerifiedImport after Android API36 signature validation,
 * split checks and exact staged-byte revalidation; that capability is already
 * consumed by the independent PackageInstaller path. This historical type is
 * deliberately still unmintable and is NOT the production proof capability.
 * Signing validity is not anchored publisher identity; Play evidence is separate.
 */
internal class VerifiedApkSet private constructor(
    val attempt: ArtifactAttempt,
    val fileSha256: List<String>,
    val baseSignerSha256: String,
    val trustTier: ArtifactTrustTier
) {
    val isPlayEvidence: Boolean
        get() = false
}
