/*
 * SPDX-FileCopyrightText: 2021 Aurora OSS
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

package com.aurora.store.viewmodel.all

import android.content.Context
import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aurora.extensions.TAG
import com.aurora.gplayapi.PlayClient
import com.aurora.gplayapi.PlayException
import com.aurora.gplayapi.model.App
import com.aurora.gplayapi.session.Capability
import com.aurora.store.AuroraApp
import com.aurora.store.data.ExodusRepository
import com.aurora.store.data.event.AuthEvent
import com.aurora.store.data.event.InstallerEvent
import com.aurora.store.data.helper.DownloadHelper
import com.aurora.store.data.helper.UpdateHelper
import com.aurora.store.data.model.ExodusTracker
import com.aurora.store.data.model.StorageRequirement
import com.aurora.store.data.room.update.Update
import com.aurora.store.util.Preferences
import com.aurora.store.util.Preferences.PREFERENCE_UPDATES_LAST_CHECKED
import com.aurora.store.util.StorageUtil
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.coroutines.launch

@HiltViewModel
class UpdatesViewModel @Inject constructor(
    val updateHelper: UpdateHelper,
    private val downloadHelper: DownloadHelper,
    private val playClient: PlayClient,
    private val exodusRepository: ExodusRepository,
    @ApplicationContext private val context: Context
) : ViewModel() {

    var updateAllEnqueued: Boolean = false

    private val _storageWarning = MutableSharedFlow<StorageRequirement>()
    val storageWarning = _storageWarning.asSharedFlow()

    val downloadsList get() = downloadHelper.downloadsList
    val updates get() = updateHelper.updates
    val ignoredUpdates get() = updateHelper.ignoredUpdates

    val fetchingUpdates = updateHelper.isCheckingUpdates

    private val _cancellingPackages = MutableStateFlow<Set<String>>(emptySet())
    val cancellingPackages = _cancellingPackages.asStateFlow()

    private val _installing = MutableStateFlow<Set<String>>(emptySet())
    val installing = _installing.asStateFlow()

    init {
        AuroraApp.events.installerEvent.onEach { event ->
            _installing.update {
                when (event) {
                    is InstallerEvent.Installing -> it + event.packageName
                    is InstallerEvent.PendingUserAction,
                    is InstallerEvent.Installed,
                    is InstallerEvent.Failed -> it - event.packageName

                    else -> it
                }
            }
        }.launchIn(viewModelScope)

        // An empty list only means "no updates" once a check has actually run
        if (Preferences.getLong(context, PREFERENCE_UPDATES_LAST_CHECKED) == 0L) fetchUpdates()
    }

    fun fetchUpdates() {
        updateHelper.checkUpdatesNow()
    }

    fun unignore(packageName: String) {
        viewModelScope.launch { updateHelper.unignore(packageName) }
    }

    fun download(update: Update) {
        viewModelScope.launch {
            if (hasSpaceFor(listOf(update), update.displayName)) {
                downloadHelper.enqueueUpdate(update)
            }
        }
    }

    /** Home discovery cards are partial listings; never enqueue without a full v4 details fetch. */
    fun downloadApp(app: App, onDetailsFallback: () -> Unit = {}) {
        viewModelScope.launch {
            val fullApp = try {
                if (!playClient.supports(Capability.DOWNLOAD)) {
                    onDetailsFallback()
                    return@launch
                }
                withContext(Dispatchers.IO) { playClient.apps.details(app.packageName) }
            } catch (exception: PlayException.Unauthorized) {
                AuroraApp.events.send(AuthEvent.SessionExpired(app.packageName))
                return@launch
            } catch (exception: Exception) {
                Log.w(TAG, "Home install details unavailable for ${app.packageName}", exception)
                onDetailsFallback()
                return@launch
            }
            if (!downloadHelper.needsDownload(fullApp.packageName, fullApp.versionCode) ||
                StorageUtil.check(context, listOf(fullApp.size), fullApp.displayName).also {
                    if (!it.isSufficient) _storageWarning.emit(it)
                }.isSufficient
            ) {
                downloadHelper.enqueueApp(fullApp)
            }
        }
    }

    suspend fun getNewTrackers(
        packageName: String,
        installedVersionCode: Long
    ): List<ExodusTracker> = exodusRepository.getNewTrackers(packageName, installedVersionCode)

    fun downloadAll(updates: List<Update>) {
        viewModelScope.launch {
            if (hasSpaceFor(updates)) updates.forEach { downloadHelper.enqueueUpdate(it) }
        }
    }

    private suspend fun hasSpaceFor(updates: List<Update>, appName: String? = null): Boolean {
        val sizes = updates
            .filter { downloadHelper.needsDownload(it.packageName, it.versionCode) }
            .map { it.size }

        val requirement = StorageUtil.check(context, sizes, appName)
        if (!requirement.isSufficient) _storageWarning.emit(requirement)
        return requirement.isSufficient
    }

    fun cancelDownload(packageName: String) {
        viewModelScope.launch {
            if (packageName in _cancellingPackages.value) return@launch
            _cancellingPackages.update { it + packageName }
            try {
                downloadHelper.cancelDownload(packageName)
                // Never hold UI cancellation state indefinitely after a worker disappears.
                withTimeoutOrNull(5_000L) {
                    downloadHelper.downloadsList.first { downloads ->
                        downloads.none { item ->
                            item.packageName == packageName &&
                                item.status in com.aurora.store.data.model.DownloadStatus.running
                        }
                    }
                }
            } finally {
                _cancellingPackages.update { it - packageName }
            }
        }
    }

    fun cancelAll() {
        viewModelScope.launch { downloadHelper.cancelAll(true) }
    }
}
