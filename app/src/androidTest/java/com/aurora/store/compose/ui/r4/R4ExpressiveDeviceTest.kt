/*
 * SPDX-FileCopyrightText: 2026 Aurora OSS
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.compose.ui.r4

import android.graphics.Bitmap
import androidx.compose.material3.Text
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.aurora.store.IsolatedTest
import com.aurora.store.R
import com.aurora.store.compose.composable.ExpressiveCheckableMenuItem
import com.aurora.store.compose.composable.ExpressiveMenuGroup
import com.aurora.store.compose.composable.ExpressiveMenuPopup
import com.aurora.store.compose.composable.ExpressiveSelectableMenuItem
import com.aurora.store.compose.composable.app.AppUpdateItem
import com.aurora.store.compose.navigation.Destination
import com.aurora.store.compose.ui.preferences.SettingsScreen
import com.aurora.store.data.model.DownloadStatus
import com.aurora.store.data.room.download.Download
import com.aurora.store.data.room.update.Update
import com.google.common.truth.Truth.assertThat
import java.io.File
import java.io.FileOutputStream
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Real device-rendered Material3 Expressive UI with synthetic account-free fixtures.
 * No Google Play requests, privileged installation or external APKs are used here.
 */
@RunWith(AndroidJUnit4::class)
class R4ExpressiveDeviceTest : IsolatedTest() {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext

    @Test
    fun settingsPreserveR3dArtifactEntryAndNavigateToUiPreferences() {
        var destination: Destination? = null
        setContent { SettingsScreen(onNavigateTo = { destination = it }) }
        composeTestRule.onNodeWithText("Import and verify APKs").assertExists()
        screenshot("r4_settings.png")
        composeTestRule.onNodeWithText(context.getString(R.string.pref_ui_title))
            .performScrollTo()
            .performClick()
        composeTestRule.runOnIdle {
            assertThat(destination).isEqualTo(Destination.UIPreference)
        }
    }

    @Test
    fun updateRowInvokesUpdateWithoutCallingCancellation() {
        var updates = 0
        var cancels = 0
        setContent {
            AppUpdateItem(
                update = updateFixture(),
                onUpdate = { updates++ },
                onCancel = { cancels++ }
            )
        }
        composeTestRule.onNodeWithText(context.getString(R.string.action_update)).assertExists()
        composeTestRule.onNodeWithText(context.getString(R.string.action_cancel)).assertDoesNotExist()
        screenshot("r4_update_idle.png")
        composeTestRule.onNodeWithText(context.getString(R.string.action_update)).performClick()
        composeTestRule.runOnIdle {
            assertThat(updates).isEqualTo(1)
            assertThat(cancels).isEqualTo(0)
        }
    }

    @Test
    fun verifyingUpdateCanBeCancelledWithoutLaunchingInstall() {
        val update = updateFixture()
        var updates = 0
        var cancels = 0
        setContent {
            AppUpdateItem(
                update = update,
                download = Download.fromUpdate(update).copy(status = DownloadStatus.VERIFYING),
                onUpdate = { updates++ },
                onCancel = { cancels++ }
            )
        }
        composeTestRule.onNodeWithText(context.getString(R.string.action_cancel)).assertExists()
        composeTestRule.onNodeWithText(context.getString(R.string.action_update)).assertDoesNotExist()
        screenshot("r4_update_verifying.png")
        composeTestRule.onNodeWithText(context.getString(R.string.action_cancel)).performClick()
        composeTestRule.runOnIdle {
            assertThat(cancels).isEqualTo(1)
            assertThat(updates).isEqualTo(0)
        }
    }

    @Test
    fun installingUpdateDoesNotOfferCancellationOrNewUpdate() {
        val update = updateFixture()
        setContent {
            AppUpdateItem(
                update = update,
                download = Download.fromUpdate(update).copy(status = DownloadStatus.INSTALLING)
            )
        }
        composeTestRule.onNodeWithText(context.getString(R.string.action_installing)).assertExists()
        composeTestRule.onNodeWithText(context.getString(R.string.action_cancel)).assertDoesNotExist()
        composeTestRule.onNodeWithText(context.getString(R.string.action_update)).assertDoesNotExist()
        screenshot("r4_update_installing.png")
    }

    @Test
    fun expressiveMenuKeepsSelectedAndCheckedCallbacks() {
        var selectedActions = 0
        var toggles = 0
        var lastToggle: Boolean? = null
        setContent {
            ExpressiveMenuPopup(expanded = true, onDismissRequest = {}) {
                ExpressiveMenuGroup(index = 0, count = 1) {
                    ExpressiveSelectableMenuItem(
                        index = 0,
                        count = 2,
                        selected = true,
                        text = { Text("R4 Selected Item") },
                        onClick = { selectedActions++ }
                    )
                    ExpressiveCheckableMenuItem(
                        index = 1,
                        count = 2,
                        checked = true,
                        text = { Text("R4 Checked Item") },
                        onCheckedChange = { value ->
                            lastToggle = value
                            toggles++
                        }
                    )
                }
            }
        }
        composeTestRule.onNodeWithText("R4 Selected Item").assertExists()
        composeTestRule.onNodeWithText("R4 Checked Item").assertExists()
        screenshot("r4_expressive_menu.png")
        composeTestRule.onNodeWithText("R4 Selected Item").performClick()
        composeTestRule.onNodeWithText("R4 Checked Item").performClick()
        composeTestRule.runOnIdle {
            assertThat(selectedActions).isEqualTo(1)
            assertThat(toggles).isEqualTo(1)
            assertThat(lastToggle).isFalse()
        }
    }

    private fun updateFixture(): Update = Update(
        packageName = "com.aurora.r4.fixture",
        versionCode = 42L,
        versionName = "4.2",
        displayName = "R4 Offline Update",
        iconURL = "",
        changelog = "Offline fixture - no Play account",
        id = 42,
        developerName = "Aurora R4 QA",
        size = 4096L,
        updatedOn = "November 2026",
        hasValidCert = true,
        offerType = 1,
        fileList = emptyList(),
        sharedLibs = emptyList()
    )

    private fun screenshot(name: String) {
        composeTestRule.waitForIdle()
        val bitmap = checkNotNull(
            InstrumentationRegistry.getInstrumentation().uiAutomation.takeScreenshot()
        ) { "R4_SCREENSHOT_NULL $name" }
        check(bitmap.width >= 320 && bitmap.height >= 480) {
            "R4_SCREENSHOT_BAD_DIMENSIONS $name ${bitmap.width}x${bitmap.height}"
        }
        val destination = File(context.filesDir, name)
        FileOutputStream(destination).use {
            check(bitmap.compress(Bitmap.CompressFormat.PNG, 100, it)) {
                "R4_SCREENSHOT_ENCODE_FAILED $name"
            }
        }
        check(destination.length() > 2048L) { "R4_SCREENSHOT_MISSING_OR_EMPTY $name" }
    }
}
