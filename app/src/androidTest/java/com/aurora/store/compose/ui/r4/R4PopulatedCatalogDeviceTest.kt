/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.compose.ui.r4

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.unit.dp
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.aurora.gplayapi.model.App
import com.aurora.gplayapi.model.Artwork
import com.aurora.gplayapi.model.Category
import com.aurora.gplayapi.model.StreamCluster
import com.aurora.gplayapi.model.StreamBundle
import com.aurora.store.IsolatedTest
import com.aurora.store.R
import com.aurora.store.compose.composable.StreamCarousel
import com.aurora.store.compose.composable.SectionHeader
import com.aurora.store.compose.composable.app.AppUpdateItem
import com.aurora.store.compose.preview.AppPreviewProvider
import com.aurora.store.compose.ui.apps.CategoriesBody
import com.aurora.store.compose.ui.apps.TopChartsBody
import com.aurora.store.compose.ui.details.composable.Actions
import com.aurora.store.compose.ui.details.composable.Details
import com.aurora.store.compose.ui.details.composable.DetailsPortalCard
import com.aurora.store.compose.ui.search.SearchResultListItem
import com.aurora.store.data.model.DownloadStatus
import com.aurora.store.data.model.ViewState
import com.aurora.store.data.room.download.Download
import com.aurora.store.data.room.update.Update
import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Render real Aurora production composables with fixed, network-free models.
 * This is not a logged-in catalog, a Play search result, or end-to-end navigation.
 * No fake screenshot bitmaps, APK writes, live repositories, or installers.
 */
@RunWith(AndroidJUnit4::class)
class R4PopulatedCatalogDeviceTest : IsolatedTest() {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext

    private fun fixtureApps(): List<App> {
        val sample = AppPreviewProvider().values.first()
        return listOf("P12 Offline Atlas", "P12 Offline Beacon", "P12 Offline Cedar").mapIndexed { index, title ->
            sample.copy(
                id = 7001 + index,
                packageName = "invalid.aurora.p12.fixture$index",
                displayName = title,
                developerName = "P12 Local Fixture",
                isInstalled = false,
                isFree = true,
                containsAds = false,
                iconArtwork = Artwork(url = "")
            )
        }
    }

    private fun updateFixture() = Update(
        packageName = "invalid.aurora.p12.update",
        versionCode = 42L,
        versionName = "4.2",
        displayName = "P12 Offline Update",
        iconURL = "",
        changelog = "Synthetic only - no network or APK",
        id = 42,
        developerName = "P12 Local Fixture",
        size = 4096L,
        updatedOn = "November 2026",
        hasValidCert = true,
        offerType = 1,
        fileList = emptyList(),
        sharedLibs = emptyList()
    )

    private fun rendered(content: @Composable () -> Unit) {
        setContent {
            Surface(modifier = Modifier.fillMaxSize()) {
                Column(modifier = Modifier.fillMaxSize().statusBarsPadding()) {
                    content()
                }
            }
        }
    }

    private fun capture(name: String) {
        R4ScreenshotEvidence.capture(context, name) { composeTestRule.waitForIdle() }
    }

