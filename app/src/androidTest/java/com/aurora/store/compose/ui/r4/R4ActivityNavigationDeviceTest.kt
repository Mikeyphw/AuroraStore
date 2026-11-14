/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.compose.ui.r4

import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color
import android.os.SystemClock
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.work.Configuration
import androidx.work.WorkManager
import com.aurora.store.ComposeActivity
import com.aurora.store.R
import com.aurora.store.compose.navigation.Screen
import dagger.hilt.android.testing.HiltAndroidRule
import dagger.hilt.android.testing.HiltAndroidTest
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import kotlin.math.abs
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Real ComposeActivity + production Navigation3. No alternate test-only route or Play login. */
@HiltAndroidTest
@RunWith(AndroidJUnit4::class)
class R4ActivityNavigationDeviceTest {
    @get:Rule(order = 0) val hiltRule = HiltAndroidRule(this)
    @get:Rule(order = 1) val composeRule = createEmptyComposeRule()

    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext

    @Before
    fun setUp() {
        hiltRule.inject()
        // HiltTestApplication replaces AuroraApp, so the production
        // Configuration.Provider is intentionally absent in instrumentation.
        // Initialize the real WorkManager before any MainScreen ViewModel
        // constructs UpdateHelper; do not change the production manifest.
        try {
            WorkManager.getInstance(context)
        } catch (_: IllegalStateException) {
            WorkManager.initialize(context, Configuration.Builder().build())
        }
        checkNotNull(WorkManager.getInstance(context)) {
            "R4_WORK_MANAGER_TEST_INITIALIZATION_FAILED"
        }
    }

    private fun launch(screen: Screen): ActivityScenario<ComposeActivity> {
        val intent = Intent(context, ComposeActivity::class.java).apply {
            putExtra(Screen.PARCEL_KEY, screen)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
        }
        return ActivityScenario.launch(intent)
    }

    private fun expect(text: String) {
        composeRule.waitUntil(timeoutMillis = 20_000L) {
            composeRule.onAllNodesWithText(text, substring = false)
                .fetchSemanticsNodes().isNotEmpty()
        }
        check(composeRule.onAllNodesWithText(text).fetchSemanticsNodes().isNotEmpty()) {
            "R4_ACTIVITY_EXPECTED_LABEL_MISSING: $text"
        }
    }

    private fun shot(name: String) = R4ScreenshotEvidence.capture(context, name) {
        composeRule.waitForIdle()
    }

    /**
     * A Compose semantics assertion is not proof of a frame painted by Android's
     * compositor. ModalBottomSheet is a separate dialog window; right after the
     * click UiAutomation may return the previous fully-rendered Main frame.
     * Require an actual large change in the lower body, not a hash difference
     * caused by a clock, shimmer or Android status icon. No Play calls or writes.
     */
    private fun changedModalBodySamples(before: Bitmap, after: Bitmap): Int {
        check(before.width == after.width && before.height == after.height) {
            "R4_MORE_SCREENSHOT_DISPLAY_CHANGED"
        }
        val w = before.width
        val h = before.height
        var changed = 0
        for (y in (h * 38 / 100) until (h * 91 / 100) step 12) {
            for (x in (w / 9) until (w * 8 / 9) step 12) {
                val a = before.getPixel(x, y)
                val b = after.getPixel(x, y)
                if (abs(Color.red(a) - Color.red(b)) +
                    abs(Color.green(a) - Color.green(b)) +
                    abs(Color.blue(a) - Color.blue(b)) >= 72
                ) changed++
            }
        }
        return changed
    }

    /** Screen-compositor fallback, read-only binary stdout; no public storage. */
    private fun shellScreenFrame(): Bitmap? {
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        return runCatching {
            automation.executeShellCommand("screencap -p").use { descriptor ->
                FileInputStream(descriptor.fileDescriptor).use { stream ->
                    BitmapFactory.decodeStream(stream)
                }
            }
        }.getOrNull()
    }

