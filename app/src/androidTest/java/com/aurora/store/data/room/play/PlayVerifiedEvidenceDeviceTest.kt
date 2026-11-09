/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.room.play

import android.content.Context
import android.util.Base64
import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.aurora.gplayapi.model.AppFile
import com.aurora.store.data.installer.verification.ApkVerificationException
import com.aurora.store.data.installer.verification.R3bVerifiedProof
import com.aurora.store.data.model.DownloadStatus
import com.aurora.store.data.model.PlayAccountFingerprint
import com.aurora.store.data.model.PlayExactVersionOutcomePolicy
import com.aurora.store.data.room.AuroraDatabase
import com.aurora.store.data.room.account.AccountConverter
import com.aurora.store.data.room.download.Download
import com.aurora.store.data.room.download.DownloadConverter
import com.google.common.truth.Truth.assertThat
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/** Real Room transactions on API 36; no credential, Play traffic or claimed verified APK. */
@RunWith(AndroidJUnit4::class)
class PlayVerifiedEvidenceDeviceTest {
    private val context: Context
        get() = InstrumentationRegistry.getInstrumentation().targetContext
    private lateinit var database: AuroraDatabase
    private var previousIdentityKey: String? = null
    private lateinit var store: PlayVerifiedEvidenceStore
    private val packageName = "com.aurora.r3c03.c02.fixture"
    private val versionCode = 73L
    private val generation = 9001L
    private val variant = "offer:0;sdk:36;lane:anonymous"
    private val secret = ByteArray(32) { it.toByte() }

    private val key: PlayExactVersionOutcomePolicy.RequestKey
        get() = PlayExactVersionOutcomePolicy.RequestKey(
            packageName,
            versionCode,
            generation,
            PlayAccountFingerprint.hmacHex(secret, "unbound"),
            variant
        )

    @Before
    fun setUp() = runBlocking {
        val prefs = context.getSharedPreferences("play_evidence_identity", Context.MODE_PRIVATE)
        previousIdentityKey = prefs.getString("key", null)
        assertThat(
            prefs.edit().putString("key", Base64.encodeToString(secret, Base64.NO_WRAP)).commit()
        ).isTrue()
        database = Room.inMemoryDatabaseBuilder(context, AuroraDatabase::class.java)
            .addTypeConverter(DownloadConverter(Json { ignoreUnknownKeys = true }))
            .addTypeConverter(AccountConverter())
            .build()
        store = PlayVerifiedEvidenceStore(
            database,
            database.playDeliveryEvidenceDao(),
            database.downloadDao(),
            context
        )
        database.downloadDao().insert(fixture(DownloadStatus.VERIFYING))
    }

    @After
    fun tearDown() {
        database.close()
        val prefs = context.getSharedPreferences("play_evidence_identity", Context.MODE_PRIVATE)
        val edit = prefs.edit()
        if (previousIdentityKey == null) {
            edit.remove("key")
        } else {
            edit.putString("key", previousIdentityKey)
        }
        assertThat(edit.commit()).isTrue()
    }

    private fun fixture(status: DownloadStatus): Download = Download(
        packageName = packageName,
        versionCode = versionCode,
        offerType = 0,
        isInstalled = false,
        displayName = "R3C-03 C02 offline fixture",
        iconURL = "",
        size = 8L,
        id = 0,
        status = status,
        progress = 0,
        speed = 0L,
        timeRemaining = 0L,
        totalFiles = 1,
        downloadedFiles = 0,
        fileList = listOf(
            AppFile(
                url = "https://localhost.invalid/fixture",
                name = "base.apk",
                size = 8L,
                sha256 = "0".repeat(64)
            )
        ),
        sharedLibs = emptyList(),
        downloadedAt = generation
    )

    private suspend fun urls(): Boolean = database.playDeliveryEvidenceDao().accept(
        packageName,
        versionCode,
        generation,
        requireNotNull(key.accountBinding),
        "unbound",
        requireNotNull(key.variant),
        "URLS_RESOLVED",
        1
    )

