/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.model

import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/** Pseudonymous local account marker; the original account identity is never emitted. */
internal object PlayAccountFingerprint {
    fun hmacHex(secret: ByteArray, accountId: String): String {
        require(secret.size == 32)
        require(accountId.isNotBlank())
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(secret, "HmacSHA256"))
        return mac.doFinal(accountId.toByteArray(Charsets.UTF_8)).joinToString("") { byte ->
            "%02x".format(byte.toInt() and 0xff)
        }
    }
}
