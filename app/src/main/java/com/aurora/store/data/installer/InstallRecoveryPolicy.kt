/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.installer

import com.aurora.store.data.model.DownloadStatus

/** Pure, idempotent policy for recovering a download whose install handoff was interrupted. */
internal object InstallRecoveryPolicy {
    fun resolve(
        status: DownloadStatus,
        installedVersion: Long,
        targetVersion: Long,
        hasLiveSession: Boolean,
        hasCachedApks: Boolean
    ): DownloadStatus? {
        val recoverable = status == DownloadStatus.COMPLETED ||
            status == DownloadStatus.INSTALLING ||
            status == DownloadStatus.AWAITING_INSTALL
        if (!recoverable) return null

        return when {
            // The OS is the authority, not an old Room status or a missed callback.
            targetVersion > 0 && installedVersion == targetVersion -> DownloadStatus.INSTALLED
            // Never abandon an outstanding Android confirmation just because Aurora restarted.
            hasLiveSession -> DownloadStatus.AWAITING_INSTALL
            // A vanished session can be retried using the already downloaded APKs.
            hasCachedApks -> DownloadStatus.AWAITING_INSTALL
            // No package, session, or APK to complete installation. Do not remain Installing.
            else -> DownloadStatus.FAILED
        }
    }
}
