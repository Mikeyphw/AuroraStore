/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import java.io.InputStream
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference

/** One-shot import cancellation and best-effort stream abort; never a trust receipt. */
internal class ArtifactCopyCancellation(
    private val closeAsync: (InputStream) -> Unit = { it.close() }
) {
    private val stopped = AtomicBoolean(false)
    private val openSource = AtomicReference<InputStream?>(null)

    fun isCancelled(): Boolean = stopped.get() || Thread.currentThread().isInterrupted

    fun attach(source: InputStream) {
        check(openSource.compareAndSet(null, source)) { "Source stream already open" }
        if (isCancelled()) {
            // Cancellation may race after openInputStream but before first read.
            openSource.compareAndSet(source, null)
            runCatching { closeAsync(source) }
            throw IllegalStateException("Import cancelled")
        }
    }

    fun detach(source: InputStream) {
        openSource.compareAndSet(source, null)
    }

    fun cancel() {
        stopped.set(true)
        openSource.getAndSet(null)?.let { runCatching { closeAsync(it) } }
    }
}
