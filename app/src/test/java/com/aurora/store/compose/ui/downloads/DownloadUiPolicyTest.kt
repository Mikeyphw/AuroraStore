/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.compose.ui.downloads

import com.aurora.store.data.model.DownloadStatus
import com.google.common.truth.Truth.assertThat
import org.junit.Test

class DownloadUiPolicyTest {
    @Test
    fun errorStatesCanRetry() {
        listOf(DownloadStatus.FAILED, DownloadStatus.CANCELLED, DownloadStatus.UNAVAILABLE)
            .forEach { assertThat(DownloadUiPolicy.canRetry(it, false)).isTrue() }
    }

    @Test
    fun completedWithPresentFilesDoesNotRetry() {
        assertThat(DownloadUiPolicy.canRetry(DownloadStatus.COMPLETED, true)).isFalse()
    }

    @Test
    fun completedWithMissingFilesCanRetry() {
        assertThat(DownloadUiPolicy.canRetry(DownloadStatus.COMPLETED, false)).isTrue()
    }

    @Test
    fun pendingInstallWithMissingFilesCanRetry() {
        assertThat(DownloadUiPolicy.canRetry(DownloadStatus.AWAITING_INSTALL, false)).isTrue()
    }

    @Test
    fun installingAndInstalledCannotRetry() {
        listOf(DownloadStatus.INSTALLING, DownloadStatus.INSTALLED)
            .forEach { assertThat(DownloadUiPolicy.canRetry(it, false)).isFalse() }
    }

    @Test
    fun onlyDownloadingShowsTransferStats() {
        DownloadStatus.entries.forEach {
            assertThat(DownloadUiPolicy.showTransferStats(it))
                .isEqualTo(it == DownloadStatus.DOWNLOADING)
        }
    }

    @Test
    fun onlyQueuedAndProcessingStatesCanCancel() {
        DownloadStatus.entries.forEach {
            assertThat(DownloadUiPolicy.canCancel(it))
                .isEqualTo(it in DownloadStatus.running)
        }
    }
}
