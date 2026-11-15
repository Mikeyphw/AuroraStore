/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.compose.ui.r4

import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color
import android.os.SystemClock
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.hasClickAction
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.hasSetTextAction
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performImeAction
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.test.performScrollToIndex
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
import java.io.File
import kotlin.math.abs

/**
 * P14-P01: actual Android ComposeActivity and production Navigation3, offline only.
 * No mock navigator, Play sign-in, catalog query, APK install, account mutation or root.
 * P14-P02/P03 own the deferred data-backed and installer journeys.
 */
@HiltAndroidTest
@RunWith(AndroidJUnit4::class)
class R4P14OfflineNav3JourneyDeviceTest {
    @get:Rule(order = 0) val hiltRule = HiltAndroidRule(this)
    @get:Rule(order = 1) val composeRule = createEmptyComposeRule()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext

    @Before
    fun initialize() {
        hiltRule.inject()
        try { WorkManager.getInstance(context) }
        catch (_: IllegalStateException) {
            WorkManager.initialize(context, Configuration.Builder().build())
        }
        checkNotNull(WorkManager.getInstance(context)) { "P14_WORKMANAGER_MISSING" }
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
        check(composeRule.onAllNodesWithText(label).fetchSemanticsNodes().isNotEmpty()) {
            "P14_EXPECTED_LABEL_MISSING $label"
        }
    }

    // Android 16 UiAutomation can briefly return the previous painted frame.
    // Sample the body, not the changing status-bar clock; reject stale visuals.
    private var previousBodySignature: IntArray? = null