    @Test
    fun populatedForYouUsesRealHomeCardAndAction() {
        val apps = fixtureApps()
        var actionCount = 0
        rendered {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                SectionHeader(title = "P12 For You offline")
                StreamCarousel(
                    streamBundle = StreamBundle(
                        id = "p12-home",
                        clusters = listOf(
                            StreamCluster(id = "p12-featured", title = "P12 Featured", apps = apps),
                            StreamCluster(id = "p12-popular", title = "P12 Popular", apps = apps.reversed())
                        )
                    ),
                    showHomeActions = true,
                    onAppAction = { actionCount++ }
                )
            }
        }
        // Both carousel clusters intentionally reuse these offline fixture cards.
        composeTestRule.onAllNodesWithText("P12 Offline Atlas").assertCountEquals(2)
        composeTestRule.onAllNodesWithText("P12 Offline Beacon").assertCountEquals(2)
        capture("r4_populated_for_you.png")
        composeTestRule.onAllNodesWithText(context.getString(R.string.action_install))
            .get(0).performClick()
        composeTestRule.runOnIdle { assertThat(actionCount).isEqualTo(1) }
    }

    @Test
    fun populatedSearchRendersProductionResultRows() {
        val apps = fixtureApps()
        var clicked = ""
        rendered {
            Column {
                SectionHeader(title = "P12 Search offline")
                LazyColumn {
                    items(apps, key = { it.packageName }) { app ->
                        SearchResultListItem(app = app, onClick = { clicked = app.packageName })
                    }
                }
            }
        }
        composeTestRule.onNodeWithText("P12 Offline Atlas").assertExists()
        composeTestRule.onNodeWithText("P12 Offline Beacon").assertExists()
        capture("r4_populated_search.png")
        composeTestRule.onNodeWithText("P12 Offline Atlas").performClick()
        composeTestRule.runOnIdle { assertThat(clicked).isEqualTo(apps[0].packageName) }
    }

    @Test
    fun populatedDetailsShowsRealDetailsAndInstallButtons() {
        val app = fixtureApps()[0]
        var installs = 0
        var detailsClicks = 0
        rendered {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Details(app = app)
                Actions(
                    primaryActionDisplayName = context.getString(R.string.action_install),
                    secondaryActionDisplayName = context.getString(R.string.title_manual_download),
                    onPrimaryAction = { installs++ }
                )
                DetailsPortalCard(
                    title = "P12 Offline Details",
                    description = "Production details portal, synthetic app metadata",
                    icon = painterResource(R.drawable.ic_apps),
                    onClick = { detailsClicks++ }
                )
            }
        }
        composeTestRule.onNodeWithText("P12 Offline Atlas").assertExists()
        composeTestRule.onNodeWithText("P12 Offline Details").assertExists()
        capture("r4_populated_details.png")
        composeTestRule.onNodeWithText(context.getString(R.string.action_install)).performClick()
        composeTestRule.onNodeWithText("P12 Offline Details").performClick()
        composeTestRule.runOnIdle {
            assertThat(installs).isEqualTo(1)
            assertThat(detailsClicks).isEqualTo(1)
        }
    }

    @Test
    fun populatedTopChartsUsesRealRankedList() {
        val apps = fixtureApps()
        val cluster = StreamCluster(id = "p12-charts", title = "Offline Top Charts", apps = apps)
        var clicked = ""
        rendered {
            Column {
                SectionHeader(title = "P12 Top Charts offline")
                TopChartsBody(
                    state = ViewState.Success(cluster),
                    cluster = cluster,
                    bottomContentPadding = 0.dp,
                    onAppClick = { clicked = it.packageName }
                )
            }
        }
        composeTestRule.onNodeWithText("P12 Offline Atlas").assertExists()
        composeTestRule.onNodeWithText("P12 Offline Beacon").assertExists()
        capture("r4_populated_charts.png")
        composeTestRule.onNodeWithText("P12 Offline Atlas").performClick()
        composeTestRule.runOnIdle { assertThat(clicked).isEqualTo(apps[0].packageName) }
    }

    @Test
    fun populatedCategoriesUsesRealCategoryBody() {
        val categories = listOf("P12 Art", "P12 Business", "P12 Education", "P12 Games")
            .map { Category(title = it, imageUrl = "") }
        var clicked = ""
        rendered {
            Column {
                SectionHeader(title = "P12 Categories offline")
                CategoriesBody(list = categories, onCategoryClick = { clicked = it.title })
            }
        }
        composeTestRule.onNodeWithText("P12 Art").assertExists()
        composeTestRule.onNodeWithText("P12 Business").assertExists()
        capture("r4_populated_categories.png")
        composeTestRule.onNodeWithText("P12 Art").performClick()
        composeTestRule.runOnIdle { assertThat(clicked).isEqualTo("P12 Art") }
    }

    @Test
    fun populatedInstallControlsRetainSyntheticUpdateCancelBehavior() {
        val update = updateFixture()
        var updates = 0
        var cancellations = 0
        rendered {
            Column(modifier = Modifier.padding(top = 8.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                SectionHeader(title = "P12 Install controls offline")
                AppUpdateItem(update = update, onUpdate = { updates++ })
                AppUpdateItem(
                    update = update.copy(
                        packageName = "invalid.aurora.p12.verifying",
                        displayName = "P12 Verifying"
                    ),
                    download = Download.fromUpdate(update).copy(status = DownloadStatus.VERIFYING),
                    onCancel = { cancellations++ }
                )
            }
        }
        composeTestRule.onNodeWithText(context.getString(R.string.action_update)).assertExists()
        composeTestRule.onNodeWithText(context.getString(R.string.action_cancel)).assertExists()
        capture("r4_populated_install_controls.png")
        composeTestRule.onNodeWithText(context.getString(R.string.action_update)).performClick()
        composeTestRule.onNodeWithText(context.getString(R.string.action_cancel)).performClick()
        composeTestRule.runOnIdle {
            assertThat(updates).isEqualTo(1)
            assertThat(cancellations).isEqualTo(1)
        }
    }
}
