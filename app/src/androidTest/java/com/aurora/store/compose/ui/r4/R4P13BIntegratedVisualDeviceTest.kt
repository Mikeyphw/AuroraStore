/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.compose.ui.r4

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.os.SystemClock
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollToIndex
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.aurora.gplayapi.model.App
import com.aurora.gplayapi.model.Artwork
import com.aurora.gplayapi.model.Category
import com.aurora.gplayapi.model.Review
import com.aurora.gplayapi.model.StreamBundle
import com.aurora.gplayapi.model.StreamCluster
import com.aurora.store.IsolatedTest
import com.aurora.store.R
import com.aurora.store.compose.composable.SectionHeader
import com.aurora.store.compose.composable.StreamCarousel
import com.aurora.store.compose.preview.AppPreviewProvider
import com.aurora.store.compose.ui.apps.CategoriesBody
import com.aurora.store.compose.ui.apps.TopChartsBody
import com.aurora.store.compose.ui.details.composable.Actions
import com.aurora.store.compose.ui.details.composable.Details
import com.aurora.store.compose.ui.details.composable.DetailsPortalCard
import com.aurora.store.compose.ui.details.composable.RatingAndReviews
import com.aurora.store.compose.ui.details.composable.Screenshots
import com.aurora.store.compose.ui.search.SearchResultListItem
import com.aurora.store.data.model.ViewState
import com.google.common.truth.Truth.assertThat
import java.io.File
import java.io.FileOutputStream
import org.junit.Test
import org.junit.runner.RunWith

/**
 * P13-B hermetic component-integrated journeys, NOT production Navigation3,
 * authenticated catalog, Play search, real install or full upstream visual parity.
 * All displayed apps use .invalid packages; no installer/download APIs are invoked.
 * Rendered evidence is captured from the actual API36 emulator compositor.
 */
@RunWith(AndroidJUnit4::class)
class R4P13BIntegratedVisualDeviceTest : IsolatedTest() {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val apps: List<App> get() {
        val sample = AppPreviewProvider().values.first()
        return listOf("P13 Offline Atlas", "P13 Offline Beacon", "P13 Offline Cedar")
            .mapIndexed { i, name -> sample.copy(
                id = 13100 + i,
                packageName = "invalid.aurora.p13b.fixture$i",
                displayName = name,
                developerName = "P13 Hermetic Fixture",
                isInstalled = false,
                isFree = true,
                containsAds = false,
                iconArtwork = Artwork(url = "")
            ) }
    }
    private val categories = listOf("P13 Art", "P13 Business", "P13 Education", "P13 Games")
        .map { Category(title = it, imageUrl = "") }

    private fun render(content: @Composable () -> Unit) = setContent {
        Surface(modifier = Modifier.fillMaxSize()) {
            Column(modifier = Modifier.fillMaxSize().statusBarsPadding()) { content() }
        }
    }
    private fun shot(filename: String) {
        R4ScreenshotEvidence.capture(context, filename) { composeTestRule.waitForIdle() }
    }

