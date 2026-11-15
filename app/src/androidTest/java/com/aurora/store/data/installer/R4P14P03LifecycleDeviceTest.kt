/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.installer

import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.aurora.store.compose.ui.downloads.DownloadUiPolicy
import com.aurora.store.data.model.DownloadStatus
import com.aurora.store.data.room.AuroraDatabase
import com.aurora.store.data.room.account.AccountConverter
import com.aurora.store.data.room.download.Download
import com.aurora.store.data.room.download.DownloadConverter
import com.aurora.store.data.room.download.DownloadDao
import com.google.common.truth.Truth.assertThat
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Real Room DAO + production installer-result/recovery policy on disposable API36.
 * No actual APK install, Android permission dialog, Play client or physical device.
 * The user-decline outcome is simulated from the OS callback, not a clicked OS dialog.
 */
@RunWith(AndroidJUnit4::class)
class R4P14P03LifecycleDeviceTest {
    private lateinit var database: AuroraDatabase
    private lateinit var dao: DownloadDao

    @Before fun setUp() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        database = Room.inMemoryDatabaseBuilder(context, AuroraDatabase::class.java)
            .addTypeConverter(DownloadConverter(Json { ignoreUnknownKeys = true }))
            .addTypeConverter(AccountConverter())
            .build()
        dao = database.downloadDao()
    }

    @After fun tearDown() { database.close() }

    private fun fixture(status: DownloadStatus, pkg: String = PACKAGE): Download = Download(
        packageName = pkg, versionCode = VERSION, offerType = 0, isInstalled = false,
        displayName = "P14 offline update fixture", iconURL = "", size = 4096L,
        id = 145, status = status, progress = 0, speed = 0L, timeRemaining = 0L,
        totalFiles = 1, downloadedFiles = 0, fileList = emptyList(),
        sharedLibs = emptyList(), downloadedAt = ATTEMPT
    )

    @Test
    fun activeUpdateCancelBlocksLateProgressAndCompletion() = runBlocking {
        dao.insert(fixture(DownloadStatus.DOWNLOADING))
        assertThat(dao.cancelActiveDownload(PACKAGE, VERSION, ATTEMPT)).isEqualTo(1)
        assertThat(dao.updateWorkerProgress(PACKAGE, VERSION, ATTEMPT, 99, 1234, 1)).isEqualTo(0)
        assertThat(dao.updateWorkerStatus(PACKAGE, VERSION, ATTEMPT, DownloadStatus.COMPLETED))
            .isEqualTo(0)
        assertThat(dao.getDownload(PACKAGE).status).isEqualTo(DownloadStatus.CANCELLED)
        assertThat(DownloadUiPolicy.canRetry(DownloadStatus.CANCELLED, false)).isTrue()
    }

    @Test
    fun verifyStageCancellationCannotBecomeInstallerHandoff() = runBlocking {
        dao.insert(fixture(DownloadStatus.VERIFYING))
        assertThat(dao.cancelActiveDownload(PACKAGE, VERSION, ATTEMPT)).isEqualTo(1)
        assertThat(dao.updateWorkerStatus(PACKAGE, VERSION, ATTEMPT, DownloadStatus.INSTALLING))
            .isEqualTo(0)
        assertThat(dao.getDownload(PACKAGE).status).isEqualTo(DownloadStatus.CANCELLED)
    }

    @Test
    fun failedUpdateRetryGetsFreshAttemptAndDropsOldWorker() = runBlocking {
        dao.insert(fixture(DownloadStatus.FAILED))
        assertThat(dao.retryWithNewAttempt(PACKAGE, VERSION, ATTEMPT, ATTEMPT + 11)).isEqualTo(1)
        val retry = dao.getDownload(PACKAGE)
        assertThat(retry.downloadedAt).isEqualTo(ATTEMPT + 11)
        assertThat(retry.status).isEqualTo(DownloadStatus.QUEUED)
        assertThat(dao.updateWorkerStatus(PACKAGE, VERSION, ATTEMPT, DownloadStatus.COMPLETED))
            .isEqualTo(0)
        assertThat(dao.updateWorkerStatus(PACKAGE, VERSION, retry.downloadedAt,
            DownloadStatus.DOWNLOADING)).isEqualTo(1)
        assertThat(dao.updateWorkerProgress(PACKAGE, VERSION, retry.downloadedAt,
            42, 1000L, 12L)).isEqualTo(1)
        assertThat(dao.getDownload(PACKAGE).progress).isEqualTo(42)
    }

    @Test
    fun newerUpdateVersionRejectsOldCancellationAndInstallerResult() = runBlocking {
        dao.insert(fixture(DownloadStatus.DOWNLOADING))
        dao.insert(fixture(DownloadStatus.QUEUED).copy(versionCode = VERSION + 1L,
            downloadedAt = ATTEMPT + 1L))
        assertThat(dao.cancelActiveDownload(PACKAGE, VERSION, ATTEMPT)).isEqualTo(0)
        assertThat(dao.updateWorkerStatus(PACKAGE, VERSION, ATTEMPT, DownloadStatus.FAILED))
            .isEqualTo(0)
        assertThat(dao.transitionInstallAttempt(PACKAGE, VERSION, ATTEMPT,
            DownloadStatus.QUEUED, DownloadStatus.INSTALLED)).isEqualTo(0)
        assertThat(dao.getDownload(PACKAGE).versionCode).isEqualTo(VERSION + 1L)
    }

    @Test
    fun installerUserDeclineWithCachedApkRemainsPendingNotInstalled() = runBlocking {
        dao.insert(fixture(DownloadStatus.INSTALLING))
        val pending = InstallResultPolicy.next(DownloadStatus.INSTALLING,
            InstallResultPolicy.Outcome.PENDING_USER_ACTION, true)
        assertThat(pending).isEqualTo(DownloadStatus.AWAITING_INSTALL)
        assertThat(dao.transitionInstallAttempt(PACKAGE, VERSION, ATTEMPT,
            DownloadStatus.INSTALLING, pending!!)).isEqualTo(1)
        // Android STATUS_FAILURE_ABORTED is mapped to Outcome.FAILURE by the receiver.
        // Available cached APKs permit explicit retry; declining MUST NOT mark installed.
        val declined = InstallResultPolicy.next(DownloadStatus.AWAITING_INSTALL,
            InstallResultPolicy.Outcome.FAILURE, true)
        assertThat(declined).isNull()
        assertThat(dao.getDownload(PACKAGE).status).isEqualTo(DownloadStatus.AWAITING_INSTALL)
        assertThat(DownloadUiPolicy.canRetry(DownloadStatus.AWAITING_INSTALL, true)).isFalse()
    }

    @Test
    fun installerUserDeclineWithoutCachedApkFailsThenAllowsRetry() = runBlocking {
        dao.insert(fixture(DownloadStatus.INSTALLING))
        val declined = InstallResultPolicy.next(DownloadStatus.INSTALLING,
            InstallResultPolicy.Outcome.FAILURE, false)
        assertThat(declined).isEqualTo(DownloadStatus.FAILED)
        assertThat(dao.transitionInstallAttempt(PACKAGE, VERSION, ATTEMPT,
            DownloadStatus.INSTALLING, declined!!)).isEqualTo(1)
        assertThat(dao.retryWithNewAttempt(PACKAGE, VERSION, ATTEMPT, ATTEMPT + 5L)).isEqualTo(1)
        val next = dao.getDownload(PACKAGE)
        assertThat(next.status).isEqualTo(DownloadStatus.QUEUED)
        assertThat(dao.transitionInstallAttempt(PACKAGE, VERSION, ATTEMPT,
            DownloadStatus.INSTALLING, DownloadStatus.INSTALLED)).isEqualTo(0)
    }

    @Test
    fun interruptedInstallRecoveryWithCachedApkRestoresPendingState() = runBlocking {
        dao.insert(fixture(DownloadStatus.INSTALLING))
        val recovered = InstallRecoveryPolicy.resolve(DownloadStatus.INSTALLING,
            installedVersion = 0L, targetVersion = VERSION, hasLiveSession = false,
            hasCachedApks = true)
        assertThat(recovered).isEqualTo(DownloadStatus.AWAITING_INSTALL)
        assertThat(dao.reconcileInstallStatus(PACKAGE, VERSION, ATTEMPT, recovered!!)).isEqualTo(1)
        assertThat(dao.getDownload(PACKAGE).status).isEqualTo(DownloadStatus.AWAITING_INSTALL)
        assertThat(dao.cancelActiveDownload(PACKAGE, VERSION, ATTEMPT)).isEqualTo(0)
    }

    @Test
    fun missingSessionAndApkCannotRemainInstallingForever() = runBlocking {
        dao.insert(fixture(DownloadStatus.INSTALLING))
        val recovered = InstallRecoveryPolicy.resolve(DownloadStatus.INSTALLING,
            installedVersion = 0L, targetVersion = VERSION, hasLiveSession = false,
            hasCachedApks = false)
        assertThat(recovered).isEqualTo(DownloadStatus.FAILED)
        assertThat(dao.reconcileInstallStatus(PACKAGE, VERSION, ATTEMPT, recovered!!)).isEqualTo(1)
        assertThat(dao.getDownload(PACKAGE).status).isEqualTo(DownloadStatus.FAILED)
        assertThat(DownloadUiPolicy.canRetry(DownloadStatus.FAILED, false)).isTrue()
        assertThat(dao.retryWithNewAttempt(PACKAGE, VERSION, ATTEMPT, ATTEMPT + 2L)).isEqualTo(1)
        assertThat(dao.getDownload(PACKAGE).status).isEqualTo(DownloadStatus.QUEUED)
    }

    companion object {
        const val PACKAGE = "com.aurora.p14p03.fixture"
        const val VERSION = 45L
        const val ATTEMPT = 1403000L
    }
}
