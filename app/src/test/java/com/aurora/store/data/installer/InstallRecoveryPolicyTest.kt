/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.installer

import com.aurora.store.data.model.DownloadStatus
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class InstallRecoveryPolicyTest {
    private fun recover(
        initial: DownloadStatus = DownloadStatus.INSTALLING,
        installed: Long = 0,
        target: Long = 42,
        session: Boolean = false,
        apks: Boolean = true
    ) = InstallRecoveryPolicy.resolve(initial, installed, target, session, apks)

    @Test
    fun `matching version after missed callback is installed`() {
        assertEquals(DownloadStatus.INSTALLED, recover(installed = 42))
    }

    @Test
    fun `newer installed version is installed`() {
        assertEquals(DownloadStatus.INSTALLED, recover(installed = 57))
    }

    @Test
    fun `older installed package cannot be mistaken for success`() {
        assertEquals(DownloadStatus.AWAITING_INSTALL, recover(installed = 41))
    }

    @Test
    fun `committed session survives restart without duplicate commit`() {
        assertEquals(DownloadStatus.AWAITING_INSTALL, recover(apks = false, session = true))
    }

    @Test
    fun `vanished session with APKs becomes retryable`() {
        assertEquals(DownloadStatus.AWAITING_INSTALL, recover(session = false, apks = true))
    }

    @Test
    fun `vanished session and absent APKs become failed rather than stuck`() {
        assertEquals(DownloadStatus.FAILED, recover(session = false, apks = false))
    }

    @Test
    fun `stale self update with no installed target is not falsely successful`() {
        assertEquals(DownloadStatus.AWAITING_INSTALL, recover(installed = 40, target = 41))
    }

    @Test
    fun `awaiting confirmation also reconciles`() {
        assertEquals(
            DownloadStatus.INSTALLED,
            recover(initial = DownloadStatus.AWAITING_INSTALL, installed = 42)
        )
    }

    @Test
    fun `completed download can recover to user install action`() {
        assertEquals(
            DownloadStatus.AWAITING_INSTALL,
            recover(initial = DownloadStatus.COMPLETED)
        )
    }

    @Test
    fun `active worker statuses are never reconciled by installer policy`() {
        for (status in DownloadStatus.running) {
            assertNull(recover(initial = status))
        }
    }

    @Test
    fun `zero target cannot be spuriously resolved as installed`() {
        assertEquals(DownloadStatus.FAILED, recover(installed = 0, target = 0, apks = false))
    }
}
