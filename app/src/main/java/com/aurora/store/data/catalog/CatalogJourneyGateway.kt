/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.catalog

import com.aurora.gplayapi.api.SearchSuggestion
import com.aurora.gplayapi.model.App
import com.aurora.gplayapi.model.Review
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Inject

/** Optional deterministic catalog source. Null always delegates to existing production Play clients.
 * Only androidTest replaces the no-op binding; no sample data ships in release code.
 */
interface CatalogJourneyGateway {
    val isHermetic: Boolean get() = false
    fun searchResults(query: String): List<App>? = null
    fun suggestions(query: String): List<SearchSuggestion>? = null
    fun appDetails(packageName: String): App? = null
    fun featuredReviews(packageName: String): List<Review>? = null
}

class LiveCatalogJourneyGateway @Inject constructor() : CatalogJourneyGateway

@Module
@InstallIn(SingletonComponent::class)
abstract class CatalogJourneyGatewayModule {
    @Binds abstract fun bindCatalogJourneyGateway(
        implementation: LiveCatalogJourneyGateway
    ): CatalogJourneyGateway
}
