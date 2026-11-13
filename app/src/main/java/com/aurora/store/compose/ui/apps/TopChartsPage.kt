/*
 * SPDX-FileCopyrightText: 2026 Aurora OSS
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

package com.aurora.store.compose.ui.apps

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.Badge
import androidx.compose.material3.ExperimentalMaterial3ExpressiveApi
import androidx.compose.material3.Icon
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SegmentedListItem
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.dimensionResource
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.tooling.preview.PreviewWrapper
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.Dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil3.compose.AsyncImage
import com.aurora.gplayapi.api.TopChartType
import com.aurora.gplayapi.model.App
import com.aurora.gplayapi.model.StreamCluster
import com.aurora.gplayapi.model.ContentType
import com.aurora.store.R
import com.aurora.store.compose.composable.Placeholder
import com.aurora.store.compose.composable.auroraSegmentedListItemShapes
import com.aurora.store.compose.composable.rememberStoreImageRequest
import com.aurora.store.compose.composable.rememberShimmerBrush
import com.aurora.store.compose.composable.ShimmerAppRow
import com.aurora.store.compose.preview.AppPreviewProvider
import com.aurora.store.compose.preview.ThemePreviewProvider
import com.aurora.store.data.model.ViewState
import com.aurora.store.data.model.ViewState.Loading.getDataAs
import com.aurora.store.viewmodel.topchart.TopChartViewModel

private const val LOAD_MORE_THRESHOLD = 2
private val TOP_CHARTS = listOf(
    TopChartType.TOP_SELLING_FREE,
    TopChartType.TOP_GROSSING,
    TopChartType.MOVERS_SHAKERS,
    TopChartType.TOP_SELLING_PAID
)

@Composable
@OptIn(ExperimentalMaterial3ExpressiveApi::class)
internal fun TopChartsContent(
    pageType: Int,
    viewModel: TopChartViewModel,
    onAppClick: (App) -> Unit,
    selectedIndex: Int,
    bottomContentPadding: Dp
) {
    val chartType =
        if (pageType == 1) ContentType.GAME else ContentType.APPLICATION
    val selectedChart = TOP_CHARTS[selectedIndex]
    val state by viewModel.state.collectAsStateWithLifecycle()
    val cluster = state.getDataAs<StreamCluster?>()
    val listState = rememberLazyListState()

    LaunchedEffect(selectedIndex) {
        listState.scrollToItem(0)
        viewModel.getStreamCluster(chartType, selectedChart)
    }

    // WebChartApi in GPlayAPI 4 has no continuation. Do not trigger a missing nextCluster.
    TopChartsBody(
        state = state,
        cluster = cluster,
        listState = listState,
        chartIndex = selectedIndex,
        bottomContentPadding = bottomContentPadding,
        onRetry = { viewModel.getStreamCluster(chartType, selectedChart) },
        onAppClick = onAppClick
    )
}

@OptIn(ExperimentalMaterial3ExpressiveApi::class)
@Composable
private fun TopChartAppCard(
    modifier: Modifier = Modifier,
    rank: Int,
    itemIndex: Int,
    itemCount: Int,
    app: App,
    onClick: () -> Unit
) {
    SegmentedListItem(
        selected = false,
        onClick = onClick,
        shapes = auroraSegmentedListItemShapes(index = itemIndex, count = itemCount),
        modifier = modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        colors = ListItemDefaults.segmentedColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainerLow
        ),
        contentPadding = PaddingValues(
            horizontal = dimensionResource(R.dimen.spacing_large),
            vertical = dimensionResource(R.dimen.spacing_small)
        ),
        leadingContent = {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Badge(
                    containerColor = MaterialTheme.colorScheme.secondaryContainer,
                    contentColor = MaterialTheme.colorScheme.onSecondaryContainer
                ) {
                    Text(text = rank.toString(), style = MaterialTheme.typography.labelMedium)
                }
                AsyncImage(
                    modifier = Modifier
                        .size(48.dp)
                        .clip(RoundedCornerShape(dimensionResource(R.dimen.app_icon_radius))),
                    model = rememberStoreImageRequest(app.iconArtwork.url),
                    contentDescription = null,
                    contentScale = ContentScale.Crop
                )
            }
        },
        supportingContent = {
            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(
                    text = app.developerName,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1
                )
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        painter = painterResource(R.drawable.ic_star),
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(14.dp)
                    )
                    Spacer(Modifier.width(3.dp))
                    Text(text = app.labeledRating, style = MaterialTheme.typography.bodySmall)
                    if (app.downloadString.isNotBlank()) {
                        Spacer(Modifier.width(8.dp))
                        Text(
                            text = app.downloadString,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 1
                        )
                    }
                }
            }
        }
    ) {
        Text(app.displayName, maxLines = 1, style = MaterialTheme.typography.titleSmall)
    }
}

@OptIn(ExperimentalMaterial3ExpressiveApi::class)
@Composable
private fun TopChartsBody(
    state: ViewState,
    cluster: StreamCluster?,
    chartIndex: Int = 0,
    bottomContentPadding: Dp,
    listState: LazyListState = rememberLazyListState(),
    onRetry: () -> Unit = {},
    onAppClick: (App) -> Unit = {}
) {
    Column(
        modifier = Modifier.fillMaxSize()
    ) {
        when {
            state is ViewState.Error -> Placeholder(
                modifier = Modifier.weight(1f),
                painter = painterResource(R.drawable.ic_apps),
                message = stringResource(R.string.no_apps_available),
                actionLabel = stringResource(R.string.action_retry),
                onAction = onRetry
            )

            cluster != null && cluster.apps.isEmpty() -> Placeholder(
                modifier = Modifier.weight(1f),
                painter = painterResource(R.drawable.ic_apps),
                message = stringResource(R.string.no_apps_available)
            )

            cluster != null -> {
                val apps = cluster.apps
                LazyColumn(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth(),
                    state = listState,
                    contentPadding = PaddingValues(
                        start = dimensionResource(R.dimen.spacing_large),
                        end = dimensionResource(R.dimen.spacing_large),
                        top = dimensionResource(R.dimen.spacing_small),
                        bottom = bottomContentPadding
                    ),
                    verticalArrangement = Arrangement.spacedBy(ListItemDefaults.SegmentedGap)
                ) {
                    items(count = apps.size, key = { "${chartIndex}_${apps[it].id}" }) { index ->
                        TopChartAppCard(
                            rank = index + 1,
                            itemIndex = index,
                            itemCount = apps.size,
                            app = apps[index],
                            onClick = { onAppClick(apps[index]) }
                        )
                    }
                }
            }

            else -> {
                val shimmerBrush = rememberShimmerBrush()
                LazyColumn(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth(),
                    contentPadding = PaddingValues(
                        start = dimensionResource(R.dimen.spacing_large),
                        end = dimensionResource(R.dimen.spacing_large),
                        top = dimensionResource(R.dimen.spacing_small),
                        bottom = bottomContentPadding
                    ),
                    verticalArrangement = Arrangement.spacedBy(ListItemDefaults.SegmentedGap)
                ) {
                    items(8) { ShimmerAppRow(shimmerBrush) }
                }
            }
        }
    }
}

@PreviewWrapper(ThemePreviewProvider::class)
@Preview(showBackground = true)
@Composable
private fun TopChartsBodyLoadingPreview() {
    TopChartsBody(
        state = ViewState.Loading,
        cluster = null,
        bottomContentPadding = 0.dp
    )
}

@PreviewWrapper(ThemePreviewProvider::class)
@Preview(showBackground = true)
@Composable
private fun TopChartsBodyLoadedPreview() {
    val app = AppPreviewProvider().values.first()
    val apps = List(5) { i -> app.copy(id = i + 1, packageName = "com.preview.app$i") }
    val cluster = StreamCluster(id = "1", apps = apps)
    TopChartsBody(
        state = ViewState.Success(cluster),
        cluster = cluster,
        bottomContentPadding = 0.dp
    )
}

@PreviewWrapper(ThemePreviewProvider::class)
@Preview(showBackground = true)
@Composable
private fun TopChartsBodyEmptyPreview() {
    val cluster = StreamCluster(id = "1", apps = emptyList())
    TopChartsBody(
        state = ViewState.Success(cluster),
        cluster = cluster,
        bottomContentPadding = 0.dp
    )
}

@PreviewWrapper(ThemePreviewProvider::class)
@Preview(showBackground = true)
@Composable
private fun TopChartsBodyErrorPreview() {
    TopChartsBody(
        state = ViewState.Error("Network error"),
        cluster = null,
        bottomContentPadding = 0.dp
    )
}
