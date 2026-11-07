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
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/** Production Room DAO exercised inside an actual API 36 emulator; no Play credentials. */
@RunWith(AndroidJUnit4::class)
class DownloadLifecycleDeviceTest {
    private lateinit var database: AuroraDatabase
    private lateinit var dao: DownloadDao

    @Before
    fun setUp() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        database = Room.inMemoryDatabaseBuilder(context, AuroraDatabase::class.java)
            .addTypeConverter(DownloadConverter(Json { ignoreUnknownKeys = true }))
            .addTypeConverter(AccountConverter())
            .build()
        dao = database.downloadDao()
    }

    @After
    fun tearDown() {
        database.close()
    }

    @Test
    fun cancellationDuringDownloadCannotBeResurrected() = runBlocking {
        dao.insert(fixture(DownloadStatus.DOWNLOADING))
        assertThat(dao.cancelActiveDownload(PACKAGE, VERSION, ATTEMPT)).isEqualTo(1)
        assertThat(dao.updateWorkerStatus(PACKAGE, VERSION, ATTEMPT, DownloadStatus.DOWNLOADING))
            .isEqualTo(0)
        assertThat(dao.updateWorkerProgress(PACKAGE, VERSION, ATTEMPT, 70, 512L, 20L))
            .isEqualTo(0)
        assertThat(dao.getDownload(PACKAGE).status).isEqualTo(DownloadStatus.CANCELLED)
    }

    @Test
    fun cancellationDuringVerificationRemainsPossible() = runBlocking {
        dao.insert(fixture(DownloadStatus.VERIFYING))
        assertThat(dao.cancelActiveDownload(PACKAGE, VERSION, ATTEMPT)).isEqualTo(1)
        assertThat(dao.updateWorkerStatus(PACKAGE, VERSION, ATTEMPT, DownloadStatus.INSTALLING))
            .isEqualTo(0)
        assertThat(dao.getDownload(PACKAGE).status).isEqualTo(DownloadStatus.CANCELLED)
    }

    @Test
    fun sameVersionRetryCreatesNewAttemptAndRejectsOldWorker() = runBlocking {
        dao.insert(fixture(DownloadStatus.CANCELLED))
        assertThat(dao.retryWithNewAttempt(PACKAGE, VERSION, ATTEMPT, ATTEMPT))
            .isEqualTo(1)
        val newAttempt = dao.getDownload(PACKAGE).downloadedAt
        assertThat(newAttempt).isEqualTo(ATTEMPT + 1L)
        assertThat(dao.retryWithNewAttempt(PACKAGE, VERSION, ATTEMPT, ATTEMPT))
            .isEqualTo(0)
        assertThat(dao.updateWorkerStatus(PACKAGE, VERSION, ATTEMPT, DownloadStatus.DOWNLOADING))
            .isEqualTo(0)
        assertThat(dao.updateWorkerStatus(PACKAGE, VERSION, newAttempt, DownloadStatus.DOWNLOADING))
            .isEqualTo(1)
    }

    @Test
    fun obsoleteCancelCannotCancelFreshAttempt() = runBlocking {
        dao.insert(fixture(DownloadStatus.CANCELLED))
        assertThat(dao.retryWithNewAttempt(PACKAGE, VERSION, ATTEMPT, ATTEMPT)).isEqualTo(1)
        val newAttempt = dao.getDownload(PACKAGE).downloadedAt
        assertThat(dao.cancelActiveDownload(PACKAGE, VERSION, ATTEMPT)).isEqualTo(0)
        assertThat(dao.cancelActiveDownload(PACKAGE, VERSION, newAttempt)).isEqualTo(1)
        assertThat(dao.getDownload(PACKAGE).status).isEqualTo(DownloadStatus.CANCELLED)
    }

    @Test
    fun supersededVersionCannotMutateNewVersion() = runBlocking {
        dao.insert(fixture(DownloadStatus.DOWNLOADING))
        dao.insert(fixture(DownloadStatus.QUEUED).copy(versionCode = VERSION + 1L))
        assertThat(dao.updateWorkerStatus(PACKAGE, VERSION, ATTEMPT, DownloadStatus.FAILED))
            .isEqualTo(0)
        assertThat(dao.updateWorkerFiles(PACKAGE, VERSION, ATTEMPT, emptyList()))
            .isEqualTo(0)
        assertThat(dao.updateWorkerSharedLibs(PACKAGE, VERSION, ATTEMPT, emptyList()))
            .isEqualTo(0)
        assertThat(dao.getDownload(PACKAGE).versionCode).isEqualTo(VERSION + 1L)
    }

    @Test
    fun orphanRecoveryOnlyChangesMatchingAttempt() = runBlocking {
        dao.insert(fixture(DownloadStatus.DOWNLOADING))
        assertThat(dao.failOrphanedDownload(PACKAGE, VERSION, ATTEMPT - 1L)).isEqualTo(0)
        assertThat(dao.failOrphanedDownload(PACKAGE, VERSION + 1L, ATTEMPT)).isEqualTo(0)
        assertThat(dao.failOrphanedDownload(PACKAGE, VERSION, ATTEMPT)).isEqualTo(1)
        assertThat(dao.getDownload(PACKAGE).status).isEqualTo(DownloadStatus.FAILED)
    }

    @Test
    fun installerHandoffDoesNotAcceptCancellationOrWorkerReentry() = runBlocking {
        dao.insert(fixture(DownloadStatus.INSTALLING))
        assertThat(dao.cancelActiveDownload(PACKAGE, VERSION, ATTEMPT)).isEqualTo(0)
        assertThat(dao.updateWorkerStatus(PACKAGE, VERSION, ATTEMPT, DownloadStatus.FAILED))
            .isEqualTo(0)
        assertThat(dao.retryWithNewAttempt(PACKAGE, VERSION, ATTEMPT, ATTEMPT)).isEqualTo(0)
        assertThat(dao.getDownload(PACKAGE).status).isEqualTo(DownloadStatus.INSTALLING)
    }

    @Test
    fun oldClearActionCannotDeleteReplacement() = runBlocking {
        dao.insert(fixture(DownloadStatus.CANCELLED))
        dao.insert(fixture(DownloadStatus.QUEUED).copy(downloadedAt = ATTEMPT + 1L))
        assertThat(dao.deleteVersion(PACKAGE, VERSION, ATTEMPT)).isEqualTo(0)
        assertThat(dao.getDownload(PACKAGE).downloadedAt).isEqualTo(ATTEMPT + 1L)
    }

    @Test
    fun finishedInstallCannotBeRetroactivelyMarkedAsDownloadFailure() = runBlocking {
        dao.insert(fixture(DownloadStatus.INSTALLED))
        assertThat(dao.failOrphanedDownload(PACKAGE, VERSION, ATTEMPT)).isEqualTo(0)
        assertThat(dao.updateWorkerStatus(PACKAGE, VERSION, ATTEMPT, DownloadStatus.FAILED))
            .isEqualTo(0)
        assertThat(dao.getDownload(PACKAGE).status).isEqualTo(DownloadStatus.INSTALLED)
    }

    companion object {
        const val PACKAGE = "com.aurora.r1d.fixture"
        const val VERSION = 42L
        const val ATTEMPT = 1000L

        fun fixture(status: DownloadStatus): Download = Download(
            packageName = PACKAGE,
            versionCode = VERSION,
            offerType = 0,
            isInstalled = false,
            displayName = "R1D offline fixture",
            iconURL = "",
            size = 4096L,
            id = 42,
            status = status,
            progress = 0,
            speed = 0L,
            timeRemaining = 0L,
            totalFiles = 1,
            downloadedFiles = 0,
            fileList = emptyList(),
            sharedLibs = emptyList(),
            downloadedAt = ATTEMPT
        )
    }
}
