/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.compose.ui.r4

import android.content.Intent
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

    private fun capture(filename: String) =
        R4ScreenshotEvidence.capture(context, filename) { composeRule.waitForIdle() }

    @Test
    fun actualMainSearchButtonNavigatesToSearchAndReturns() {
        launchMain().use {
            expect(context.getString(R.string.title_apps))
            composeRule.onNodeWithContentDescription(context.getString(R.string.action_search))
                .performClick()
            expect(context.getString(R.string.search_hint))
            capture("r4_p13b_nav_search.png")
            composeRule.onNodeWithContentDescription(context.getString(R.string.action_back))
                .performClick()
            expect(context.getString(R.string.title_apps))
            capture("r4_p13b_nav_return.png")
        }
    }

    @Test
    fun actualMainMoreSettingsAndCustomizationRoute() {
        launchMain().use {
            expect(context.getString(R.string.title_apps))
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
