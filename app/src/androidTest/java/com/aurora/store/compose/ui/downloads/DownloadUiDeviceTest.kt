/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.compose.ui.downloads

import android.graphics.Bitmap
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.test.captureToImage
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.aurora.store.IsolatedTest
import com.aurora.store.R
import com.aurora.store.compose.composable.DownloadListItem
import com.aurora.store.compose.ui.sheets.DownloadActionsSheet
import com.aurora.store.data.model.DownloadStatus
import com.aurora.store.data.room.download.Download
import com.google.common.truth.Truth.assertThat
import java.io.File
import java.io.FileOutputStream
import org.junit.Test
import org.junit.runner.RunWith

/** Real Compose semantics and screenshot evidence on the hosted API36 emulator. */
@RunWith(AndroidJUnit4::class)
class DownloadUiDeviceTest : IsolatedTest() {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext

    @Test
    fun queuedDoesNotShowMisleadingZeroSpeedOrEta() {
        setContent { DownloadListItem(download = fixture(DownloadStatus.QUEUED)) }
        composeTestRule.onNodeWithText("0%", substring = true).assertDoesNotExist()
        composeTestRule.onNodeWithText("0 B/s", substring = true).assertDoesNotExist()
        composeTestRule.onNodeWithText(context.getString(R.string.status_queued)).assertExists()
        screenshot("r1f_queued.png")
    }

    @Test
    fun downloadingShowsRealProgressWithoutFabricatedSpeed() {
        setContent {
            DownloadListItem(download = fixture(DownloadStatus.DOWNLOADING, progress = 45))
        }
        composeTestRule.onNodeWithText("45%", substring = true).assertExists()
        composeTestRule.onNodeWithText("0 B/s", substring = true).assertDoesNotExist()
        screenshot("r1f_downloading.png")
    }

    @Test
    fun failedDownloadHasDistinctFailureDescription() {
        setContent { DownloadListItem(download = fixture(DownloadStatus.FAILED)) }
        composeTestRule.onNodeWithContentDescription(context.getString(R.string.status_failed))
            .assertExists()
        screenshot("r1f_failed.png")
    }

    @Test
    fun failedDownloadExposesWorkingRetryAction() {
        var retries = 0
        setContent {
            DownloadActionsSheet(
                download = fixture(DownloadStatus.FAILED),
                onDismiss = {},
                onShowDetails = {},
                onCancel = {},
                onRetry = { retries++ },
                onInstall = {},
                onExport = {},
                onClear = {}
            )
        }
        composeTestRule.onNodeWithText(context.getString(R.string.r1f_download_retry))
            .assertExists()
            .performClick()
        composeTestRule.runOnIdle { assertThat(retries).isEqualTo(1) }
    }

    private fun fixture(status: DownloadStatus, progress: Int = 0): Download = Download(
        packageName = "com.aurora.r1f.fixture",
        versionCode = 42L,
        offerType = 0,
        isInstalled = false,
        displayName = "R1F Download UX Fixture",
        iconURL = "",
        size = 8192L,
        id = 0,
        status = status,
        progress = progress,
        speed = 0L,
        timeRemaining = 0L,
        totalFiles = 1,
        downloadedFiles = 0,
        fileList = emptyList(),
        sharedLibs = emptyList(),
        downloadedAt = 1000L
    )

    private fun screenshot(filename: String) {
        val bitmap = composeTestRule.onRoot().captureToImage().asAndroidBitmap()
        val out = File(context.filesDir, filename)
        FileOutputStream(out).use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        assertThat(out.length()).isGreaterThan(100L)
    }
}
