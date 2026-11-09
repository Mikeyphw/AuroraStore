/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

/**
 * Reserved C04-03 verification capability. Intentionally unmintable in C04-01:
 * no constructor or factory is exposed to picker, provenance or source adapters.
 *
 * The future real verifier must validate immutable private staged bytes with Android's
 * verified archive-signing API, split topology, exact package/version, and installed
 * signer continuity before it can add a tightly scoped factory here. Signing validity
 * is not an anchored developer identity; Play evidence remains a distinct subsystem.
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
