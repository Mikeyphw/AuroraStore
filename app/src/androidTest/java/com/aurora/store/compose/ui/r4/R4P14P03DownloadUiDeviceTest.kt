/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.compose.ui.r4

import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
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
import org.junit.Test
import org.junit.runner.RunWith

/** Real download UI on GitHub API36; use R4's bounded compositor screenshot guard. */
@RunWith(AndroidJUnit4::class)
class R4P14P03DownloadUiDeviceTest : IsolatedTest() {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext

    private fun fixture(status: DownloadStatus, progress: Int = 0): Download = Download(
        packageName = "com.aurora.p14p03.ui.fixture",
        versionCode = 45L, offerType = 0, isInstalled = false,
        displayName = "P14 Download UI Fixture", iconURL = "", size = 8192L,
        id = 145, status = status, progress = progress, speed = 0L,
        timeRemaining = 0L, totalFiles = 1, downloadedFiles = 0,
        fileList = emptyList(), sharedLibs = emptyList(), downloadedAt = 1403000L
    )

    private fun screenshot(filename: String) =
        R4ScreenshotEvidence.capture(context, filename) { composeTestRule.waitForIdle() }

    @Test
    fun queuedStatusHasNoInventedProgressOrSpeed() {
        setContent { DownloadListItem(download = fixture(DownloadStatus.QUEUED)) }
        composeTestRule.onNodeWithText(context.getString(R.string.status_queued)).assertExists()
        composeTestRule.onNodeWithText("0%", substring = true).assertDoesNotExist()
        composeTestRule.onNodeWithText("0 B/s", substring = true).assertDoesNotExist()
        screenshot("r4_p14p03_queued.png")
    }

    @Test
    fun activeTransferDisplaysActualProgressWithoutFakeSpeed() {
        setContent { DownloadListItem(download = fixture(DownloadStatus.DOWNLOADING, 45)) }
        composeTestRule.onNodeWithText("45%", substring = true).assertExists()
        composeTestRule.onNodeWithText("0 B/s", substring = true).assertDoesNotExist()
        screenshot("r4_p14p03_downloading.png")
    }

    @Test
    fun failedTransferDisplaysCorrectFailureStatus() {
        setContent { DownloadListItem(download = fixture(DownloadStatus.FAILED)) }
        composeTestRule.onNodeWithContentDescription(context.getString(R.string.status_failed))
            .assertExists()
        screenshot("r4_p14p03_failed.png")
    }

    @Test
    fun failedTransferRetryActionInvokesProductionCallback() {
        var retries = 0
        setContent {
            DownloadActionsSheet(
                download = fixture(DownloadStatus.FAILED),
                onDismiss = {}, onShowDetails = {}, onCancel = {},
                onRetry = { retries++ }, onInstall = {}, onExport = {}, onClear = {}
            )
        }
        composeTestRule.onNodeWithText(context.getString(R.string.r1f_download_retry))
            .assertExists().performClick()
        composeTestRule.runOnIdle { assertThat(retries).isEqualTo(1) }
    }
}
