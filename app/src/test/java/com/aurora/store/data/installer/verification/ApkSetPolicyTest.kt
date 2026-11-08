/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.installer.verification

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

class ApkSetPolicyTest {
    private fun apk(
        name: String = "base.apk",
        pkg: String = "com.example.fixture",
        version: Long = 73L,
        base: Boolean = true,
        signers: Set<String> = setOf("signer-a")
    ) = ApkIdentity(name, pkg, version, base, signers)

    private fun rejects(vararg identities: ApkIdentity) {
        try {
            ApkSetPolicy.check("com.example.fixture", 73L, identities.toList())
            fail("Verification should have rejected this APK set")
        } catch (_: ApkVerificationException) {
            // Expected fail-closed behavior.
        }
    }

    @Test
    fun `single valid base and matching signed split are accepted`() {
        ApkSetPolicy.check("com.example.fixture", 73, listOf(apk()))
        ApkSetPolicy.check(
            "com.example.fixture",
            73,
            listOf(apk(), apk(name = "config.en.apk", base = false))
        )
    }

    @Test
    fun `missing and duplicate base or duplicate split is refused`() {
        rejects()
        rejects(apk(name = "config.apk", base = false))
        rejects(apk(), apk(name = "second.apk"))
        rejects(apk(), apk(name = "config.apk", base = false), apk(name = "config.apk", base = false))
    }

    @Test
    fun `different package or historical version is refused`() {
        rejects(apk(pkg = "com.example.evil"))
        rejects(apk(version = 74))
        rejects(apk(), apk(name = "config.apk", base = false, version = 74))
        rejects(apk(), apk(name = "config.apk", base = false, pkg = "com.example.evil"))
    }

    @Test
    fun `missing and inconsistent signing certificates are refused`() {
        rejects(apk(signers = emptySet()))
        rejects(apk(), apk(name = "config.apk", base = false, signers = emptySet()))
        rejects(apk(), apk(name = "config.apk", base = false, signers = setOf("signer-b")))
    }

    @Test
    fun `installed signer rules are conservative`() {
        val a = setOf("signer-a")
        val b = setOf("signer-b")
        assertTrue(ApkSetPolicy.compatibleInstalledSigners(a, a, a))
        assertTrue(ApkSetPolicy.compatibleInstalledSigners(a, b, a + b))
        assertFalse(ApkSetPolicy.compatibleInstalledSigners(a, b, b))
        assertFalse(ApkSetPolicy.compatibleInstalledSigners(emptySet(), a, a))
        assertFalse(ApkSetPolicy.compatibleInstalledSigners(a + b, a, a + b))
    }
}
