/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.work

import android.content.Context
import androidx.work.Data
import androidx.work.Worker
import androidx.work.WorkerParameters

/** Debug-only test worker, never bundled in release builds. */
class OfflineAttemptWorker(context: Context, params: WorkerParameters) : Worker(context, params) {
    override fun doWork(): Result {
        val attempt = inputData.getLong("ATTEMPT_KEY", -1L)
        return Result.success(Data.Builder().putLong("OBSERVED_ATTEMPT", attempt).build())
    }
}
