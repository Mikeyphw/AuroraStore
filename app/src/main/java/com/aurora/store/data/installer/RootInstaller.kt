/*
 * SPDX-FileCopyrightText: 2021 Aurora OSS
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

package com.aurora.store.data.installer

import android.content.Context
import android.os.Process
import android.util.Log
import com.aurora.extensions.TAG
import com.aurora.store.R
import com.aurora.store.data.installer.base.InstallerBase
import com.aurora.store.data.model.Installer
import com.aurora.store.data.model.InstallerInfo
import com.aurora.store.data.room.download.Download
import com.aurora.store.util.PackageUtil.isSharedLibraryInstalled
import com.topjohnwu.superuser.Shell
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class RootInstaller @Inject constructor(
    @ApplicationContext private val context: Context
) : InstallerBase(context) {

    companion object {
        const val PLAY_PACKAGE_NAME = "com.android.vending"

        val installerInfo: InstallerInfo
            get() = InstallerInfo(
                id = 2,
                installer = Installer.ROOT,
                installerPackageNames = listOf(PLAY_PACKAGE_NAME),
                title = R.string.pref_install_mode_root,
                subtitle = R.string.root_installer_subtitle,
                description = R.string.root_installer_desc
            )
    }

    override fun install(download: Download) {
        super.install(download)
        if (isAlreadyQueued(download.packageName)) {
            Log.i(TAG, "${download.packageName} already queued")
            return
        }
        if (!Shell.getShell().isRoot) {
            postError(
                download.packageName,
                context.getString(R.string.installer_status_failure),
                context.getString(R.string.installer_root_unavailable),
                download
            )
            return
        }

        // A shared library failure must stop the parent installation immediately.
        for (lib in download.sharedLibs) {
            if (!isSharedLibraryInstalled(context, lib.packageName, lib.versionCode) &&
                !installPackage(download, lib.packageName)
            ) {
                return
            }
        }
        if (installPackage(download)) {
            AppInstaller.recordPlayAttributedInstall(context, download.packageName)
            onInstallationSuccess(download)
        }
    }

    private fun installPackage(download: Download, libraryName: String = ""): Boolean {
        val files = getFiles(download.packageName, download.versionCode, libraryName)
        if (files.isEmpty()) {
            postError(download.packageName, "No APK files for privileged install", null, download)
            return false
        }
        val totalSize = files.sumOf { it.length() }
        val userId = Process.myUid() / 100_000
        val created = Shell.cmd(
            "pm install-create -i $PLAY_PACKAGE_NAME --user $userId -r -S $totalSize"
        ).exec()
        val sessionId = InstallerBackendPolicy.createdSession(
            created.isSuccess,
            created.out.joinToString("\n")
        )
        if (sessionId == null) {
            postError(
                download.packageName,
                context.getString(R.string.installer_status_failure_session),
                (created.err + created.out).joinToString("\n"),
                download
            )
            return false
        }
        try {
            files.forEach { file ->
                val command = "cat ${quote(file.absolutePath)} | pm install-write " +
                    "-S ${file.length()} $sessionId ${quote(file.name)}"
                val response = Shell.cmd(command).exec()
                val accepted = InstallerBackendPolicy.commandSucceeded(
                    response.isSuccess,
                    response.out.joinToString("\n")
                )
                check(accepted) { (response.err + response.out).joinToString("\n") }
            }
            val response = Shell.cmd("pm install-commit $sessionId").exec()
            val committed = InstallerBackendPolicy.commandSucceeded(
                response.isSuccess,
                response.out.joinToString("\n")
            )
            check(committed) { (response.err + response.out).joinToString("\n") }
            return true
        } catch (error: Exception) {
            runCatching { Shell.cmd("pm install-abandon $sessionId").exec() }
            postError(
                download.packageName,
                error.localizedMessage,
                error.stackTraceToString(),
                download
            )
            return false
        }
    }

    private fun quote(argument: String): String = "'" + argument.replace("'", "'\"'\"'") + "'"
}
