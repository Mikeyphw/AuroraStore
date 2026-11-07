/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

package com.aurora.store.data.work

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TransferStallWatchdogTest {
    @Test
    fun `idle queue never trips network watchdog`() {
        var now = 1_000L
        val watchdog = TransferStallWatchdog(clock = { now }, timeoutMillis = 90_000L)
        now += 300_000L
        assertFalse(watchdog.isStalled())
    }

    @Test
    fun `a transfer with no bytes reaches its timeout`() {
        var now = 1_000L
        val watchdog = TransferStallWatchdog(clock = { now }, timeoutMillis = 90_000L)
        watchdog.begin()
        now += 89_999L
        assertFalse(watchdog.isStalled())
        now += 1L
        assertTrue(watchdog.isStalled())
    }

    @Test
    fun `every positive byte keeps a slow download alive`() {
        var now = 1_000L
        val watchdog = TransferStallWatchdog(clock = { now }, timeoutMillis = 90_000L)
        watchdog.begin()
        repeat(6) {
            now += 60_000L
            watchdog.onBytes(1)
            assertFalse(watchdog.isStalled())
        }
        now += 90_000L
        assertTrue(watchdog.isStalled())
    }

    @Test
    fun `zero-byte updates do not mask a stalled transfer`() {
        var now = 1_000L
        val watchdog = TransferStallWatchdog(clock = { now }, timeoutMillis = 90_000L)
        watchdog.begin()
        now += 60_000L
        watchdog.onBytes(0)
        now += 30_000L
        assertTrue(watchdog.isStalled())
    }

    @Test
    fun `completion disarms watchdog and next transfer resets clock`() {
        var now = 1_000L
        val watchdog = TransferStallWatchdog(clock = { now }, timeoutMillis = 90_000L)
        watchdog.begin()
        now += 90_000L
        assertTrue(watchdog.isStalled())
        watchdog.finish()
        assertFalse(watchdog.isStalled())
        now += 1_000L
        watchdog.begin()
        assertFalse(watchdog.isStalled())
    }
}