    private fun captureVisiblyDrawnMoreSheet(before: Bitmap) {
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        val filename = "r4_activity_more_sheet.png"
        val output = File(context.filesDir, filename)
        var maximumChange = 0
        var nullCaptures = 0
        // Eight UIAutomation frames, then four fixed-command shell screencaps.
        // Never manufacture a screenshot or weaken the strict PNG auditor.
        for (attempt in 1..12) {
            composeRule.waitForIdle()
            val frame = if (attempt <= 8) automation.takeScreenshot() else shellScreenFrame()
            if (frame == null) {
                nullCaptures++
            } else {
                try {
                    val changed = changedModalBodySamples(before, frame)
                    maximumChange = maxOf(maximumChange, changed)
                    if (changed >= 200) {
                        FileOutputStream(output).use { stream ->
                            check(frame.compress(Bitmap.CompressFormat.PNG, 100, stream)) {
                                "R4_MORE_SCREENSHOT_ENCODE_FAILED"
                            }
                        }
                        check(output.length() > 2048L) { "R4_MORE_SCREENSHOT_EMPTY" }
                        return
                    }
                } finally {
                    frame.recycle()
                }
            }
            if (attempt < 12) SystemClock.sleep(350)
        }
        error("R4_MORE_SHEET_NOT_PAINTED_AFTER_12_FRAMES changed=$maximumChange null=$nullCaptures")
    }

    @Test
    fun realSettingsNavigatesToUiPreferencesAndRetainsR3dImport() {
        launch(Screen.Settings).use {
            expect("Import and verify APKs")
            shot("r4_activity_settings.png")
            composeRule.onNodeWithText(context.getString(R.string.pref_ui_title))
                .performScrollTo().performClick()
            expect(context.getString(R.string.pref_ui_theme))
            composeRule.onNodeWithText("Import and verify APKs").assertDoesNotExist()
            shot("r4_activity_ui_preferences.png")
        }
    }

    @Test
    fun realMainMoreSheetNavigatesToSettingsViaActualTap() {
        // Follow the user's production route. A deep-link directly to Settings
        // does not exercise the expressive More sheet or its navigation wiring.
        launch(Screen.Main(initialTab = 0)).use {
            expect(context.getString(R.string.title_apps))
            composeRule.waitForIdle()
            val before = checkNotNull(
                InstrumentationRegistry.getInstrumentation().uiAutomation.takeScreenshot()
            ) { "R4_MORE_BASELINE_SCREENSHOT_NULL" }
            try {
                composeRule.onNodeWithContentDescription(context.getString(R.string.title_more))
                    .performClick()
                expect(context.getString(R.string.title_settings))
                composeRule.onNodeWithText(context.getString(R.string.title_settings))
                    .assertIsDisplayed()
                captureVisiblyDrawnMoreSheet(before)
            } finally {
                before.recycle()
            }
            composeRule.onNodeWithText(context.getString(R.string.title_settings))
                .performClick()
            expect("Import and verify APKs")
            composeRule.onNodeWithText(context.getString(R.string.pref_ui_title)).assertExists()
        }
    }

    @Test
    fun realMainShowsExpressiveTabNavigationWithoutPlayAccount() {
        launch(Screen.Main(initialTab = 0)).use {
            expect(context.getString(R.string.title_apps))
            shot("r4_activity_main.png")
        }
    }

    @Test
    fun realSearchShowsSearchInputWithoutPerformingNetworkQuery() {
        launch(Screen.Search()).use {
            expect(context.getString(R.string.search_hint))
            shot("r4_activity_search.png")
        }
    }

    @Test
    fun realDownloadsShowsOfflineDownloadNavigation() {
        launch(Screen.Downloads).use {
            expect(context.getString(R.string.title_download_manager))
            shot("r4_activity_downloads.png")
        }
    }

    @Test
    fun realMainUpdatesTabRendersWithoutInstallingAnything() {
        launch(Screen.Main(initialTab = 2)).use {
            expect(context.getString(R.string.title_updates))
            shot("r4_activity_updates.png")
        }
    }
}