    private fun bodySignature(bitmap: Bitmap): IntArray {
        val values = IntArray(14 * 27)
        var index = 0
        for (row in 0 until 14) {
            val y = (bitmap.height * (13 + 5 * row) / 100).coerceIn(0, bitmap.height - 1)
            for (column in 0 until 27) {
                val x = (bitmap.width * (10 + 3 * column) / 100).coerceIn(0, bitmap.width - 1)
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
        ) { "P14_BASELINE_SCREENSHOT_NULL" }
        previousBodySignature = try { bodySignature(frame) } finally { frame.recycle() }
    }

    private fun capture(filename: String) {
        val prior = checkNotNull(previousBodySignature) { "P14_BASELINE_NOT_INITIALIZED" }
        var observed = 0
        for (attempt in 1..12) {
            R4ScreenshotEvidence.capture(context, filename) { composeRule.waitForIdle() }
            val image = checkNotNull(BitmapFactory.decodeFile(
                File(context.filesDir, filename).absolutePath
            )) { "P14_FRAME_DECODE_FAILED $filename" }
            val sample = try { bodySignature(image) } finally { image.recycle() }
            observed = changedBody(prior, sample)
            if (observed >= 12) {
                previousBodySignature = sample
                return
            }
            if (attempt < 12) SystemClock.sleep(250)
        }
        error("P14_REFUSED_STALE_BODY_FRAME $filename samples=$observed retries=12")
    }

    /** Match the *clickable selected tab*, not the duplicate app-bar heading. */
    private fun selectTab(label: String) {
        val node = composeRule.onAllNodes(hasText(label) and hasClickAction()).get(0)
        node.performClick()
        composeRule.waitUntil(timeoutMillis = 20_000L) {
            composeRule.onAllNodes(hasText(label) and hasClickAction())
                .fetchSemanticsNodes().any {
                    it.config.getOrNull(SemanticsProperties.Selected) == true
                }
        }
    }

    @Test
    fun realMainSearchBackThenDownloadsBack() {
        launchMain().use {
            expect(context.getString(R.string.title_apps))
            primeVisualBaseline()
            composeRule.onNodeWithContentDescription(context.getString(R.string.action_search))
                .performClick()
            expect(context.getString(R.string.search_hint))
            capture("r4_p14_search_route.png")
            composeRule.onNodeWithContentDescription(context.getString(R.string.action_back))
                .performClick()
            expect(context.getString(R.string.title_apps))
            composeRule.onNodeWithContentDescription(context.getString(R.string.title_download_manager))
                .performClick()
            expect(context.getString(R.string.title_download_manager))
            capture("r4_p14_downloads_route.png")
            composeRule.onNodeWithContentDescription(context.getString(R.string.action_back))
                .performClick()
            expect(context.getString(R.string.title_apps))
            composeRule.onNodeWithContentDescription(context.getString(R.string.action_search))
                .assertExists()
        }
    }

    @Test
    fun realMainSettingsPreferencesAndReverseBackstack() {
        launchMain().use {
            expect(context.getString(R.string.title_apps))
            primeVisualBaseline()
            composeRule.onNodeWithContentDescription(context.getString(R.string.title_more))
                .performClick()
            expect(context.getString(R.string.title_settings))
            composeRule.onNodeWithText(context.getString(R.string.title_settings))
                .performClick()
            expect("Import and verify APKs")
            capture("r4_p14_settings_route.png")
            composeRule.onNodeWithText(context.getString(R.string.pref_ui_title))
                .performScrollTo().performClick()
            expect(context.getString(R.string.pref_ui_theme))
            capture("r4_p14_preferences_route.png")
            composeRule.onNodeWithContentDescription(context.getString(R.string.action_back))
                .performClick()
            expect("Import and verify APKs")
            composeRule.onNodeWithContentDescription(context.getString(R.string.action_back))
                .performClick()
            expect(context.getString(R.string.title_apps))
        }
    }

    /** Actual Main Search overlay -> real SearchViewModel -> real AppDetailsViewModel.
     * Only the Hilt catalog gateway is swapped in androidTest; both screens and
     * the adaptive list/detail pane remain the production implementations.
     */
    @Test
    fun realSearchToFullDetailsHeaderArtworkAndReviews() {
        val priorSearches = P14HermeticCatalogGateway.searchCount.get()
        val priorDetails = P14HermeticCatalogGateway.detailsCount.get()
        val priorReviews = P14HermeticCatalogGateway.reviewCount.get()
        launchMain().use {
            expect(context.getString(R.string.title_apps))
            primeVisualBaseline()
            composeRule.onNodeWithContentDescription(context.getString(R.string.action_search))
                .performClick()
            expect(context.getString(R.string.search_hint))
            composeRule.onAllNodes(hasSetTextAction()).get(0).performTextInput("Atlas")
            composeRule.onAllNodes(hasSetTextAction()).get(0).performImeAction()
            expect("P14 Offline Atlas")
            check(P14HermeticCatalogGateway.searchCount.get() > priorSearches) {
                "P14_REFUSED_SEARCH_VIEWMODEL_NOT_EXERCISED"
            }
            capture("r4_p14_populated_search.png")
            composeRule.onNodeWithText("P14 Offline Atlas").performClick()
            composeRule.waitUntil(timeoutMillis = 20_000L) {
                composeRule.onAllNodesWithTag("aurora-details-main-list")
                    .fetchSemanticsNodes().isNotEmpty()
            }
            expect("P14 Offline Atlas")
            check(P14HermeticCatalogGateway.detailsCount.get() > priorDetails &&
                P14HermeticCatalogGateway.reviewCount.get() > priorReviews) {
                "P14_REFUSED_DETAILS_VIEWMODEL_OR_REVIEWS_NOT_EXERCISED"
            }
            capture("r4_p14_details_identity.png")
            composeRule.onNodeWithTag("aurora-details-main-list").performScrollToIndex(3)
            composeRule.onNodeWithTag("aurora-details-screenshots").assertExists()
            SystemClock.sleep(950) // local png inputs, no Play images
            capture("r4_p14_details_carousel.png")
            composeRule.onNodeWithTag("aurora-details-main-list").performScrollToIndex(5)
            composeRule.onNodeWithTag("aurora-details-reviews").assertExists()
            expect("P14 Offline Reviewer")
            capture("r4_p14_details_reviews.png")
        }
    }

    @Test
    fun realMainGamesUpdatesAppsRoundTripNoInstaller() {
        launchMain().use {
            expect(context.getString(R.string.title_apps))
            primeVisualBaseline()
            selectTab(context.getString(R.string.title_games))
            capture("r4_p14_games_tab.png")
            selectTab(context.getString(R.string.title_updates))
            capture("r4_p14_updates_tab.png")
            selectTab(context.getString(R.string.title_apps))
            composeRule.onNodeWithContentDescription(context.getString(R.string.action_search))
                .assertExists()
        }
    }
}
