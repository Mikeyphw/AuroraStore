/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.model

import com.google.common.truth.Truth.assertThat
import org.junit.Test

class PlayAccountFingerprintTest {
    private val secret = ByteArray(32) { it.toByte() }

    @Test
    fun sameKeyAndAccountProduceSamePrivateTag() {
        val first = PlayAccountFingerprint.hmacHex(secret, "user@example.org")
        val second = PlayAccountFingerprint.hmacHex(secret, "user@example.org")
        assertThat(first).isEqualTo(second)
        assertThat(first.length).isEqualTo(64)
        assertThat(first).doesNotContain("@")
        assertThat(first).doesNotContain("example.org")
    }

    @Test
    fun separateAccountCannotReuseTag() {
        assertThat(PlayAccountFingerprint.hmacHex(secret, "a@example.org"))
            .isNotEqualTo(PlayAccountFingerprint.hmacHex(secret, "b@example.org"))
    }

    @Test
    fun aDifferentPrivateSecretChangesTag() {
        assertThat(PlayAccountFingerprint.hmacHex(secret, "a@example.org"))
            .isNotEqualTo(
                PlayAccountFingerprint.hmacHex(ByteArray(32) { 7 }, "a@example.org")
            )
    }

    @Test(expected = IllegalArgumentException::class)
    fun shortSecretIsRefused() {
        PlayAccountFingerprint.hmacHex(ByteArray(3), "a@example.org")
    }

    @Test(expected = IllegalArgumentException::class)
    fun blankAccountCannotBePersisted() {
        PlayAccountFingerprint.hmacHex(secret, " ")
    }
}