    @Test
    fun bytesCannotSkipRealPlayUrls() = runBlocking {
        assertThat(store.bytesReceived(key, "unbound", 1)).isFalse()
        assertThat(database.playDeliveryEvidenceDao().latest(packageName)).isNull()
        assertThat(urls()).isTrue()
        assertThat(store.bytesReceived(key, "unbound", 1)).isTrue()
        val row = database.playDeliveryEvidenceDao().latest(packageName)
        assertThat(row?.state).isEqualTo("BYTES_DOWNLOADED_NOT_VERIFIED")
        assertThat(row?.verifiedApkVersion).isNull()
    }

    @Test
    fun wrongVersionAndFileCountCannotAcquireEvidence() = runBlocking {
        assertThat(urls()).isTrue()
        assertThat(store.bytesReceived(key.copy(versionCode = 74L), "unbound", 1)).isFalse()
        assertThat(store.bytesReceived(key, "unbound", 2)).isFalse()
        assertThat(database.playDeliveryEvidenceDao().latest(packageName)?.state)
            .isEqualTo("URLS_RESOLVED_NOT_VERIFIED")
    }

    @Test
    fun cancelledAttemptCannotAdvance() = runBlocking {
        assertThat(urls()).isTrue()
        assertThat(database.downloadDao().cancelActiveDownload(packageName, versionCode, generation))
            .isEqualTo(1)
        assertThat(store.bytesReceived(key, "unbound", 1)).isFalse()
    }

    @Test
    fun replacedAttemptCannotAdvance() = runBlocking {
        assertThat(urls()).isTrue()
        database.downloadDao().insert(fixture(DownloadStatus.VERIFYING).copy(downloadedAt = 9002L))
        assertThat(store.bytesReceived(key, "unbound", 1)).isFalse()
    }

    @Test
    fun accountSelectionMismatchCannotAdvance() = runBlocking {
        assertThat(urls()).isTrue()
        assertThat(store.bytesReceived(key, "other-account", 1)).isFalse()
    }

    @Test
    fun missingUnverifiedApkCannotMintProof() {
        val download = fixture(DownloadStatus.VERIFYING)
        try {
            R3bVerifiedProof.verify(context, download) { false }
            throw AssertionError("Missing fake APK unexpectedly minted a verification proof")
        } catch (_: ApkVerificationException) {
            // A byte-only test fixture is never sufficient to assert verified content.
        }
    }

    @Test
    fun installerFailureRequiresPriorVerifiedState() = runBlocking {
        assertThat(urls()).isTrue()
        database.downloadDao().insert(fixture(DownloadStatus.FAILED))
        assertThat(store.installerFailed(packageName, versionCode, generation)).isFalse()
        assertThat(database.playDeliveryEvidenceDao().latest(packageName)?.verifiedApkVersion)
            .isNull()
    }

    @Test
    fun syntheticMatchedInstallerFailureTransitionsVerifiedEvidence() = runBlocking {
        val snapshot = PlayExactVersionOutcomePolicy.Snapshot(
            key,
            PlayExactVersionOutcomePolicy.State.VERIFIED_SET,
            verifiedApkVersion = versionCode,
            resolvedFileCount = 1
        )
        // This is a DAO state-machine fixture, not proof that a synthetic APK was verified.
        database.playDeliveryEvidenceDao().put(PlayDeliveryEvidence.from(snapshot))
        database.downloadDao().insert(fixture(DownloadStatus.AWAITING_INSTALL))
        assertThat(store.installerFailed(packageName, versionCode, generation)).isTrue()
        assertThat(database.playDeliveryEvidenceDao().latest(packageName)?.state)
            .isEqualTo("INSTALL_FAILED")
        assertThat(store.installerFailed(packageName, versionCode, generation + 1)).isFalse()
    }
}
