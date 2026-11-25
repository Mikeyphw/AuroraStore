/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.compose.ui.r4

import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color
import android.os.SystemClock
import java.io.File
import kotlin.math.abs
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithContentDescription
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
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Actual Hilt-backed ComposeActivity and production Navigation3 destinations.
 * No mocked NavHost, test-only navigation graph, Play session, online query or install.
 * The P13BIntegratedVisualDeviceTest separately covers offline populated components.
 */
@HiltAndroidTest
@RunWith(AndroidJUnit4::class)
class R4P13BProductionNav3DeviceTest {
    @get:Rule(order = 0) val hiltRule = HiltAndroidRule(this)
    @get:Rule(order = 1) val composeRule = createEmptyComposeRule()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext

    @Before
    fun initialize() {
        hiltRule.inject()
        try {
            WorkManager.getInstance(context)
        } catch (_: IllegalStateException) {
            WorkManager.initialize(context, Configuration.Builder().build())
        }
        checkNotNull(WorkManager.getInstance(context)) { "P13B_WORKMANAGER_MISSING" }
    }

    private fun launchMain(): ActivityScenario<ComposeActivity> =
        ActivityScenario.launch(Intent(context, ComposeActivity::class.java).apply {
            putExtra(Screen.PARCEL_KEY, Screen.Main(initialTab = 0))
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
        })

    private fun expect(label: String) {
        composeRule.waitUntil(timeoutMillis = 20_000L) {
            composeRule.onAllNodesWithText(label, substring = false)
                .fetchSemanticsNodes().isNotEmpty()
        }
        composeRule.onAllNodesWithText(label).get(0).assertExists()
    }

    private var previousBodySignature: IntArray? = null

    private fun bodySignature(bitmap: Bitmap): IntArray {
        // 25,600 representative compositor pixels; 6..94% high includes the
        // in-app title row that the old 13..78% 378-pixel grid entirely missed.
        // 5..95% wide excludes display edges but includes compact headers.
        val rows = 160
        val columns = 160
        val values = IntArray(rows * columns)
        var index = 0
        for (row in 0 until rows) {
            val y = (bitmap.height * (6 * rows + 88 * row) / (100 * rows))
                .coerceIn(0, bitmap.height - 1)
            for (column in 0 until columns) {
                val x = (bitmap.width * (5 * columns + 90 * column) / (100 * columns))
                    .coerceIn(0, bitmap.width - 1)
                values[index++] = bitmap.getPixel(x, y)
            }
        }
        return values
    }

    private fun changedBody(before: IntArray, after: IntArray): Int =
        before.indices.count { index ->
            val a = before[index]
            val b = after[index]
            abs(Color.red(a) - Color.red(b)) +
                abs(Color.green(a) - Color.green(b)) +
                abs(Color.blue(a) - Color.blue(b)) >= 32
        }

    private fun primeVisualBaseline() {
        composeRule.waitForIdle()
        val frame = checkNotNull(
            InstrumentationRegistry.getInstrumentation().uiAutomation.takeScreenshot()
        ) { "P13B_BASELINE_SCREENSHOT_NULL" }
        previousBodySignature = try { bodySignature(frame) } finally { frame.recycle() }
    }

    private fun capture(filename: String) {
        val prior = checkNotNull(previousBodySignature) { "P13B_BASELINE_NOT_INITIALIZED" }
        var observed = 0
        for (attempt in 1..12) {
            R4ScreenshotEvidence.capture(context, filename) { composeRule.waitForIdle() }
            val image = checkNotNull(BitmapFactory.decodeFile(
                File(context.filesDir, filename).absolutePath
            )) { "P13B_FRAME_DECODE_FAILED $filename" }
            val sample = try { bodySignature(image) } finally { image.recycle() }
            observed = changedBody(prior, sample)
            if (attempt == 1 || attempt == 12) {
                android.util.Log.i("P13BVisualEvidence",
                    "P13B_FRAME_READBACK file=$filename attempt=$attempt " +
                        "changedPixels=$observed required=12 sampleSize=${sample.size}")
            }
            if (observed >= 12) {
                previousBodySignature = sample
                return
            }
            if (attempt < 12) SystemClock.sleep(250)
        }
        error("P13B_REFUSED_STALE_BODY_FRAME $filename samples=$observed retries=12")
    }

    @Test
    fun actualMainSearchButtonNavigatesToSearchAndReturns() {
        launchMain().use {
            expect(context.getString(R.string.title_apps))
            primeVisualBaseline()
            composeRule.onNodeWithContentDescription(context.getString(R.string.action_search))
                .performClick()
            expect(context.getString(R.string.search_hint))
            capture("r4_p13b_nav_search.png")
            composeRule.onNodeWithContentDescription(context.getString(R.string.action_back))
                .performClick()
            expect(context.getString(R.string.title_apps))
            composeRule.waitUntil(timeoutMillis = 20_000L) {
                composeRule.onAllNodesWithText(context.getString(R.string.search_hint))
                    .fetchSemanticsNodes().isEmpty()
            }
            composeRule.onNodeWithContentDescription(context.getString(R.string.action_search))
                .assertExists()
            capture("r4_p13b_nav_return.png")
        }
    }

    @Test
    fun actualMainMoreSettingsAndCustomizationRoute() {
        launchMain().use {
            expect(context.getString(R.string.title_apps))
            primeVisualBaseline()
            composeRule.onNodeWithContentDescription(context.getString(R.string.title_more))
                .performClick()
            expect(context.getString(R.string.title_settings))
            composeRule.onNodeWithText(context.getString(R.string.title_settings))
                .performClick()
            expect("Import and verify APKs") // protected R3D action must survive
            capture("r4_p13b_nav_settings.png")
            composeRule.onNodeWithText(context.getString(R.string.pref_ui_title))
                .performScrollTo().performClick()
            expect(context.getString(R.string.pref_ui_theme))
            capture("r4_p13b_nav_preferences.png")
        }
    }
}
