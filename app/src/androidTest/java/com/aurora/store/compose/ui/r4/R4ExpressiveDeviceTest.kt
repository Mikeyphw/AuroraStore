/*
 * SPDX-FileCopyrightText: 2026 Aurora OSS
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.compose.ui.r4

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Modifier
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
        val update = updateFixture()
        val activeDownload = mutableStateOf<Download?>(null)
        setInsetContent {
            AppUpdateItem(
                update = update,
                download = activeDownload.value,
                onUpdate = {
                    updates++
                    // Offline visual fixture: show a real production update row's
                    // in-progress presentation, without starting Play/download work.
                    activeDownload.value = Download.fromUpdate(update).copy(
                        status = DownloadStatus.DOWNLOADING,
                        progress = 45
                    )
                },
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
        // The new state is distinct from the verified and installing captures.
        // An isolated Settings shot duplicated the actual activity Settings image.
        composeTestRule.onNodeWithText(context.getString(R.string.action_cancel)).assertExists()
        composeTestRule.onNodeWithText(context.getString(R.string.action_update)).assertDoesNotExist()
        screenshot("r4_update_downloading.png")
    }

    @Test
    fun verifyingUpdateCanBeCancelledWithoutLaunchingInstall() {
        val update = updateFixture()
        var updates = 0
        var cancels = 0
        setInsetContent {
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
        setInsetContent {
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
        // A full-screen Material Surface is required for faithful dark-mode
        // screenshots. AuroraTheme alone does not paint an isolated window.
        setInsetContent {
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

    // Component fixtures receive the insets their real Main/Downloads screens provide.
    // This prevents test-only rows from rendering underneath the system status bar.
    private fun setInsetContent(content: @Composable () -> Unit) {
        setContent {
            Surface(modifier = Modifier.fillMaxSize()) {
                Box(modifier = Modifier.fillMaxSize().statusBarsPadding()) {
                    content()
                }
            }
        }
    }

    private fun screenshot(name: String) {
        R4ScreenshotEvidence.capture(
            context = context,
            filename = name,
            waitForIdle = { composeTestRule.waitForIdle() }
        )
    }
}
