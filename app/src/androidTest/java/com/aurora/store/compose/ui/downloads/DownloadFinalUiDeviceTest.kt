/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.compose.ui.downloads

import android.graphics.Bitmap
import androidx.compose.runtime.Composable
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
import java.io.File
import java.io.FileOutputStream
import org.junit.Test
import org.junit.runner.RunWith

/** Final real Compose/semantics acceptance; synthetic rows, no Play or installation. */
@RunWith(AndroidJUnit4::class)
class DownloadFinalUiDeviceTest : IsolatedTest() {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext

    @Test
    fun verifyingDownloadStillAllowsCancellation() {
        var cancellations = 0
        setContent {
            actions(
                download = fixture(DownloadStatus.VERIFYING),
                onCancel = { cancellations++ }
            )
        }
        composeTestRule.onNodeWithText(context.getString(R.string.action_cancel))
            .assertExists()
            .performClick()
        composeTestRule.runOnIdle { assertThat(cancellations).isEqualTo(1) }
    }

    @Test
    fun missingCachedApkShowsRetryWithoutInstallation() {
        var retries = 0
        setContent {
            actions(
                download = fixture(DownloadStatus.AWAITING_INSTALL),
                onRetry = { retries++ }
            )
        }
        composeTestRule.onNodeWithText(context.getString(R.string.r1f_download_retry))
            .assertExists()
        composeTestRule.onNodeWithText(context.getString(R.string.action_install))
            .assertDoesNotExist()
        screenshot("r1g_awaiting_retry.png")
        composeTestRule.onNodeWithText(context.getString(R.string.r1f_download_retry))
            .performClick()
        composeTestRule.runOnIdle { assertThat(retries).isEqualTo(1) }
    }

    @Test
    fun installingDoesNotExposeCancelOrRetry() {
        setContent { actions(download = fixture(DownloadStatus.INSTALLING)) }
        composeTestRule.onNodeWithText(context.getString(R.string.action_cancel))
            .assertDoesNotExist()
        composeTestRule.onNodeWithText(context.getString(R.string.r1f_download_retry))
            .assertDoesNotExist()
    }

    @Test
    fun cancelledShowsAccurateStatusWithoutFakeTransferStats() {
        setContent { DownloadListItem(download = fixture(DownloadStatus.CANCELLED)) }
        composeTestRule.onNodeWithText(context.getString(R.string.status_cancelled))
            .assertExists()
        composeTestRule.onNodeWithText("0 B/s", substring = true).assertDoesNotExist()
        composeTestRule.onNodeWithText("0%", substring = true).assertDoesNotExist()
        screenshot("r1g_cancelled.png")
    }

    @Composable
    private fun actions(download: Download, onCancel: () -> Unit = {}, onRetry: () -> Unit = {}) {
        DownloadActionsSheet(
            download = download,
            onDismiss = {},
            onShowDetails = {},
            onCancel = onCancel,
            onRetry = onRetry,
            onInstall = {},
            onExport = {},
            onClear = {}
        )
    }

    private fun fixture(status: DownloadStatus): Download = Download(
        packageName = "com.aurora.r1g.fixture",
        versionCode = 42L,
        offerType = 0,
        isInstalled = false,
        displayName = "R1G Download Acceptance Fixture",
        iconURL = "",
        size = 8192L,
        id = 0,
        status = status,
        progress = 0,
        speed = 0L,
        timeRemaining = 0L,
        totalFiles = 1,
        downloadedFiles = 0,
        fileList = emptyList(),
        sharedLibs = emptyList(),
        downloadedAt = 1001L
    )

    private fun screenshot(filename: String) {
        // Keep the real Compose assertions and idle synchronization, but avoid
        // captureToImage()'s intermittent Android 16 forceRedraw timeout.
        composeTestRule.waitForIdle()
        val bitmap = checkNotNull(InstrumentationRegistry.getInstrumentation().uiAutomation.takeScreenshot()) {
            "Device display screenshot unavailable: $filename"
        }
        val file = File(context.filesDir, filename)
        FileOutputStream(file).use { stream ->
            check(bitmap.compress(Bitmap.CompressFormat.PNG, 100, stream)) {
                "PNG encoding failed for $filename"
            }
        }
        assertThat(file.length()).isGreaterThan(100L)
    }
}
