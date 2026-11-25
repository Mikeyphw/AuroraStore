/*
 * SPDX-FileCopyrightText: 2026 Aurora OSS
 * SPDX-FileCopyrightText: 2025 The Calyx Institute
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

package com.aurora.store.compose.ui.downloads

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.dimensionResource
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.tooling.preview.PreviewParameter
import androidx.compose.ui.tooling.preview.PreviewWrapper
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.paging.LoadState
import androidx.paging.PagingData
import androidx.paging.compose.LazyPagingItems
import androidx.paging.compose.collectAsLazyPagingItems
import androidx.paging.compose.itemKey
import com.aurora.extensions.emptyPagingItems
import com.aurora.extensions.toast
import com.aurora.gplayapi.model.App
import com.aurora.store.R
import com.aurora.store.compose.composable.ContainedLoadingIndicator
import com.aurora.store.compose.composable.DownloadListItem
import com.aurora.store.compose.composable.Placeholder
import com.aurora.store.compose.composable.ScrollHint
import com.aurora.store.compose.composable.TopAppBar
import com.aurora.store.compose.navigation.Destination
import com.aurora.store.compose.preview.AppPreviewProvider
import com.aurora.store.compose.preview.ThemePreviewProvider
import com.aurora.store.compose.ui.commons.SortSheet
import com.aurora.store.compose.ui.downloads.menu.DownloadsMenu
import com.aurora.store.compose.ui.downloads.menu.MenuItem
import com.aurora.store.compose.ui.sheets.DownloadActionsSheet
import com.aurora.store.data.model.DownloadSortBy
import com.aurora.store.data.model.DownloadStatus
import com.aurora.store.data.room.download.Download
import com.aurora.store.viewmodel.downloads.DownloadsViewModel
import kotlin.random.Random
import kotlinx.coroutines.flow.MutableStateFlow

@Composable
fun DownloadsScreen(
    onNavigateTo: (Destination) -> Unit,
    viewModel: DownloadsViewModel = hiltViewModel()
) {
    val context = LocalContext.current
    val downloads = viewModel.downloads.collectAsLazyPagingItems()
    val sort by viewModel.sort.collectAsStateWithLifecycle()
    val liveDownloads by viewModel.liveDownloads.collectAsStateWithLifecycle()

    val exportMimeType = "application/zip"
    var requestedExport by rememberSaveable { mutableStateOf<Download?>(null) }
    val documentLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.CreateDocument(exportMimeType),
        onResult = {
            if (it != null) {
                requestedExport?.let { download -> viewModel.export(download, it) }
            } else {
                context.toast(R.string.failed_apk_export)
            }
            requestedExport = null
        }
    )

    ScreenContent(
        downloads = downloads,
        liveDownloads = liveDownloads,
        sort = sort,
        onSortChange = { viewModel.updateSort(it) },
        onNavigateTo = onNavigateTo,
        onCancelAll = { viewModel.cancelAll() },
        onForceClearAll = { viewModel.clearAll() },
        onClearFinished = { viewModel.clearFinished() },
        onCancel = { download -> viewModel.cancel(download) },
        onRetry = { download -> viewModel.retry(download) },
        onInstall = { download -> viewModel.install(download) },
        onClear = { download -> viewModel.clear(download) },
        onExport = { download ->
            requestedExport = download
            documentLauncher.launch("${download.packageName}.zip")
        }
    )
}

@Composable
private fun ScreenContent(
    downloads: LazyPagingItems<Download> = emptyPagingItems(),
    liveDownloads: List<Download> = emptyList(),
    sort: DownloadSort = DownloadSort(),
    onSortChange: (DownloadSort) -> Unit = {},
    onNavigateTo: (Destination) -> Unit = {},
    onCancel: (download: Download) -> Unit = {},
    onRetry: (download: Download) -> Unit = {},
    onClear: (download: Download) -> Unit = {},
    onExport: (download: Download) -> Unit = {},
    onInstall: (download: Download) -> Unit = {},
    onCancelAll: () -> Unit = {},
    onForceClearAll: () -> Unit = {},
    onClearFinished: () -> Unit = {}
) {
    /*
     * For some reason paging3 frequently out-of-nowhere invalidates the list which causes
     * the loading animation to play again even if the keys are same causing a glitching effect.
     *
     * Save the initial loading state to make sure we don't replay the loading animation again.
     */
    var initialLoad by rememberSaveable { mutableStateOf(true) }
    var actionsTarget by rememberSaveable { mutableStateOf<Download?>(null) }
    var sortSheetVisible by remember { mutableStateOf(false) }
    var confirmClearAll by rememberSaveable { mutableStateOf(false) }
    val liveByPackage = remember(liveDownloads) { liveDownloads.associateBy { it.packageName } }

    if (confirmClearAll) {
        AlertDialog(
            onDismissRequest = { confirmClearAll = false },
            title = { Text(stringResource(R.string.download_force_clear_all)) },
            text = { Text(stringResource(R.string.r1f_download_clear_all_warning)) },
            confirmButton = {
                TextButton(onClick = {
                    confirmClearAll = false
                    onForceClearAll()
                }) {
                    Text(stringResource(R.string.download_force_clear_all))
                }
            },
            dismissButton = {
                TextButton(onClick = { confirmClearAll = false }) {
                    Text(stringResource(R.string.action_cancel))
                }
            }
        )
    }

    if (sortSheetVisible) {
        SortSheet(
            options = DownloadSortBy.entries,
            sortBy = sort.sortBy,
            sortOrder = sort.sortOrder,
            labelRes = { it.labelRes() },
            onSortByChange = { onSortChange(sort.copy(sortBy = it)) },
            onSortOrderChange = { onSortChange(sort.copy(sortOrder = it)) },
            onDismiss = { sortSheetVisible = false }
        )
    }

    actionsTarget?.let { selected ->
        val target = liveByPackage[selected.packageName]
            ?.takeIf { live ->
                live.versionCode == selected.versionCode &&
                    live.downloadedAt == selected.downloadedAt
            } ?: selected
        DownloadActionsSheet(
            download = target,
            onDismiss = { actionsTarget = null },
            onShowDetails = { onNavigateTo(Destination.AppDetails(target.packageName)) },
            onCancel = { onCancel(target) },
            onRetry = { onRetry(target) },
            onInstall = { onInstall(target) },
            onExport = { onExport(target) },
            onClear = { onClear(target) }
        )
    }

    @Composable
    fun SetupMenu() {
        DownloadsMenu { menuItem ->
            when (menuItem) {
                MenuItem.CANCEL_ALL -> onCancelAll()
                MenuItem.FORCE_CLEAR_ALL -> confirmClearAll = true
                MenuItem.CLEAR_FINISHED -> onClearFinished()
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = stringResource(R.string.title_download_manager),
                actions = {
                    if (downloads.itemCount != 0) {
                        IconButton(onClick = { sortSheetVisible = true }) {
                            Icon(
                                painter = painterResource(R.drawable.ic_tune),
                                contentDescription = stringResource(R.string.installed_sort_by)
                            )
                        }
                        SetupMenu()
                    }
                }
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .padding(paddingValues)
                .fillMaxSize()
                .padding(vertical = dimensionResource(R.dimen.spacing_medium))
        ) {
            when {
                downloads.loadState.refresh is LoadState.Loading && initialLoad -> {
                    ContainedLoadingIndicator()
                }

                else -> {
                    initialLoad = false

                    if (downloads.itemCount == 0) {
                        Placeholder(
                            modifier = Modifier.padding(paddingValues),
                            painter = painterResource(R.drawable.ic_download_manager),
                            message = stringResource(R.string.download_none)
                        )
                    } else {
                        val listState = rememberLazyListState()
                        Box(modifier = Modifier.fillMaxSize()) {
                            LazyColumn(
                                state = listState
                            ) {
                                items(
                                    count = downloads.itemCount,
                                    key = downloads.itemKey { it.packageName }
                                ) { index ->
                                    downloads[index]?.let { download ->
                                        DownloadListItem(
                                            modifier = Modifier.animateItem(),
                                            download = liveByPackage[download.packageName]
                                                ?: download,
                                            onClick = {
                                                actionsTarget = liveByPackage[download.packageName]
                                                    ?: download
                                            }
                                        )
                                    }
                                }
                            }
                            ScrollHint(
                                listState = listState,
                                modifier = Modifier.align(Alignment.BottomCenter)
                            )
                        }
                    }
                }
            }
        }
    }
}

@PreviewWrapper(ThemePreviewProvider::class)
@Preview
@Composable
private fun DownloadsScreenPreview(@PreviewParameter(AppPreviewProvider::class) app: App) {
    val downloads = List(10) {
        Download.fromApp(app).copy(
            packageName = Random.nextInt().toString(),
            status = DownloadStatus.entries.random()
        )
    }
    val pagedDownloads = MutableStateFlow(PagingData.from(downloads)).collectAsLazyPagingItems()
    ScreenContent(downloads = pagedDownloads)
}
