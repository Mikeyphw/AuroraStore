/*
 * SPDX-FileCopyrightText: 2026 Aurora OSS
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

package com.aurora.store.data.helper

import android.content.Context
import android.util.Log
import androidx.paging.PagingSource
import androidx.sqlite.db.SimpleSQLiteQuery
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.Data
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.OutOfQuotaPolicy
import androidx.work.WorkManager
import androidx.work.WorkRequest
import com.aurora.extensions.TAG
import com.aurora.gplayapi.model.App
import com.aurora.store.AuroraApp
import com.aurora.store.data.AccountRepository
import com.aurora.store.data.event.InstallerEvent
import com.aurora.store.data.installer.AppInstaller
import com.aurora.store.data.model.DownloadSortBy
import com.aurora.store.data.model.DownloadStatus
import com.aurora.store.data.room.download.Download
import com.aurora.store.data.room.download.DownloadDao
import com.aurora.store.data.room.suite.ExternalApk
import com.aurora.store.data.room.update.Update
import com.aurora.store.data.work.DownloadWorker
import com.aurora.store.util.NotificationUtil
import com.aurora.store.util.PackageUtil
import com.aurora.store.util.PathUtil
import dagger.hilt.android.qualifiers.ApplicationContext
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import kotlin.coroutines.cancellation.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.firstOrNull
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/**
 * Helper class to work with the [DownloadWorker].
 */
