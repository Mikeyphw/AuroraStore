/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.installer

/** Common fail-closed interpretation of privileged installer command receipts. */
internal object InstallerBackendPolicy {
    private val sessionPattern = Regex("""\[(\d+)]""")
    private val successPattern = Regex("""(?m)^\s*Success(?=[:\s]|$)""")

    fun createdSession(exitOk: Boolean, output: String): Int? {
        if (!commandSucceeded(exitOk, output)) return null
        return sessionPattern.find(output)?.groupValues?.get(1)?.toIntOrNull()
    }

    fun commandSucceeded(exitOk: Boolean, output: String): Boolean = exitOk && validReceipt(output)

    private fun validReceipt(output: String): Boolean {
        if (output.contains("Failure", ignoreCase = true)) {
            return false
        }
        return successPattern.containsMatchIn(output)
    }

    fun isInstalled(installedVersion: Long, expectedVersion: Long): Boolean =
        expectedVersion > 0L && installedVersion >= expectedVersion
}
