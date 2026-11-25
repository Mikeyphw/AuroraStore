/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.work

import androidx.test.ext.junit.runners.AndroidJUnit4
import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith

/** Uses the production watchdog with a deterministic monotonic clock. */
@RunWith(AndroidJUnit4::class)
class TransferStallWatchdogDeviceTest {
    @Test
    fun noBytesForTimeoutMarksTransferStalled() {
        var now = 0L
        val watchdog = TransferStallWatchdog({ now }, timeoutMillis = 90_000L)
        watchdog.begin()
        now = 89_999L
        assertThat(watchdog.isStalled()).isFalse()
        now = 90_000L
        assertThat(watchdog.isStalled()).isTrue()
    }

    @Test
    fun slowButRealProgressResetsTimeout() {
        var now = 0L
        val watchdog = TransferStallWatchdog({ now }, timeoutMillis = 90_000L)
        watchdog.begin()
        now = 80_000L
        watchdog.onBytes(1)
        now = 160_000L
        assertThat(watchdog.isStalled()).isFalse()
        now = 170_000L
        assertThat(watchdog.isStalled()).isTrue()
    }

    @Test
    fun zeroByteActivityDoesNotResetAndFinishDisarms() {
        var now = 0L
        val watchdog = TransferStallWatchdog({ now }, timeoutMillis = 90_000L)
        watchdog.begin()
        now = 89_000L
        watchdog.onBytes(0)
        now = 90_001L
        assertThat(watchdog.isStalled()).isTrue()
        watchdog.finish()
        assertThat(watchdog.isStalled()).isFalse()
    }
}
