/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.compose.ui.downloads

import com.aurora.store.data.model.DownloadStatus

/** Single source of truth for download affordances across the list and action sheet. */
internal object DownloadUiPolicy {
    fun showTransferStats(status: DownloadStatus): Boolean = status == DownloadStatus.DOWNLOADING

    fun canRetry(status: DownloadStatus, installableFilesPresent: Boolean): Boolean =
        when (status) {
            DownloadStatus.FAILED,
            DownloadStatus.CANCELLED,
            DownloadStatus.UNAVAILABLE -> true

            DownloadStatus.COMPLETED,
            DownloadStatus.AWAITING_INSTALL -> !installableFilesPresent

            else -> false
        }

    fun canCancel(status: DownloadStatus): Boolean = status in DownloadStatus.running
}
