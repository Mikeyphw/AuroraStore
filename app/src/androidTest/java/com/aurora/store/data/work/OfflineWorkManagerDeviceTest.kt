/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.work

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.work.Configuration
import androidx.work.Data
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkInfo
import androidx.work.WorkManager
import com.google.common.truth.Truth.assertThat
import java.util.UUID
import java.util.concurrent.TimeUnit
import org.junit.Test
import org.junit.runner.RunWith

/** Exercises Android's real WorkManager, never Google's delivery service. */
@RunWith(AndroidJUnit4::class)
class OfflineWorkManagerDeviceTest {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext

    @Test
    fun cancellationOfOldAttemptDoesNotCancelNewAttempt() {
        val manager = manager()
        val prefix = "r1d2-${UUID.randomUUID()}"
        val oldName = "$prefix/42/100"
        val newName = "$prefix/42/101"
        val old = delayed(100L)
        val new = delayed(101L)
        try {
            manager.enqueueUniqueWork(oldName, ExistingWorkPolicy.KEEP, old)
                .result.get(30L, TimeUnit.SECONDS)
            manager.enqueueUniqueWork(newName, ExistingWorkPolicy.KEEP, new)
                .result.get(30L, TimeUnit.SECONDS)
            assertThat(info(manager, old.id).state).isEqualTo(WorkInfo.State.ENQUEUED)
            assertThat(info(manager, new.id).state).isEqualTo(WorkInfo.State.ENQUEUED)
            manager.cancelUniqueWork(oldName).result.get(30L, TimeUnit.SECONDS)
            assertThat(info(manager, old.id).state).isEqualTo(WorkInfo.State.CANCELLED)
            assertThat(info(manager, new.id).state).isEqualTo(WorkInfo.State.ENQUEUED)
        } finally {
            manager.cancelUniqueWork(oldName).result.get(30L, TimeUnit.SECONDS)
            manager.cancelUniqueWork(newName).result.get(30L, TimeUnit.SECONDS)
        }
    }

    @Test
    fun offlineWorkerExecutesWithExpectedAttempt() {
        val manager = manager()
        val name = "r1d2-execute-${UUID.randomUUID()}"
        val request = OneTimeWorkRequestBuilder<OfflineAttemptWorker>()
            .setInputData(Data.Builder().putLong("ATTEMPT_KEY", 31337L).build())
            .build()
        try {
            manager.enqueueUniqueWork(name, ExistingWorkPolicy.KEEP, request)
                .result.get(30L, TimeUnit.SECONDS)
            val finished = waitForCompletion(manager, request.id)
            assertThat(finished.state).isEqualTo(WorkInfo.State.SUCCEEDED)
            assertThat(finished.outputData.getLong("OBSERVED_ATTEMPT", -1L)).isEqualTo(31337L)
        } finally {
            manager.cancelUniqueWork(name).result.get(30L, TimeUnit.SECONDS)
        }
    }

    @Test
    fun seedPersistentAttemptAcrossForceStop() {
        val manager = manager()
        manager.cancelUniqueWork(RESTART_NAME).result.get(30L, TimeUnit.SECONDS)
        manager.enqueueUniqueWork(RESTART_NAME, ExistingWorkPolicy.REPLACE, delayed(9191L))
            .result.get(30L, TimeUnit.SECONDS)
        val stored = manager.getWorkInfosForUniqueWork(RESTART_NAME).get(30L, TimeUnit.SECONDS)
        assertThat(stored).hasSize(1)
        assertThat(stored.single().state).isEqualTo(WorkInfo.State.ENQUEUED)
        assertThat(stored.single().tags).contains("ATTEMPT_KEY:9191")
    }

    @Test
    fun verifyPersistentAttemptAfterForceStop() {
        val manager = manager()
        try {
            val stored = manager.getWorkInfosForUniqueWork(RESTART_NAME).get(30L, TimeUnit.SECONDS)
            assertThat(stored).hasSize(1)
            assertThat(stored.single().state).isEqualTo(WorkInfo.State.ENQUEUED)
            assertThat(stored.single().tags).contains("ATTEMPT_KEY:9191")
        } finally {
            manager.cancelUniqueWork(RESTART_NAME).result.get(30L, TimeUnit.SECONDS)
        }
    }

    private fun delayed(attempt: Long) = OneTimeWorkRequestBuilder<OfflineAttemptWorker>()
        .setInputData(Data.Builder().putLong("ATTEMPT_KEY", attempt).build())
        .addTag("ATTEMPT_KEY:$attempt")
        .setInitialDelay(12L, TimeUnit.HOURS)
        .build()

    private fun manager(): WorkManager = try {
        WorkManager.getInstance(context)
    } catch (_: IllegalStateException) {
        WorkManager.initialize(context, Configuration.Builder().build())
        WorkManager.getInstance(context)
    }

    private fun info(manager: WorkManager, id: UUID): WorkInfo =
        requireNotNull(manager.getWorkInfoById(id).get(30L, TimeUnit.SECONDS))

    private fun waitForCompletion(manager: WorkManager, id: UUID): WorkInfo {
        val deadline = System.currentTimeMillis() + 45_000L
        while (System.currentTimeMillis() < deadline) {
            val state = info(manager, id)
            if (state.state.isFinished) return state
            Thread.sleep(250L)
        }
        error("Offline Worker did not complete")
    }

    companion object {
        private const val RESTART_NAME = "r1d2-unique-work-across-process-stop/42/9191"
    }
}
