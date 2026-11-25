/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

package com.aurora.store.data.installer

import com.aurora.store.data.model.DownloadStatus

/** The only installer-result transitions allowed for a persisted download attempt. */
internal object InstallResultPolicy {
    enum class Outcome {
        PROGRESS,
        PENDING_USER_ACTION,
        SUCCESS,
        FAILURE
    }

    fun matches(
        currentVersion: Long,
        currentAttempt: Long,
        resultVersion: Long,
        resultAttempt: Long
    ): Boolean = currentVersion == resultVersion && currentAttempt == resultAttempt

    fun next(current: DownloadStatus, outcome: Outcome, hasCachedApks: Boolean): DownloadStatus? {
        val result = when (outcome) {
            Outcome.PROGRESS -> when (current) {
                DownloadStatus.COMPLETED -> DownloadStatus.INSTALLING
                else -> null
            }

            Outcome.PENDING_USER_ACTION -> when (current) {
                DownloadStatus.COMPLETED,
                DownloadStatus.INSTALLING -> DownloadStatus.AWAITING_INSTALL

                else -> null
            }

            Outcome.SUCCESS -> when (current) {
                DownloadStatus.COMPLETED,
                DownloadStatus.INSTALLING,
                DownloadStatus.AWAITING_INSTALL -> DownloadStatus.INSTALLED

                else -> null
            }

            Outcome.FAILURE -> when (current) {
                DownloadStatus.COMPLETED,
                DownloadStatus.INSTALLING,
                DownloadStatus.AWAITING_INSTALL -> {
                    if (hasCachedApks) DownloadStatus.AWAITING_INSTALL else DownloadStatus.FAILED
                }

                else -> null
            }
        }
        // Duplicate and out-of-order callbacks must not cause repeated Room writes.
        return result?.takeIf { it != current }
    }
}