    /** These three files are *input app artwork*, not evidence screenshots. */
    private fun offlineArtwork(): List<Artwork> = (0..2).map { index ->
        val file = File(context.filesDir, "p13b-input-art-$index.png=rw-w480-v1-e15")
        val bitmap = Bitmap.createBitmap(320, 560, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val paint = Paint(Paint.ANTI_ALIAS_FLAG)
        paint.color = listOf(Color.rgb(66, 91, 172), Color.rgb(57, 128, 114),
            Color.rgb(154, 83, 122))[index]
        canvas.drawColor(paint.color)
        paint.color = Color.WHITE
        paint.textSize = 38f
        canvas.drawText("P13 TEST", 46f, 180f, paint)
        paint.textSize = 26f
        canvas.drawText("Offline art ${index + 1}", 44f, 250f, paint)
        FileOutputStream(file).use { check(bitmap.compress(Bitmap.CompressFormat.PNG, 100, it)) }
        bitmap.recycle()
        check(file.length() > 2048L) { "P13B_OFFLINE_IMAGE_INPUT_MISSING" }
        Artwork(url = "file://" + File(context.filesDir, "p13b-input-art-$index.png").absolutePath)
    }

    @Test
    fun integratedHomeChartsCategoriesHaveSharedTabState() {
        val all = apps
        val cluster = StreamCluster(id = "p13b-chart", title = "P13 Ranked", apps = all)
        var actionCount = 0
        render {
            var tab by remember { mutableStateOf("Home") }
            Column(modifier = Modifier.fillMaxSize()) {
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp),
                    modifier = Modifier.padding(horizontal = 12.dp)) {
                    listOf("Home", "Charts", "Categories").forEach { name ->
                        FilterChip(selected = tab == name, onClick = { tab = name },
                            label = { Text("P13 $name") })
                    }
                }
                Box(modifier = Modifier.weight(1f)) {
                    when (tab) {
                        "Home" -> StreamCarousel(
                            streamBundle = StreamBundle(id = "p13b-home", clusters = listOf(
                                StreamCluster(id = "p13b-featured", title = "P13 Featured", apps = all),
                                StreamCluster(id = "p13b-popular", title = "P13 Popular", apps = all.reversed())
                            )), showHomeActions = true, onAppAction = { actionCount++ })
                        "Charts" -> TopChartsBody(
                            state = ViewState.Success(cluster), cluster = cluster,
                            bottomContentPadding = 0.dp)
                        else -> CategoriesBody(list = categories)
                    }
                }
            }
        }
        composeTestRule.onAllNodesWithText("P13 Offline Atlas").assertCountEquals(2)
        shot("r4_p13b_home.png")
        composeTestRule.onAllNodesWithText(context.getString(R.string.action_install))
            .get(0).performClick()
        composeTestRule.runOnIdle { assertThat(actionCount).isEqualTo(1) }
        composeTestRule.onNodeWithText("P13 Charts").performClick()
        composeTestRule.onNodeWithText("P13 Offline Atlas").assertExists()
        shot("r4_p13b_charts.png")
        composeTestRule.onNodeWithText("P13 Categories").performClick()
        composeTestRule.onNodeWithText("P13 Art").assertExists()
        shot("r4_p13b_categories.png")
    }

    @Test
    fun typedOfflineSearchOpensDetailsArtworkAndReview() {
        val all = apps
        val inputArt = offlineArtwork()
        val review = Review(userName = "P13 Test Reviewer", timeStamp = 1745750879,
            rating = 4, comment = "P13 hermetic review. No Play account or network.")
        var actions = 0
        var filterClicks = 0
        render {
            var query by remember { mutableStateOf("") }
            var selected by remember { mutableStateOf<App?>(null) }
            var freeOnly by remember { mutableStateOf(false) }
            val keyboard = LocalSoftwareKeyboardController.current
            if (selected == null) {
                Column {
                    Text("P13 Offline Search", modifier = Modifier.padding(12.dp))
                    TextField(value = query, onValueChange = { query = it },
                        label = { Text("P13 Query") },
                        modifier = Modifier.fillMaxWidth().testTag("p13-query"))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        FilterChip(selected = freeOnly, onClick = {
                            freeOnly = !freeOnly
                            filterClicks++
                        }, label = { Text("P13 Free filter") })
                        FilterChip(selected = true, onClick = {},
                            label = { Text("P13 Offline only") })
                    }
                    if (query.isNotBlank()) {
                        FilterChip(selected = false,
                            onClick = { query = "Atlas" },
                            label = { Text("P13 Suggest Atlas") })
                    }
                    LazyColumn {
                        items(all.filter {
                            it.displayName.contains(query, ignoreCase = true) &&
                                (!freeOnly || it.isFree)
                        }, key = { it.packageName }) { app ->
                            SearchResultListItem(app = app, onClick = {
                                keyboard?.hide()
                                selected = app
                            })
                        }
                    }
                }
            } else {
                val app = checkNotNull(selected)
                Column {
                    FilterChip(selected = true, onClick = { selected = null },
                        label = { Text("P13 Back to search") })
                    LazyColumn(modifier = Modifier.testTag("p13-details-list")) {
                        item { Details(app = app) }
                        item { Actions(
                            primaryActionDisplayName = context.getString(R.string.action_install),
                            secondaryActionDisplayName = context.getString(R.string.title_manual_download),
                            onPrimaryAction = { actions++ }
                        ) }
                        item { Screenshots(screenshots = inputArt) }
                        item {
                            Column {
                                Text("P13 Review", modifier = Modifier.padding(12.dp))
                                RatingAndReviews(rating = app.rating, featuredReviews = listOf(review))
                                DetailsPortalCard(title = "P13 More about app",
                                    description = "Deterministic in-memory metadata",
                                    icon = painterResource(R.drawable.ic_apps),
                                    onClick = {})
                            }
                        }
                    }
                }
            }
        }
        composeTestRule.onNodeWithTag("p13-query").performTextInput("Atlas")
        composeTestRule.onNodeWithText("P13 Offline Atlas").assertExists()
        composeTestRule.onNodeWithText("P13 Offline Beacon").assertDoesNotExist()
        composeTestRule.onNodeWithText("P13 Suggest Atlas").assertExists()
        composeTestRule.onNodeWithText("P13 Free filter").performClick()
        composeTestRule.runOnIdle { assertThat(filterClicks).isEqualTo(1) }
        shot("r4_p13b_search.png")
        composeTestRule.onNodeWithText("P13 Offline Atlas").performClick()
        composeTestRule.onNodeWithText("P13 Back to search").assertExists()
        shot("r4_p13b_details_top.png")
        composeTestRule.onNodeWithTag("p13-details-list").performScrollToIndex(3)
        composeTestRule.onNodeWithText("P13 Review").assertExists()
        SystemClock.sleep(850) // bounded: production screenshot carousel loads local input art
        shot("r4_p13b_details_reviews.png")
        composeTestRule.runOnIdle { assertThat(actions).isEqualTo(0) }
    }

    @Test
    fun selectedCategoryShowsLocalAppsWithoutPlayCall() {
        val all = apps
        render {
            var selected by remember { mutableStateOf<String?>(null) }
            Column {
                if (selected == null) {
                    SectionHeader(title = "P13 Category browser")
                    CategoriesBody(list = categories,
                        onCategoryClick = { selected = it.title })
                } else {
                    FilterChip(selected = true, onClick = { selected = null },
                        label = { Text("P13 Back to categories") })
                    StreamCarousel(streamBundle = StreamBundle(
                        id = "p13b-category-results", clusters = listOf(
                            StreamCluster(id = "p13b-selected", title = "P13 Selected Art", apps = all)
                        )
                    ), showHomeActions = false)
                }
            }
        }
        composeTestRule.onNodeWithText("P13 Art").assertExists()
        shot("r4_p13b_category_selection.png")
        composeTestRule.onNodeWithText("P13 Art").performClick()
        composeTestRule.onNodeWithText("P13 Selected Art").assertExists()
        composeTestRule.onNodeWithText("P13 Offline Atlas").assertExists()
        shot("r4_p13b_category_collection.png")
    }
}
