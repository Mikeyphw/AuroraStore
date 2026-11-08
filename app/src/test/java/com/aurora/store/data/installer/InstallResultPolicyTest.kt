/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

package com.aurora.store.data.installer

import com.aurora.store.data.model.DownloadStatus
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class InstallResultPolicyTest {
    private val policy = InstallResultPolicy

    @Test
    fun `matching generation requires exact version and attempt`() {
        assertTrue(policy.matches(42L, 1001L, 42L, 1001L))
        assertFalse(policy.matches(42L, 1001L, 42L, 1002L))
        assertFalse(policy.matches(42L, 1001L, 43L, 1001L))
        assertFalse(policy.matches(42L, 1001L, 43L, 1002L))
    }

    @Test
    fun `progress moves only a completed handoff into installing`() {
        assertEquals(
            DownloadStatus.INSTALLING,
            policy.next(DownloadStatus.COMPLETED, InstallResultPolicy.Outcome.PROGRESS, true)
        )
        assertNull(
            policy.next(DownloadStatus.INSTALLING, InstallResultPolicy.Outcome.PROGRESS, true)
        )
        assertNull(
            policy.next(DownloadStatus.QUEUED, InstallResultPolicy.Outcome.PROGRESS, true)
        )
    }

    @Test
    fun `pending confirmation is idempotent and never revives installed`() {
        val action = InstallResultPolicy.Outcome.PENDING_USER_ACTION
        assertEquals(
            DownloadStatus.AWAITING_INSTALL,
            policy.next(DownloadStatus.INSTALLING, action, true)
        )
        assertEquals(
            DownloadStatus.AWAITING_INSTALL,
            policy.next(DownloadStatus.COMPLETED, action, true)
        )
        assertNull(policy.next(DownloadStatus.AWAITING_INSTALL, action, true))
        assertNull(policy.next(DownloadStatus.INSTALLED, action, true))
    }

    @Test
    fun `success is a one way terminal transition`() {
        val success = InstallResultPolicy.Outcome.SUCCESS
        val installerStates = listOf(
            DownloadStatus.COMPLETED,
            DownloadStatus.INSTALLING,
            DownloadStatus.AWAITING_INSTALL
        )
        for (status in installerStates) {
            assertEquals(DownloadStatus.INSTALLED, policy.next(status, success, false))
        }
        assertNull(policy.next(DownloadStatus.INSTALLED, success, false))
        assertNull(policy.next(DownloadStatus.QUEUED, success, false))
    }

    @Test
    fun `failure preserves cached apk retry state`() {
        val failure = InstallResultPolicy.Outcome.FAILURE
        assertEquals(
            DownloadStatus.AWAITING_INSTALL,
            policy.next(DownloadStatus.INSTALLING, failure, true)
        )
        assertNull(policy.next(DownloadStatus.AWAITING_INSTALL, failure, true))
    }

    @Test
    fun `failure without apk becomes failed instead of installing forever`() {
        val failure = InstallResultPolicy.Outcome.FAILURE
        assertEquals(DownloadStatus.FAILED, policy.next(DownloadStatus.INSTALLING, failure, false))
        assertEquals(
            DownloadStatus.FAILED,
            policy.next(DownloadStatus.AWAITING_INSTALL, failure, false)
        )
        assertNull(policy.next(DownloadStatus.FAILED, failure, false))
    }

    @Test
    fun `late failure cannot reverse installed even without cached apks`() {
        val failure = InstallResultPolicy.Outcome.FAILURE
        assertNull(policy.next(DownloadStatus.INSTALLED, failure, true))
        assertNull(policy.next(DownloadStatus.INSTALLED, failure, false))
    }

    @Test
    fun `callbacks never override queued or active download states`() {
        val downloadStates = listOf(
            DownloadStatus.QUEUED,
            DownloadStatus.PURCHASING,
            DownloadStatus.DOWNLOADING,
            DownloadStatus.VERIFYING,
            DownloadStatus.CANCELLED,
            DownloadStatus.UNAVAILABLE
        )
        for (status in downloadStates) {
            for (outcome in InstallResultPolicy.Outcome.entries) {
                assertNull(policy.next(status, outcome, true))
                assertNull(policy.next(status, outcome, false))
            }
        }
    }

    @Test
    fun `duplicate ordered callbacks perform only one transition`() {
        val pending = InstallResultPolicy.Outcome.PENDING_USER_ACTION
        val success = InstallResultPolicy.Outcome.SUCCESS
        val initial = policy.next(DownloadStatus.COMPLETED, pending, true)!!
        assertEquals(DownloadStatus.AWAITING_INSTALL, initial)
        assertNull(policy.next(initial, pending, true))
        val terminal = policy.next(initial, success, true)!!
        assertEquals(DownloadStatus.INSTALLED, terminal)
        assertNull(policy.next(terminal, pending, true))
        assertNull(policy.next(terminal, success, true))
        assertNull(policy.next(terminal, InstallResultPolicy.Outcome.FAILURE, true))
    }
}
