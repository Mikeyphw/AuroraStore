/*
 * SPDX-FileCopyrightText: 2021 Aurora OSS
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

package com.aurora.store.data.installer.base

import android.content.Context
import android.content.pm.PackageInstaller
import android.net.Uri
import android.util.Log
import androidx.core.content.FileProvider
import com.aurora.extensions.TAG
import com.aurora.store.AuroraApp
import com.aurora.store.BuildConfig
import com.aurora.store.R
import com.aurora.store.data.event.InstallAttempt
import com.aurora.store.data.event.InstallerEvent
import com.aurora.store.data.room.download.Download
import com.aurora.store.util.NotificationUtil
import com.aurora.store.util.PathUtil
import java.io.File

abstract class InstallerBase(private val context: Context) : IInstaller {

    companion object {
        fun notifyInstallation(context: Context, displayName: String, packageName: String) {
            NotificationUtil.notifyInstalled(context, displayName, packageName)
        }

        fun getErrorString(context: Context, status: Int): String = when (status) {
            PackageInstaller.STATUS_FAILURE_ABORTED -> context.getString(
                R.string.installer_status_aborted
            )

            PackageInstaller.STATUS_FAILURE_BLOCKED -> context.getString(
                R.string.installer_status_failure_blocked
            )

            PackageInstaller.STATUS_FAILURE_CONFLICT -> context.getString(
                R.string.installer_status_failure_conflict
            )

            PackageInstaller.STATUS_FAILURE_INCOMPATIBLE -> context.getString(
                R.string.installer_status_failure_incompatible
            )

            PackageInstaller.STATUS_FAILURE_INVALID -> context.getString(
                R.string.installer_status_failure_invalid
            )

            PackageInstaller.STATUS_FAILURE_STORAGE -> context.getString(
                R.string.installer_status_failure_storage
            )

            else -> context.getString(R.string.installer_status_failure)
        }
    }

    var download: Download? = null
        private set

    override fun install(download: Download) {
        this.download = download
    }

    override fun clearQueue() {
        AuroraApp.enqueuedInstalls.clear()
    }

    override fun isAlreadyQueued(packageName: String): Boolean =
        AuroraApp.enqueuedInstalls.contains(packageName)

    override fun removeFromInstallQueue(packageName: String) {
        AuroraApp.enqueuedInstalls.remove(packageName)
    }

    /** A backend receipt is only a candidate; Room CAS authorizes final side effects. */
    fun onInstallationSuccess(accepted: Download? = download) {
        accepted?.let {
            AuroraApp.events.send(
                InstallerEvent.Installed(
                    it.packageName,
                    InstallAttempt(it.versionCode, it.downloadedAt)
                )
            )
        }
    }

    open fun postError(
        packageName: String,
        error: String?,
        extra: String?,
        failed: Download? = download
    ) {
        Log.e(TAG, "Installer Error :$error")
        val identified = failed?.takeIf { it.packageName == packageName }
        AuroraApp.events.send(
            InstallerEvent.Failed(
                packageName = packageName,
                error = error,
                extra = extra,
                attempt = identified?.let { InstallAttempt(it.versionCode, it.downloadedAt) }
            )
        )
    }

    fun getFiles(
        packageName: String,
        versionCode: Long,
        sharedLibPackageName: String = ""
    ): List<File> {
        val downloadDir = if (sharedLibPackageName.isNotBlank()) {
            PathUtil.getLibDownloadDir(context, packageName, versionCode, sharedLibPackageName)
        } else {
            PathUtil.getAppDownloadDir(context, packageName, versionCode)
        }
        return downloadDir.listFiles().orEmpty().filter { it.path.endsWith(".apk") && it.isFile }
    }

    fun getUri(file: File): Uri = FileProvider.getUriForFile(
        context,
        "${BuildConfig.APPLICATION_ID}.fileProvider",
        file
    )
}
