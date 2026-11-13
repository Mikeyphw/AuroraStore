/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.compose.ui.r4

import android.content.Intent
import androidx.compose.ui.test.junit4.createEmptyComposeRule
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
            composeRule.onNodeWithContentDescription(context.getString(R.string.title_more))
                .performClick()
            expect(context.getString(R.string.title_settings))
            shot("r4_activity_more_sheet.png")
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
