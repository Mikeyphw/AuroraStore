/*
 * SPDX-FileCopyrightText: 2025 The Calyx Institute
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

package com.aurora.store.viewmodel.downloads

import android.content.Context
import android.net.Uri
import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.paging.PagingData
import androidx.paging.cachedIn
import com.aurora.extensions.TAG
import com.aurora.store.compose.ui.commons.SortOrder
import com.aurora.store.compose.ui.downloads.DownloadSort
import com.aurora.store.compose.ui.downloads.loadDownloadSort
import com.aurora.store.compose.ui.downloads.save
import com.aurora.store.data.helper.DownloadHelper
import com.aurora.store.data.installer.AppInstaller
import com.aurora.store.data.paging.GenericPagingSource.Companion.pager
import com.aurora.store.data.room.download.Download
import com.aurora.store.data.work.ExportWorker
import com.aurora.store.util.PathUtil
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.launch

@HiltViewModel
class DownloadsViewModel @Inject constructor(
    private val downloadHelper: DownloadHelper,
    private val appInstaller: AppInstaller,
    @ApplicationContext private val context: Context
) : ViewModel() {

    private val _downloads = MutableStateFlow<PagingData<Download>>(PagingData.empty())
    val downloads = _downloads.asStateFlow()
    val liveDownloads = downloadHelper.downloadsList

    private val _sort = MutableStateFlow(loadDownloadSort(context))
    val sort = _sort.asStateFlow()

    init {
        getPagedDownloads()
    }

    fun updateSort(sort: DownloadSort) {
        if (sort == _sort.value) return
        _sort.value = sort
        sort.save(context)
    }

    fun cancel(packageName: String) {
        viewModelScope.launch(NonCancellable) {
            downloadHelper.cancelDownload(packageName)
        }
    }

    fun cancel(download: Download) {
        viewModelScope.launch(NonCancellable) {
            downloadHelper.cancelDownload(download.packageName, download.downloadedAt)
        }
    }

    fun retry(download: Download) {
        viewModelScope.launch(NonCancellable) {
            downloadHelper.retryDownload(download.packageName, download.downloadedAt)
        }
    }

    fun clear(download: Download) {
        viewModelScope.launch(NonCancellable) {
            downloadHelper.clearDownload(
                download.packageName,
                download.versionCode,
                download.downloadedAt
            )
        }
    }

    fun cancelAll() {
        viewModelScope.launch(NonCancellable) {
            downloadHelper.cancelAll()
        }
    }

    fun clear(packageName: String, versionCode: Long) {
        viewModelScope.launch(NonCancellable) {
            downloadHelper.clearDownload(packageName, versionCode)
        }
    }

    fun clearFinished() {
        viewModelScope.launch(NonCancellable) {
            downloadHelper.clearFinishedDownloads()
        }
    }

    fun clearAll() {
        viewModelScope.launch(NonCancellable) {
            downloadHelper.clearAllDownloads()
        }
    }

    /** A sheet may outlive the selected download generation. Always reread Room. */
    private suspend fun currentAttempt(selected: Download): Download? {
        val current = downloadHelper.getDownload(selected.packageName) ?: return null
        return current.takeIf {
            current.versionCode == selected.versionCode &&
                current.downloadedAt == selected.downloadedAt
        }
    }

    fun install(download: Download) {
        viewModelScope.launch {
            val current = currentAttempt(download) ?: return@launch
            if (!current.canInstall(context)) return@launch
            try {
                appInstaller.getPreferredInstaller(notifyOnFallback = true).install(current)
            } catch (exception: Exception) {
                Log.e(TAG, "Failed to install ${download.packageName}", exception)
            }
        }
    }

    fun export(download: Download, uri: Uri) {
        viewModelScope.launch {
            val current = currentAttempt(download) ?: return@launch
            if (PathUtil.getExportableFiles(context, current).isEmpty()) return@launch
            ExportWorker.exportDownloadedApp(context, current, uri)
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    private fun getPagedDownloads() {
        _sort
            .flatMapLatest { sort ->
                pager {
                    downloadHelper.pagedDownloads(sort.sortBy, sort.sortOrder == SortOrder.ASC)
                }.flow
            }
            .cachedIn(viewModelScope)
            .onEach { _downloads.value = it }
            .launchIn(viewModelScope)
    }
}
