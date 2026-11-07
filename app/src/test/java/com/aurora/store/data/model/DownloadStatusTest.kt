/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.model

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DownloadStatusTest {
    @Test
    fun `verification is considered active and cancellable`() {
        assertTrue(DownloadStatus.VERIFYING in DownloadStatus.running)
        assertTrue(DownloadStatus.VERIFYING in DownloadStatus.processing)
    }

    @Test
    fun `installation is not an active network download`() {
        assertFalse(DownloadStatus.INSTALLING in DownloadStatus.running)
        assertFalse(DownloadStatus.INSTALLED in DownloadStatus.processing)
        assertFalse(DownloadStatus.CANCELLED in DownloadStatus.running)
    }

    @Test
    fun `queued requests do not block the worker download slot`() {
        assertTrue(DownloadStatus.QUEUED in DownloadStatus.running)
        assertFalse(DownloadStatus.QUEUED in DownloadStatus.processing)
    }
}
