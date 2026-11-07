/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

package com.aurora.store.data.work

/** Monotonic per-transfer heartbeat. Does not count waiting in a WorkManager queue. */
internal class TransferStallWatchdog(
    private val clock: () -> Long,
    private val timeoutMillis: Long = 90_000L
) {
    private var lastByteAt: Long? = null

    init {
        require(timeoutMillis > 0L)
    }

    @Synchronized
    fun begin() {
        lastByteAt = clock()
    }

    @Synchronized
    fun onBytes(count: Long) {
        if (count > 0L && lastByteAt != null) {
            lastByteAt = clock()
        }
    }

    @Synchronized
    fun isStalled(): Boolean {
        val last = lastByteAt ?: return false
        return clock() - last >= timeoutMillis
    }

    @Synchronized
    fun finish() {
        lastByteAt = null
    }
}
