/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import java.io.FileNotFoundException
import java.io.IOException

/**
 * R3C07 P03B: manual-only review/retry copy. Provider page existence is not
 * historical-version availability, file-byte provenance, publisher trust or an
 * Android installation result. No network I/O or installation side effects.
 */
internal object ArtifactImportJourney {
    enum class Failure { PICKER_UNAVAILABLE, DOCUMENT_INACCESSIBLE, PERMISSION_REVOKED,
        INVALID_OR_INCOMPATIBLE, UNKNOWN }

    fun failureKind(error: Throwable): Failure = when (error) {
        is SecurityException -> Failure.PERMISSION_REVOKED
        is FileNotFoundException -> Failure.DOCUMENT_INACCESSIBLE
        is IOException -> Failure.DOCUMENT_INACCESSIBLE
        is IllegalArgumentException, is IllegalStateException -> Failure.INVALID_OR_INCOMPATIBLE
        else -> Failure.UNKNOWN
    }

    fun failureMessage(error: Throwable): String = when (failureKind(error)) {
        Failure.PICKER_UNAVAILABLE -> "Android document picker is unavailable."
        Failure.DOCUMENT_INACCESSIBLE -> "File access failed or the document is no longer available."
        Failure.PERMISSION_REVOKED -> "Android denied access to the selected document."
        Failure.INVALID_OR_INCOMPATIBLE -> "The selected file failed verification or compatibility checks."
        Failure.UNKNOWN -> "The selected document could not be verified."
    } + " Nothing installed. Choose a file again manually; no automatic provider fallback."

    /** A search reference is NOT a provider lookup. Blank means no preference. */
    fun versionMatches(reference: String, verifiedVersion: Long): Boolean =
        ArtifactHistoricalVersionPolicy.matchesVerified(reference, verifiedVersion)

    fun versionMessage(reference: String, verifiedVersion: Long): String =
        if (versionMatches(reference, verifiedVersion)) "" else
            "Selected APK version does not match your requested version reference. " +
                "No installation approval is possible; choose a matching file or clear the reference and reverify."

    fun providerHandoffMessage(provider: ArtifactProviderDiscovery.Provider): String =
        when (provider) {
            ArtifactProviderDiscovery.Provider.LOCAL_DOCUMENT ->
                "Local document picker only; no upstream provider lookup."
            ArtifactProviderDiscovery.Provider.GOOGLE_PLAY ->
                "Official listing navigation only; historical version availability remains UNKNOWN."
            ArtifactProviderDiscovery.Provider.APKPURE ->
                "Optional browser visit only, disabled until explicit opt-in. No automatic fallback."
            else -> "Manual HTTPS browser visit only; download availability and publisher identity are UNKNOWN."
        }

    fun retryMessage(): String =
        "Choose a downloaded file again using Android's document picker. " +
            "Previous selection and installation consent are not reused."
}
