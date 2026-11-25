/*
 * SPDX-FileCopyrightText: 2026 Aurora OSS
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

package com.aurora.store.data.activity

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.util.Log
import androidx.core.content.FileProvider
import androidx.core.content.IntentCompat
import com.aurora.Constants.PACKAGE_NAME_PLAY_STORE
import com.aurora.extensions.TAG
import com.aurora.store.AuroraApp
import com.aurora.store.BuildConfig
import com.aurora.store.data.event.InstallAttempt
import com.aurora.store.data.event.InstallerEvent
import com.aurora.store.data.installer.InstallerBackendPolicy
import com.aurora.store.data.installer.MicroGInstaller.Companion.buildMicroGInstallIntent
import com.aurora.store.data.room.download.Download
import com.aurora.store.util.PackageUtil
import java.io.File

class MicroGInstallerActivity : Activity() {

    companion object {
        private const val REQUEST_CODE = 1001
        const val EXTRA_FILES = "extra_files"
        const val EXTRA_PACKAGE_NAME = "extra_package_name"
        const val EXTRA_VERSION = "extra_install_version"
        const val EXTRA_ATTEMPT = "extra_install_attempt"

        fun launch(context: Context, download: Download, files: List<File>) {
            val uris = files.map { file ->
                val uri = FileProvider.getUriForFile(
                    context,
                    "${BuildConfig.APPLICATION_ID}.fileProvider",
                    file
                )

                context.grantUriPermission(
                    PACKAGE_NAME_PLAY_STORE,
                    uri,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION
                )

                uri
            }

            val intent = Intent(context, MicroGInstallerActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                putExtra(EXTRA_PACKAGE_NAME, download.packageName)
                putExtra(EXTRA_VERSION, download.versionCode)
                putExtra(EXTRA_ATTEMPT, download.downloadedAt)
                putExtra(EXTRA_FILES, ArrayList(uris))
            }

            context.startActivity(intent)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val files: ArrayList<Uri>? =
            IntentCompat.getParcelableArrayListExtra(intent, EXTRA_FILES, Uri::class.java)

        if (files.isNullOrEmpty()) {
            Log.e(TAG, "No files provided, cannot proceed with microG installation")
            reportFailure("No APKs available for microG", cancelled = false)
            return finish()
        }

        runCatching {
            @Suppress("DEPRECATION")
            startActivityForResult(buildMicroGInstallIntent(files), REQUEST_CODE)
        }.onFailure { error ->
            reportFailure(error.localizedMessage ?: "microG installer unavailable", false)
            finish()
        }
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != REQUEST_CODE) return
        val packageName = intent.getStringExtra(EXTRA_PACKAGE_NAME) ?: return finish()
        val versionCode = intent.getLongExtra(EXTRA_VERSION, -1L)
        val downloadedAt = intent.getLongExtra(EXTRA_ATTEMPT, -1L)
        if (versionCode <= 0L || downloadedAt < 0L) return finish()
        val attempt = InstallAttempt(versionCode, downloadedAt)
        val installed = InstallerBackendPolicy.isInstalled(
            PackageUtil.getInstalledVersionCode(this, packageName),
            versionCode
        )
        if (resultCode == RESULT_OK && installed) {
            AuroraApp.events.send(InstallerEvent.Installed(packageName, attempt))
        } else if (resultCode == RESULT_CANCELED) {
            reportFailure("microG installation cancelled", cancelled = true)
        } else if (resultCode != RESULT_OK) {
            reportFailure("microG did not confirm installation", cancelled = false)
        }
        // RESULT_OK without a verified installed version is not terminal success; R2A
        // recovery will observe the package and reconcile the persisted generation.
        finish()
    }

    private fun reportFailure(reason: String, cancelled: Boolean) {
        val packageName = intent.getStringExtra(EXTRA_PACKAGE_NAME) ?: return
        val versionCode = intent.getLongExtra(EXTRA_VERSION, -1L)
        val downloadedAt = intent.getLongExtra(EXTRA_ATTEMPT, -1L)
        if (versionCode <= 0L || downloadedAt < 0L) return
        AuroraApp.events.send(
            InstallerEvent.Failed(
                packageName = packageName,
                error = reason,
                cancelled = cancelled,
                attempt = InstallAttempt(versionCode, downloadedAt)
            )
        )
    }
}
