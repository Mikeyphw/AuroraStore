/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.compose.ui.r4

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import com.aurora.gplayapi.api.SearchSuggestion
import com.aurora.gplayapi.model.App
import com.aurora.gplayapi.model.Artwork
import com.aurora.gplayapi.model.Review
import com.aurora.store.compose.preview.AppPreviewProvider
import com.aurora.store.data.catalog.CatalogJourneyGateway
import com.aurora.store.data.catalog.CatalogJourneyGatewayModule
import dagger.Binds
import dagger.Module
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import dagger.hilt.testing.TestInstallIn
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.atomic.AtomicInteger
import javax.inject.Inject

/** Installed only in instrumentation APKs; cannot be selected by release builds. */
class P14HermeticCatalogGateway @Inject constructor(
    @ApplicationContext private val context: Context
) : CatalogJourneyGateway {
    override val isHermetic: Boolean = true

    companion object {
        const val PACKAGE = "invalid.aurora.p14.fixture"
        val searchCount = AtomicInteger()
        val detailsCount = AtomicInteger()
        val reviewCount = AtomicInteger()
    }

    private fun fixtureArtwork(): List<Artwork> = (0..2).map { index ->
        val actualFile = File(context.filesDir, "p14-image-$index.png=rw-w480-v1-e15")
        if (!actualFile.exists()) {
            val bitmap = Bitmap.createBitmap(320, 560, Bitmap.Config.ARGB_8888)
            try {
                val canvas = Canvas(bitmap)
                canvas.drawColor(
                    listOf(
                        Color.rgb(45, 91, 159),
                        Color.rgb(37, 134, 122),
                        Color.rgb(144, 78, 124)
                    )[index]
                )
                val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                    color = Color.WHITE
                    textSize = 40f
                }
                canvas.drawText("P14 LOCAL", 48f, 200f, paint)
                paint.textSize = 25f
                canvas.drawText("Screenshot ${index + 1}", 48f, 265f, paint)
                FileOutputStream(actualFile).use { output ->
                    check(bitmap.compress(Bitmap.CompressFormat.PNG, 100, output))
                }
            } finally {
                bitmap.recycle()
            }
        }
        check(actualFile.length() > 1000L) { "P14_FIXTURE_ARTWORK_EMPTY" }
        Artwork(url = "file://" + File(context.filesDir, "p14-image-$index.png").absolutePath)
    }

    private fun app(): App = AppPreviewProvider().values.first().copy(
        id = 14020,
        packageName = PACKAGE,
        displayName = "P14 Offline Atlas",
        developerName = "P14 Hermetic Fixture",
        changes = "",
        isInstalled = false,
        isFree = true,
        containsAds = false,
        iconArtwork = Artwork(url = ""),
        screenshots = fixtureArtwork().toMutableList()
    )

    override fun searchResults(query: String): List<App>? {
        searchCount.incrementAndGet()
        return listOf(app()).filter { it.displayName.contains(query.trim(), ignoreCase = true) }
    }

    override fun suggestions(query: String): List<SearchSuggestion>? = emptyList()

    override fun appDetails(packageName: String): App? = if (packageName == PACKAGE) {
        detailsCount.incrementAndGet()
        app()
    } else {
        null
    }

    override fun featuredReviews(packageName: String): List<Review>? = if (packageName == PACKAGE) {
        reviewCount.incrementAndGet()
        listOf(
            Review(
                userName = "P14 Offline Reviewer",
                timeStamp = 1745750879,
                rating = 4,
                comment = "P14 hermetic featured review. No Play API used."
            )
        )
    } else {
        null
    }
}

@Module
@TestInstallIn(
    components = [SingletonComponent::class],
    replaces = [CatalogJourneyGatewayModule::class]
)
abstract class P14HermeticCatalogModule {
    @Binds abstract fun bindCatalogJourneyGateway(
        implementation: P14HermeticCatalogGateway
    ): CatalogJourneyGateway
}
