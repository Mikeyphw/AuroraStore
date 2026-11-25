/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.room.download

import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.aurora.store.data.model.DownloadStatus
import com.aurora.store.data.room.AuroraDatabase
import com.aurora.store.data.room.account.AccountConverter
import com.google.common.truth.Truth.assertThat
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import org.junit.Test
import org.junit.runner.RunWith

/** These two tests are invoked in separate instrumentation runs with am force-stop between. */
@RunWith(AndroidJUnit4::class)
class DownloadProcessRestartDeviceTest {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext

    private fun openDatabase(): AuroraDatabase =
        Room.databaseBuilder(context, AuroraDatabase::class.java, DATABASE)
            .addTypeConverter(DownloadConverter(Json { ignoreUnknownKeys = true }))
            .addTypeConverter(AccountConverter())
            .build()

    @Test
    fun seedPersistedProcessingAttempt() = runBlocking {
        context.deleteDatabase(DATABASE)
        val database = openDatabase()
        try {
            val dao = database.downloadDao()
            dao.insert(DownloadLifecycleDeviceTest.fixture(DownloadStatus.DOWNLOADING))
            assertThat(dao.getDownload(DownloadLifecycleDeviceTest.PACKAGE).status)
                .isEqualTo(DownloadStatus.DOWNLOADING)
        } finally {
            database.close()
        }
    }

    @Test
    fun verifyPersistedAttemptAfterForceStop() = runBlocking {
        val database = openDatabase()
        try {
            val dao = database.downloadDao()
            val persisted = dao.getDownload(DownloadLifecycleDeviceTest.PACKAGE)
            assertThat(persisted.downloadedAt).isEqualTo(DownloadLifecycleDeviceTest.ATTEMPT)
            assertThat(persisted.status).isEqualTo(DownloadStatus.DOWNLOADING)
            assertThat(
                dao.failOrphanedDownload(
                    persisted.packageName,
                    persisted.versionCode,
                    persisted.downloadedAt - 1L
                )
            ).isEqualTo(0)
            assertThat(
                dao.failOrphanedDownload(
                    persisted.packageName,
                    persisted.versionCode,
                    persisted.downloadedAt
                )
            ).isEqualTo(1)
            assertThat(dao.getDownload(persisted.packageName).status)
                .isEqualTo(DownloadStatus.FAILED)
        } finally {
            database.close()
            context.deleteDatabase(DATABASE)
        }
    }

    companion object {
        private const val DATABASE = "aurora_r1d_process_restart_fixture.db"
    }
}
