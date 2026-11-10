/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import com.google.common.truth.Truth.assertThat
import java.io.ByteArrayInputStream
import java.util.concurrent.atomic.AtomicInteger
import org.junit.Test

class ArtifactCopyCancellationTest {
    @Test fun cancelsOpenSourceExactlyOnce() {
        val closed = AtomicInteger(0)
        val cancellation = ArtifactCopyCancellation { closed.incrementAndGet(); it.close() }
        val stream = ByteArrayInputStream(byteArrayOf(1, 2))
        cancellation.attach(stream)
        cancellation.cancel()
        cancellation.cancel()
        assertThat(cancellation.isCancelled()).isTrue()
        assertThat(closed.get()).isEqualTo(1)
    }

    @Test fun attachAfterCancellationRefusedAndClosed() {
        val closed = AtomicInteger(0)
        val cancellation = ArtifactCopyCancellation { closed.incrementAndGet(); it.close() }
        cancellation.cancel()
        assertThat(runCatching {
            cancellation.attach(ByteArrayInputStream(byteArrayOf(1)))
        }.isFailure).isTrue()
        assertThat(closed.get()).isEqualTo(1)
    }

    @Test fun completedStreamIsNotClosedAgainByCancellation() {
        val closed = AtomicInteger(0)
        val cancellation = ArtifactCopyCancellation { closed.incrementAndGet() }
        val stream = ByteArrayInputStream(byteArrayOf(1))
        cancellation.attach(stream)
        cancellation.detach(stream)
        cancellation.cancel()
        assertThat(closed.get()).isEqualTo(0)
    }

    @Test fun aNewGenerationDoesNotReuseCancelledState() {
        val old = ArtifactCopyCancellation()
        old.cancel()
        val next = ArtifactCopyCancellation()
        assertThat(old.isCancelled()).isTrue()
        assertThat(next.isCancelled()).isFalse()
    }
}
