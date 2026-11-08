/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.room.download

import android.content.pm.PackageInstaller
import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.aurora.store.data.model.DownloadStatus
import com.aurora.store.data.room.AuroraDatabase
import com.aurora.store.data.room.account.AccountConverter
import com.aurora.store.util.PackageUtil
import com.google.common.truth.Truth.assertThat
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import org.junit.Test
import org.junit.runner.RunWith

/**
 * R2D uses a real installed fixture APK and real OS-owned PackageInstaller session.
 * CI force-stops Aurora between these tests, then installs the fixture via Android pm.
 * The durable row uses Aurora's actual production DB (aurora_database).
 * The verifier observes AuroraApp's automatic recovery after a separate normal app startup,
 * rather than manually invoking the recovery policy in the instrumentation process.
 */
@RunWith(AndroidJUnit4::class)
class InstallLifecycleRestartDeviceTest {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext

    private fun database(): AuroraDatabase =
        Room.databaseBuilder(context, AuroraDatabase::class.java, DATABASE)
            .addTypeConverter(DownloadConverter(Json { ignoreUnknownKeys = true }))
            .addTypeConverter(AccountConverter())
            .build()

    @Test
    fun seedInterruptedInstallAndOwnedSession() = runBlocking {
        context.deleteDatabase(DATABASE)
        assertThat(PackageUtil.getInstalledVersionCode(context, PACKAGE)).isEqualTo(0L)
        val db = database()
        try {
            db.downloadDao().insert(
                DownloadLifecycleDeviceTest.fixture(DownloadStatus.INSTALLING).copy(
                    packageName = PACKAGE,
                    versionCode = VERSION,
                    downloadedAt = ATTEMPT
                )
            )
            assertThat(db.downloadDao().getDownload(PACKAGE).status)
                .isEqualTo(DownloadStatus.INSTALLING)
        } finally {
            db.close()
        }
        val installer = context.packageManager.packageInstaller
        val params = PackageInstaller.SessionParams(
            PackageInstaller.SessionParams.MODE_FULL_INSTALL
        )
        params.setAppPackageName(UNFINISHED_PACKAGE)
        val sessionId = installer.createSession(params)
        assertThat(installer.mySessions.any { it.sessionId == sessionId }).isTrue()
        context.getSharedPreferences(PREFS, 0).edit().putInt(SESSION_ID, sessionId).commit()
        // JUnit4 methods must return Java void, not the Boolean result of commit().
        Unit
    }

    @Test
    fun reconcileRealInstallAfterForceStop() = runBlocking {
        val installedVersion = PackageUtil.getInstalledVersionCode(context, PACKAGE)
        assertThat(installedVersion).isAtLeast(VERSION)
        val db = database()
        try {
            val current = db.downloadDao().getDownload(PACKAGE)
            assertThat(current.versionCode).isEqualTo(VERSION)
            assertThat(current.downloadedAt).isEqualTo(ATTEMPT)
            // The separate production AuroraApp process must have performed recovery.
            // This test deliberately does NOT call InstallRecoveryPolicy or modify the row.
            assertThat(current.status).isEqualTo(DownloadStatus.INSTALLED)
            assertThat(
                db.downloadDao().transitionInstallAttempt(
                    PACKAGE,
                    VERSION,
                    ATTEMPT - 1L,
                    DownloadStatus.INSTALLED,
                    DownloadStatus.FAILED
                )
            ).isEqualTo(0)
            assertThat(
                db.downloadDao().transitionInstallAttempt(
                    PACKAGE,
                    VERSION,
                    ATTEMPT,
                    DownloadStatus.INSTALLING,
                    DownloadStatus.FAILED
                )
            ).isEqualTo(0)
            assertThat(db.downloadDao().getDownload(PACKAGE).status)
                .isEqualTo(DownloadStatus.INSTALLED)
        } finally {
            db.close()
            context.deleteDatabase(DATABASE)
        }
        val preferences = context.getSharedPreferences(PREFS, 0)
        val sessionId = preferences.getInt(SESSION_ID, -1)
        assertThat(sessionId).isGreaterThan(0)
        val installer = context.packageManager.packageInstaller
        assertThat(installer.mySessions.any { it.sessionId == sessionId }).isTrue()
        installer.abandonSession(sessionId)
        assertThat(installer.mySessions.none { it.sessionId == sessionId }).isTrue()
        preferences.edit().clear().commit()
        Unit
    }

    companion object {
        const val PACKAGE = "com.aurora.r2d.fixture"
        const val VERSION = 73L
        const val ATTEMPT = 7300L
        private const val DATABASE = "aurora_database"
        private const val PREFS = "aurora_r2d_owned_session"
        private const val SESSION_ID = "session_id"
        private const val UNFINISHED_PACKAGE = "com.aurora.r2d.unfinished"
    }
}
