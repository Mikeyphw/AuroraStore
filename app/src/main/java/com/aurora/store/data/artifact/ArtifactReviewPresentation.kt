/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

/** Only formats already verified facts. It does not authenticate a provider or signer. */
internal object ArtifactReviewPresentation {
    data class VerifiedFacts(
        val provenance: ArtifactProvenance,
        val attemptGeneration: Long,
        val apkSha256: List<String>,
        val packageName: String,
        val versionCode: Long,
        val fileCount: Int,
        val totalApkBytes: Long,
        val sourceSha256: String,
        val signerSha256: Set<String>,
        val installedVersion: Long?,
        val signerMatchesInstalled: Boolean?,
        val trustTier: ArtifactTrustTier
    )

    fun source(provenance: ArtifactProvenance): String {
        val label = when (provenance.source) {
            ArtifactSource.LOCAL_DOCUMENT -> "Local file chosen with Android picker"
            ArtifactSource.DEVELOPER_WEBSITE -> "Developer website (browser claim)"
            ArtifactSource.GITHUB_RELEASE -> "GitHub Releases (browser claim)"
            ArtifactSource.APKMIRROR_BROWSER_HANDOFF -> "APKMirror (browser claim)"
            ArtifactSource.FDROID_REPOSITORY -> "F-Droid (browser claim)"
            ArtifactSource.APKPURE_OPT_IN -> "APKPure (opt-in browser claim)"
        }
        val origin = provenance.displayOrigin?.takeIf { it.isNotBlank() }
        // Origin is a *label* or browser host, never proof that the selected bytes
        // were downloaded from that host. No raw URL/document URI is displayed.
        return if (origin == null) label else "$label — unverified reference: $origin"
    }

    fun trust(facts: VerifiedFacts): String = when {
        facts.installedVersion != null && facts.signerMatchesInstalled == true ->
            "Installed signing identity matches; this does not independently prove who published the file"
        facts.installedVersion != null ->
            "Installed signing identity is not confirmed — installation must be blocked"
        facts.trustTier == ArtifactTrustTier.VERIFIED_PUBLISHER_IDENTITY ->
            "Publisher attestation unavailable in C04 — cannot treat this flag as proof"
        else -> "APK signature valid; developer/publisher identity NOT independently verified"
    }

    fun verification(f: VerifiedFacts): String = buildString {
        append("VERIFIED APK FILES — NOT INSTALLED\n")
        append("Source: ${source(f.provenance)}\n")
        append("Distribution: ${ArtifactOriginBoundary.family(f.provenance.source)} (independent of Play)\n")
        append("Source assurance: user/browser claim only; no Play or publisher proof\n")
        append("Attempt generation: ${f.attemptGeneration}\n")
        append("Package: ${f.packageName}\nVersion code: ${f.versionCode}\n")
        append("Files: ${f.fileCount} APK(s); ${f.totalApkBytes} verified APK bytes\n")
        append("Original selected file SHA-256: ${f.sourceSha256}\n")
        append("Independently verified APK file SHA-256:\n")
        f.apkSha256.forEachIndexed { index, hash -> append("  #${index + 1}: $hash\n") }
        append("APK signing certificate SHA-256:\n")
        f.signerSha256.sorted().forEach { append("  $it\n") }
        append("Trust: ${trust(f)}\n")
        append("Installed version: ${f.installedVersion?.toString() ?: "Not installed"}\n")
        append("Signer continuity: ${when (f.signerMatchesInstalled) {
            true -> "Matches installed signing identity"
            false -> "MISMATCH — blocked"
            null -> "No installed version to compare"
        }}\n")
        if (f.installedVersion != null && f.installedVersion > f.versionCode) {
            append("Downgrade: requested version is older. Separate approval required; Android may refuse.\n")
        }
        append("Final device/split compatibility and installation outcome are decided by Android.")
    }

    // No C04 origin currently carries authenticated publisher proof, regardless of
    // a caller-supplied trust enum. Keep presentation aligned with install blocker.
    fun consentNeedsUnknownPublisher(f: VerifiedFacts): Boolean = f.installedVersion == null

    fun consentNeedsDowngrade(f: VerifiedFacts): Boolean =
        f.installedVersion != null && f.installedVersion > f.versionCode

    fun blockerDescription(blockers: Set<ArtifactImportDecision.Blocker>): String =
        if (blockers.isEmpty()) "All required confirmations selected. Android will still review the install."
        else blockers.map {
            when (it) {
                ArtifactImportDecision.Blocker.INVALID_IDENTITY -> "Invalid package/version — blocked"
                ArtifactImportDecision.Blocker.UNVERIFIED_SIGNATURE -> "Unverified APK signature — blocked"
                ArtifactImportDecision.Blocker.SIGNER_MISMATCH -> "Installed signer mismatch/unknown — blocked"
                ArtifactImportDecision.Blocker.EXPLICIT_INSTALL_CONSENT_REQUIRED -> "Approve installation"
                ArtifactImportDecision.Blocker.UNANCHORED_PUBLISHER_CONSENT_REQUIRED -> "Acknowledge unverified publisher"
                ArtifactImportDecision.Blocker.DOWNGRADE_CONSENT_REQUIRED -> "Approve version downgrade separately"
            }
        }.joinToString(" · ")

    /** State originates only from private per-session receipts updated by Android callbacks. */
    fun androidResult(state: ArtifactSessionReceiptPolicy.State?): String = when (state) {
        null -> "No authenticated Android install outcome available"
        ArtifactSessionReceiptPolicy.State.AWAITING_ANDROID ->
            "Request submitted; waiting for Android. Installation NOT confirmed"
        ArtifactSessionReceiptPolicy.State.AWAITING_USER_APPROVAL ->
            "Android requires system approval. Installation NOT confirmed"
        ArtifactSessionReceiptPolicy.State.APPROVAL_UI_UNAVAILABLE ->
            "Android approval prompt could not be shown. Installation NOT confirmed"
        ArtifactSessionReceiptPolicy.State.INSTALLED_BY_ANDROID ->
            "Android reported installation SUCCESS"
        ArtifactSessionReceiptPolicy.State.ANDROID_REJECTED ->
            "Android reported installation REJECTED"
    }

    fun androidFailureReason(code: Int): String = when (code) {
        1 -> "General Android installer failure"
        2 -> "Android policy blocked the install"
        3 -> "Installation aborted"
        4 -> "Android rejected invalid APK data"
        5 -> "Package conflict"
        6 -> "Insufficient storage"
        7 -> "Incompatible with this device"
        else -> "Unknown Android failure"
    }
}