class DownloadHelper @Inject constructor(
    @ApplicationContext private val context: Context,
    private val downloadDao: DownloadDao,
    private val appInstaller: AppInstaller,
    private val accountRepository: AccountRepository
) {

    companion object {
        const val DOWNLOAD_WORKER = "DOWNLOAD_WORKER"
        const val PACKAGE_NAME = "PACKAGE_NAME"

        private const val DOWNLOAD_APP = "DOWNLOAD_APP"
        private const val DOWNLOAD_UPDATE = "DOWNLOAD_UPDATE"
        const val VERSION_CODE = "VERSION_CODE"
        const val ATTEMPT_KEY = "ATTEMPT_KEY"
        private const val ORPHAN_CHECK_INTERVAL_MS = 120_000L
    }

    // Single stable StateFlow shared across consumers. Previously a `get()` accessor that
    // returned a new StateFlow on every read, which made `collectAsStateWithLifecycle` re-
    // collect on every recomposition and briefly replay the `emptyList()` initial value —
    // causing the Updates screen's per-item button to flicker between "Update" and "Cancel"
    // on every download tick.
    val downloadsList = downloadDao.downloads()
        .stateIn(AuroraApp.scope, SharingStarted.WhileSubscribed(), emptyList())

    fun pagedDownloads(sortBy: DownloadSortBy, ascending: Boolean): PagingSource<Int, Download> {
        val column = when (sortBy) {
            DownloadSortBy.DATE_DOWNLOADED -> "downloadedAt"
            DownloadSortBy.NAME -> "displayName COLLATE NOCASE"
            DownloadSortBy.SIZE -> "size"
        }
        val direction = if (ascending) "ASC" else "DESC"
        return downloadDao.pagedDownloads(
            SimpleSQLiteQuery("SELECT * FROM download ORDER BY $column $direction, packageName")
        )
    }

    val pendingInstalls = downloadDao.pendingInstalls()
        .stateIn(AuroraApp.scope, SharingStarted.WhileSubscribed(), emptyList())

    /**
     * One-shot read of the current download record for [packageName], if any.
     */
    suspend fun getDownload(packageName: String): Download? =
        runCatching { downloadDao.getDownload(packageName) }.getOrNull()

    /**
     * Whether [enqueue] would actually fetch files for [packageName] at [versionCode], rather
     * than install what an earlier download already left on disk.
     */
    suspend fun needsDownload(packageName: String, versionCode: Long): Boolean {
        val existing = getDownload(packageName)
        return existing == null ||
            existing.versionCode != versionCode ||
            !existing.canInstall(context)
    }

    /**
     * Removes failed download from the queue and starts observing for newly enqueued apps.
     */
    fun init() {
        AuroraApp.scope.launch {
            val downloads = downloadDao.downloads().firstOrNull() ?: emptyList()
            cancelFailedDownloads(downloads)
            finalizeStaleSelfUpdate(downloads)
            recoverStalledInstalls(downloads)
        }.invokeOnCompletion {
            observeDownloads()
            observeInstalls()
            monitorOrphanedDownloads()
        }
    }

    private suspend fun recoverStalledInstalls(downloads: List<Download>) {
        downloads.filter {
            it.packageName != context.packageName &&
                it.status in setOf(DownloadStatus.COMPLETED, DownloadStatus.INSTALLING) &&
                it.hasDownloadedFiles(context) &&
                !PackageUtil.isInstalled(context, it.packageName, it.versionCode)
        }.forEach {
            Log.i(TAG, "Recovering stalled install for ${it.packageName}")
            downloadDao.updateStatus(it.packageName, DownloadStatus.AWAITING_INSTALL)
            WorkManager.getInstance(context)
                .cancelAllWorkByTag("$PACKAGE_NAME:${it.packageName}")
        }
    }

    /**
     * Finalizes a self-update download left dangling in [DownloadStatus.INSTALLING]. Replacing
     * the app's own APK kills the process before the installer's "installed" event can advance
     * the row, so on the next launch it would otherwise show as installing forever. Reaching
     * INSTALLING means the install was already committed, so mark it installed; if it actually
     * failed, the periodic update check re-offers and re-enqueues it.
     *
     * The worker is cancelled too: it never got to return a result either, so WorkManager would
     * keep re-running it on every launch, re-installing the app over itself each time.
     */
    private suspend fun finalizeStaleSelfUpdate(downloads: List<Download>) {
        downloads.firstOrNull {
            it.packageName == context.packageName && it.status == DownloadStatus.INSTALLING
        }?.let {
            Log.i(TAG, "Finalizing stale self-update install for ${it.packageName}")
            downloadDao.updateStatus(it.packageName, DownloadStatus.INSTALLED)
            WorkManager.getInstance(context)
                .cancelAllWorkByTag("$PACKAGE_NAME:${it.packageName}")
        }
    }

    /**
     * Advances a download row through the installer phase so its history reflects whether the
     * app actually installed, not just that the bytes finished downloading:
     * - [InstallerEvent.Installing] moves a [DownloadStatus.COMPLETED] row to
     *   [DownloadStatus.INSTALLING];
     * - [InstallerEvent.Installed] marks it [DownloadStatus.INSTALLED] (kept so the user can
     *   still export the APK);
     * - [InstallerEvent.Failed] reverts an in-progress install to
     *   [DownloadStatus.AWAITING_INSTALL] so the downloaded files can be re-installed without
     *   re-downloading.
     */
    private fun observeInstalls() {
        AuroraApp.events.installerEvent.onEach { event ->
            val existing = getDownload(event.packageName) ?: return@onEach
            when (event) {
                is InstallerEvent.Installing -> if (existing.status == DownloadStatus.COMPLETED) {
                    downloadDao.updateStatus(event.packageName, DownloadStatus.INSTALLING)
                }

                is InstallerEvent.Installed -> if (existing.status != DownloadStatus.INSTALLED) {
                    downloadDao.updateStatus(event.packageName, DownloadStatus.INSTALLED)
                }

                is InstallerEvent.Failed -> if (
                    existing.status in setOf(
                        DownloadStatus.INSTALLING,
                        DownloadStatus.AWAITING_INSTALL
                    )
                ) {
                    downloadDao.updateStatus(
                        event.packageName,
                        if (existing.hasDownloadedFiles(context)) {
                            DownloadStatus.AWAITING_INSTALL
                        } else {
                            DownloadStatus.COMPLETED
                        }
                    )
                }

                else -> {}
            }
        }.launchIn(AuroraApp.scope)
    }

    private fun observeDownloads() {
        downloadDao.downloads().onEach { list ->
            try {
                // Serialize downloads: only start the next queued item once nothing else is
                // actively purchasing/downloading/verifying. Previously this only checked for
                // DOWNLOADING, so a worker in PURCHASING/VERIFYING didn't count and a second
                // download could start concurrently and clobber the shared notification.
                if (list.none { it.status in DownloadStatus.processing }) {
                    list.find { it.status == DownloadStatus.QUEUED }
                        ?.let { queuedDownload ->
                            Log.i(TAG, "Enqueued download worker for ${queuedDownload.packageName}")
                            trigger(queuedDownload)
                        }
                }
            } catch (exception: Exception) {
                Log.e(TAG, "Failed to enqueue download worker", exception)
            }
        }.launchIn(AuroraApp.scope)
    }

    /**
     * Enqueues an app for download & install
     * @param app [App] to download
     */
    suspend fun enqueueApp(app: App) {
        enqueue(Download.fromApp(app))
    }

    /**
     * Enqueues an app for download using a chosen account. Binding to the default clears any
     * existing binding; a non-default account is persisted so future updates use it.
     */
    suspend fun enqueueApp(app: App, accountId: String) {
        accountRepository.bindApp(app.packageName, accountId)
        enqueueApp(app)
    }

    /**
     * Enqueues an update for download & install
     * @param update [Update] to download
     */
    suspend fun enqueueUpdate(update: Update) {
        enqueue(Download.fromUpdate(update))
    }

    /**
     * Enqueues an update using a chosen account. Binding to the default clears any existing
     * binding; a non-default account is persisted so this and future updates use it.
     */
    suspend fun enqueueUpdate(update: Update, accountId: String) {
        accountRepository.bindApp(update.packageName, accountId)
        enqueueUpdate(update)
    }

    /**
     * Enqueues ExternalApk for download & install
     * @param externalApk [ExternalApk] to download
     */
    suspend fun enqueueStandalone(externalApk: ExternalApk) {
        enqueue(Download.fromExternalApk(externalApk))
    }

    /**
     * Inserts a new download row, but only when a (re)download is actually needed. For an
     * existing record of the same version this:
     * - **installs without re-downloading** if the files are already downloaded & verified
     *   (e.g. the user missed the system install prompt, or the periodic update check runs
     *   again before a pending install completed); or
     * - **skips** entirely if the download is still active (queued/purchasing/downloading/
     *   verifying), so the periodic [UpdateWorker] and repeated user taps can't reset it back
     *   to [DownloadStatus.QUEUED] and re-download it.
     *
     * A genuinely newer version, or a previously failed/cancelled download whose files are
     * gone, falls through and is (re)enqueued.
     */
    private suspend fun enqueue(download: Download) {
        val existing = getDownload(download.packageName)
        // Never replace a record once its package installation has been committed.
        if (existing?.status == DownloadStatus.INSTALLING) return
        if (existing != null && existing.versionCode == download.versionCode) {
            if (existing.canInstall(context)) {
                Log.i(TAG, "${download.packageName} already downloaded, installing directly")
                runCatching {
                    appInstaller.getPreferredInstaller(notifyOnFallback = true).install(existing)
                }.onFailure { Log.e(TAG, "Failed to install ${download.packageName}", it) }
                return
            }
            if (existing.isActive) {
                Log.i(
                    TAG,
                    "Skipping enqueue for ${download.packageName}; already ${existing.status}"
                )
                return
            }
        }
        // downloadedAt is already durable in Room. Use a monotonically increasing value
        // as the attempt identity, so a new request for the SAME version cannot be confused
        // with a cancelled WorkManager generation. This also handles ExternalApk (timestamp 0).
        val nextAttempt = maxOf(
            System.currentTimeMillis(),
            (existing?.downloadedAt ?: 0L) + 1L
        )
        downloadDao.insert(download.copy(downloadedAt = nextAttempt))
        if (existing != null) {
            cancelWorkFor(existing)
        }
    }

    suspend fun installPending(packageName: String): Boolean {
        val existing = getDownload(packageName) ?: return false
        if (!existing.canInstall(context)) {
            // Auto-delete may have removed the APKs after an earlier install attempt. Nothing
            // is installable, so re-download rather than leaving the action doing nothing.
            Log.i(TAG, "Files for $packageName are gone, re-queueing download")
            retryDownload(packageName)
            return false
        }
        Log.i(TAG, "Re-triggering install for $packageName")
        NotificationUtil.clearAppNotification(context, packageName)
        return runCatching {
            appInstaller.getPreferredInstaller(notifyOnFallback = true).install(existing)
            true
        }.getOrElse {
            Log.e(TAG, "Failed to install $packageName", it)
            false
        }
    }

    suspend fun dismissPendingInstall(packageName: String, versionCode: Long) {
        Log.i(TAG, "Dismissing pending install for $packageName")
        runCatching { appInstaller.getPreferredInstaller().cancelInstall(packageName) }
        NotificationUtil.clearAppNotification(context, packageName)
        clearDownload(packageName, versionCode)
    }

    /**
     * Re-queues a previously failed (or otherwise inactive) download so it runs again. The
     * worker resumes from any verified files on disk, so a retry after an install failure
     * re-installs without re-downloading. No-op if the download is already active.
     * @param packageName Name of the package to retry
     */
    suspend fun retryDownload(packageName: String, expectedAttempt: Long? = null) {
        val existing = getDownload(packageName) ?: return
        if (expectedAttempt != null && existing.downloadedAt != expectedAttempt) return
        if (existing.isActive || existing.status == DownloadStatus.INSTALLING) {
            Log.i(TAG, "Skipping retry for $packageName; already ${existing.status}")
            return
        }
        val restarted = downloadDao.retryWithNewAttempt(
            packageName,
            existing.versionCode,
            existing.downloadedAt,
            System.currentTimeMillis()
        )
        if (restarted != 0) {
            Log.i(TAG, "Retrying download for $packageName with a fresh attempt")
            cancelWorkFor(existing)
        }
    }

    /**
     * Cancels the download for the given package
     * @param packageName Name of the package to cancel download
     */
    suspend fun cancelDownload(packageName: String, expectedAttempt: Long? = null) {
        val current = getDownload(packageName) ?: return
        if (expectedAttempt != null && current.downloadedAt != expectedAttempt) return
        val changed = downloadDao.cancelActiveDownload(
            packageName,
            current.versionCode,
            current.downloadedAt
        )
        if (changed == 0) return // Installation already committed or attempt changed.

        Log.i(TAG, "Cancelling download for $packageName at ${current.versionCode}")
        cancelWorkFor(current)
        NotificationUtil.clearAppNotification(context, packageName)
    }

    /**
     * Removes the download record from the database without deleting downloaded files.
     * @param packageName Name of the package
     */
    suspend fun removeDownload(packageName: String) {
        downloadDao.delete(packageName)
    }

    /**
     * Clears the entry & downloaded files for the given package
     * @param packageName Name of the package of the app
     * @param versionCode Version of the package
     */
    suspend fun clearDownload(
        packageName: String,
        versionCode: Long,
        expectedAttempt: Long? = null
    ) {
        val current = getDownload(packageName) ?: return
        if (expectedAttempt != null && current.downloadedAt != expectedAttempt) return
        if (current.versionCode != versionCode || current.status == DownloadStatus.INSTALLING) {
            return // Never delete a replacement download or APKs handed to the installer.
        }
        if (current.isActive) cancelDownload(packageName, current.downloadedAt)
        Log.i(TAG, "Clearing downloads for $packageName ($versionCode)")
        if (downloadDao.deleteVersion(packageName, versionCode, current.downloadedAt) == 0) {
            return
        }
        PathUtil.getAppDownloadDir(context, packageName, versionCode)
            .deleteRecursively()
    }

    /**
     * Clears all the downloads and their downloaded files
     */
    suspend fun clearAllDownloads() {
        Log.i(TAG, "Clearing all downloads!")
        // Invalidate active states before deleting records and files; workers must not
        // resurrect their database rows after force-clear.
        cancelAll()
        WorkManager.getInstance(context).cancelAllWorkByTag(DOWNLOAD_WORKER)
        downloadDao.deleteAll()
        PathUtil.getDownloadDirectory(context).deleteRecursively()
        PathUtil.getOldDownloadDirectories(context).forEach { it.deleteRecursively() }
    }

    /**
     * Clears finished downloads and their downloaded files
     */
    suspend fun clearFinishedDownloads() {
        downloadDao.downloads().firstOrNull()?.filter { it.isFinished }?.forEach {
            clearDownload(it.packageName, it.versionCode)
        }
    }

    /**
     * Cancels all the ongoing and queued downloads
     * @param updatesOnly Whether to cancel only updates, defaults to false
     */
    suspend fun cancelAll(updatesOnly: Boolean = false) {
        // Cancel exactly the matching downloads, including purchases, transfers and verifying.
        // Unlike tag-wide cancellation this covers BOTH apps and updates and cannot cancel
        // a newer generation for a package that was just re-queued.
        val cancellable = DownloadStatus.processing +
            setOf(DownloadStatus.QUEUED, DownloadStatus.COMPLETED)
        downloadDao.downloads().firstOrNull()
            ?.asSequence()
            ?.filter { it.status in cancellable }
            ?.filter { !updatesOnly || it.isInstalled }
            ?.forEach { cancelDownload(it.packageName, it.downloadedAt) }
    }

    private suspend fun cancelFailedDownloads(downloadList: List<Download>) {
        val workManager = WorkManager.getInstance(context)

        downloadList.filter { it.status in DownloadStatus.processing }.forEach { item ->
            val matchingWork = workManager
                .getWorkInfosByTagFlow("$PACKAGE_NAME:${item.packageName}")
                .firstOrNull().orEmpty()
                .filter {
                    "$VERSION_CODE:${item.versionCode}" in it.tags &&
                        "$ATTEMPT_KEY:${item.downloadedAt}" in it.tags
                }

            // all() returning false is STILL non-null: the old ?.run incorrectly failed
            // genuinely running downloads. Only release an orphaned processing slot.
            if (matchingWork.none { !it.state.isFinished }) {
                Log.w(TAG, "Recovering orphaned download for ${item.packageName}")
                downloadDao.failOrphanedDownload(
                    item.packageName,
                    item.versionCode,
                    item.downloadedAt
                )
            }
        }
    }

    /** Reconcile processing records while the app remains open, not only at startup. */
    private fun monitorOrphanedDownloads() {
        AuroraApp.scope.launch {
            while (true) {
                delay(ORPHAN_CHECK_INTERVAL_MS)
                try {
                    cancelFailedDownloads(downloadDao.downloads().firstOrNull().orEmpty())
                } catch (exception: CancellationException) {
                    throw exception
                } catch (exception: Exception) {
                    Log.w(TAG, "Unable to reconcile orphaned download workers", exception)
                }
            }
        }
    }

    /** Stop both R1A (version-only) and R1B (attempt-scoped) workers on replacement. */
    private fun cancelWorkFor(download: Download) {
        val workManager = WorkManager.getInstance(context)
        workManager.cancelUniqueWork(
            "$DOWNLOAD_WORKER/${download.packageName}/${download.versionCode}"
        )
        workManager.cancelUniqueWork(
            "$DOWNLOAD_WORKER/${download.packageName}/${download.versionCode}/" +
                download.downloadedAt
        )
    }

    private fun trigger(download: Download) {
        val inputData = Data.Builder()
            .putString(PACKAGE_NAME, download.packageName)
            .putLong(VERSION_CODE, download.versionCode)
            .putLong(ATTEMPT_KEY, download.downloadedAt)
            .build()

        // Require connectivity so the worker doesn't spin up (or keep running) without a
        // network, and back off exponentially so transient failures resume cleanly once the
        // connection returns instead of hammering the server.
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()

        val work = OneTimeWorkRequestBuilder<DownloadWorker>()
            .addTag(DOWNLOAD_WORKER)
            .addTag("$PACKAGE_NAME:${download.packageName}")
            .addTag("$VERSION_CODE:${download.versionCode}")
            .addTag("$ATTEMPT_KEY:${download.downloadedAt}")
            .addTag(if (download.isInstalled) DOWNLOAD_UPDATE else DOWNLOAD_APP)
            .setConstraints(constraints)
            .setBackoffCriteria(
                BackoffPolicy.EXPONENTIAL,
                WorkRequest.MIN_BACKOFF_MILLIS,
                TimeUnit.MILLISECONDS
            )
            .setExpedited(OutOfQuotaPolicy.DROP_WORK_REQUEST)
            .setInputData(inputData)
            .build()

        // Ensure all app downloads are unique to preserve individual records
        WorkManager.getInstance(context)
            .enqueueUniqueWork(
                "$DOWNLOAD_WORKER/${download.packageName}/${download.versionCode}/" +
                    download.downloadedAt,
                ExistingWorkPolicy.KEEP,
                work
            )
    }
}
