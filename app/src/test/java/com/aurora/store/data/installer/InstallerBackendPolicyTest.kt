/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.installer

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class InstallerBackendPolicyTest {
    @Test
    fun acceptsValidSession() {
        assertEquals(
            42,
            InstallerBackendPolicy.createdSession(true, "Success: created install session [42]")
        )
    }

    @Test
    fun rejectsErrorWithEmbeddedSessionNumber() {
        assertNull(InstallerBackendPolicy.createdSession(false, "Failure [42]"))
    }

    @Test
    fun rejectsMissingSession() {
        assertNull(InstallerBackendPolicy.createdSession(true, "Success"))
    }

    @Test
    fun rejectsNonSuccessResponseWithZeroExit() {
        assertFalse(
            InstallerBackendPolicy.commandSucceeded(true, "Failure [INSTALL_FAILED_INVALID_APK]")
        )
    }

    @Test
    fun rejectsSuccessWithFailedExit() {
        assertFalse(InstallerBackendPolicy.commandSucceeded(false, "Success"))
    }

    @Test
    fun acceptsStandardPmCommit() {
        assertTrue(InstallerBackendPolicy.commandSucceeded(true, "Success"))
    }

    @Test
    fun rejectsFalsePositiveWord() {
        assertFalse(InstallerBackendPolicy.commandSucceeded(true, "NotSuccess"))
    }

    @Test
    fun requiresInstalledTargetVersion() {
        assertFalse(InstallerBackendPolicy.isInstalled(0L, 42L))
        assertFalse(InstallerBackendPolicy.isInstalled(41L, 42L))
        assertTrue(InstallerBackendPolicy.isInstalled(42L, 42L))
        assertFalse(InstallerBackendPolicy.isInstalled(43L, 42L))
    }
}
