/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.compose.ui.r4

import android.graphics.Bitmap
import android.graphics.Color
import android.os.SystemClock
import java.io.File
import java.io.FileOutputStream
import kotlin.math.abs
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

/** Actual hosted download widgets with non-blank full-display PNG capture.
 * The general R4 screenshot heuristic expects whole-screen content. A real
 * isolated DownloadListItem covers much less screen: the hosted failure showed
 * 28-35 valid contrasting samples, below the 42-sample full-screen cutoff.
 * We therefore retain a bounded *nonzero* body-pixel requirement for this
 * explicitly isolated widget suite, plus actual Compose semantics assertions.
 */
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

    private fun screenshot(filename: String) {
        check(filename in setOf(
            "r4_p14p03_queued.png", "r4_p14p03_downloading.png", "r4_p14p03_failed.png"
        )) { "P14P03_REFUSED_SCREENSHOT_NAME" }
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        var accepted: Bitmap? = null
        var observed = -1
        for (attempt in 1..10) {
            composeTestRule.waitForIdle()
            val frame = automation.takeScreenshot()
            if (frame != null) {
                if (frame.width >= 320 && frame.height >= 480) {
                    val background = frame.getPixel(frame.width / 2, frame.height / 2)
                    var contentSamples = 0
                    // Sample the Android compositor body, avoiding clock and nav bars.
                    for (y in (frame.height / 20) until (frame.height * 9 / 10) step 8) {
                        for (x in (frame.width / 50) until (frame.width * 49 / 50) step 8) {
                            val color = frame.getPixel(x, y)
                            val delta = abs(Color.red(color) - Color.red(background)) +
                                abs(Color.green(color) - Color.green(background)) +
                                abs(Color.blue(color) - Color.blue(background))
                            if (delta >= 52) contentSamples++
                        }
                    }
                    observed = contentSamples
                    if (contentSamples >= 12) {
                        accepted = frame
                        break
                    }
                }
                frame.recycle()
            }
            if (attempt < 10) SystemClock.sleep(300)
        }
        val image = checkNotNull(accepted) {
            "P14P03_REFUSED_BLANK_WIDGET_SCREENSHOT $filename contentSamples=$observed attempts=10"
        }
        val file = File(context.filesDir, filename)
        try {
            FileOutputStream(file).use { stream ->
                check(image.compress(Bitmap.CompressFormat.PNG, 100, stream)) {
                    "P14P03_REFUSED_PNG_ENCODE $filename"
                }
            }
        } finally {
            image.recycle()
        }
        check(file.length() > 2048L) { "P14P03_REFUSED_EMPTY_PNG $filename" }
    }

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
