/*
 * SPDX-FileCopyrightText: 2021 Aurora OSS
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

package com.aurora.store.data.receiver

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.content.pm.PackageInstaller.EXTRA_SESSION_ID
import android.util.Log
import androidx.core.content.IntentCompat
import com.aurora.extensions.TAG
import com.aurora.extensions.runOnUiThread
import com.aurora.store.AuroraApp
import com.aurora.store.data.event.InstallAttempt
import com.aurora.store.data.event.InstallerEvent
import com.aurora.store.data.installer.AppInstaller.Companion.ACTION_INSTALL_STATUS
import com.aurora.store.data.installer.AppInstaller.Companion.EXTRA_ATTEMPT_KEY
import com.aurora.store.data.installer.AppInstaller.Companion.EXTRA_DISPLAY_NAME
import com.aurora.store.data.installer.AppInstaller.Companion.EXTRA_PACKAGE_NAME
import com.aurora.store.data.installer.AppInstaller.Companion.EXTRA_PARENT_PACKAGE_NAME
import com.aurora.store.data.installer.AppInstaller.Companion.EXTRA_VERSION_CODE
import com.aurora.store.data.installer.InstallResultPolicy
import com.aurora.store.data.installer.base.InstallerBase
import com.aurora.store.data.room.download.DownloadDao
import com.aurora.store.util.NotificationUtil
import com.aurora.store.util.PackageUtil
import com.aurora.store.util.PathUtil
import com.aurora.store.util.Preferences
import com.aurora.store.util.Preferences.PREFERENCE_AUTO_DELETE
import dagger.hilt.EntryPoint
import dagger.hilt.InstallIn
import dagger.hilt.android.EntryPointAccessors
import dagger.hilt.components.SingletonComponent
import kotlinx.coroutines.launch

@EntryPoint
@InstallIn(SingletonComponent::class)
internal interface InstallerStatusEntryPoint {
    fun downloadDao(): DownloadDao
}

abstract class BaseInstallerStatusReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context?, intent: Intent?) {
        if (context == null || intent?.action != ACTION_INSTALL_STATUS) return

        val packageName = intent.getStringExtra(EXTRA_PACKAGE_NAME) ?: return
        val displayName = intent.getStringExtra(EXTRA_DISPLAY_NAME) ?: packageName
        val parentPackageName = intent.getStringExtra(EXTRA_PARENT_PACKAGE_NAME) ?: packageName
        val versionCode = intent.getLongExtra(EXTRA_VERSION_CODE, -1L)
        val downloadedAt = intent.getLongExtra(EXTRA_ATTEMPT_KEY, -1L)
        val sessionId = intent.getIntExtra(EXTRA_SESSION_ID, -1)
        // STATUS_PENDING_USER_ACTION is -1; use a distinct sentinel for a missing status.
        val status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, Int.MIN_VALUE)
        val extra = intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE)

        if (versionCode < 0 || sessionId < 0 || status == Int.MIN_VALUE) {
            Log.w(TAG, "Ignoring incomplete installer callback for $packageName")
            return
        }

        val identity = InstallAttempt(versionCode, downloadedAt, sessionId)
        Log.i(
            TAG,
            "$packageName ($versionCode) attempt=$downloadedAt session=$sessionId status=$status"
        )

        // Shared library sessions have no independent Room download row. Their callbacks are
        // still needed to continue the library chain and prompt for system authorization.
        if (parentPackageName != packageName || PackageUtil.isSharedLibrary(context, packageName)) {
            when (status) {
                PackageInstaller.STATUS_SUCCESS -> return
                PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                    doAppropriatePrompt(context, intent, sessionId)
                    return
                }

                else -> {
                    notifyUser(context, packageName, displayName, status)
                    postStatus(status, packageName, extra, context, identity)
                    return
                }
            }
        }

        // A broadcast can arrive after the original download was cancelled, retried or
        // superseded. Do not show a prompt, delete APKs, or emit an event for a stale attempt.
        if (downloadedAt < 0L) {
            Log.w(TAG, "Unattributed installer callback ignored for $packageName")
            return
        }
        val pendingResult = goAsync()
        AuroraApp.scope.launch {
            try {
                val downloadDao = EntryPointAccessors
                    .fromApplication(context, InstallerStatusEntryPoint::class.java)
                    .downloadDao()
                val current = downloadDao.getDownload(packageName)
                val matchesAttempt = InstallResultPolicy.matches(
                    current.versionCode,
                    current.downloadedAt,
                    identity.versionCode,
                    identity.downloadedAt
                )
                if (!matchesAttempt) {
                    Log.w(TAG, "Discarding stale installation result for $packageName")
                    return@launch
                }

                val outcome = when (status) {
                    PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                        InstallResultPolicy.Outcome.PENDING_USER_ACTION
                    }

                    PackageInstaller.STATUS_SUCCESS -> InstallResultPolicy.Outcome.SUCCESS
                    else -> InstallResultPolicy.Outcome.FAILURE
                }
                val replacement = InstallResultPolicy.next(
                    current.status,
                    outcome,
                    current.hasDownloadedFiles(context)
                ) ?: return@launch
                val updated = downloadDao.transitionInstallAttempt(
                    packageName,
                    identity.versionCode,
                    identity.downloadedAt,
                    current.status,
                    replacement
                )
                if (updated == 0) {
                    Log.i(TAG, "Installer callback lost a concurrent transition: $packageName")
                    return@launch
                }

                when (status) {
                    PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                        AuroraApp.events.send(
                            InstallerEvent.PendingUserAction(packageName, identity)
                        )
                        doAppropriatePrompt(context, intent, sessionId)
                    }

                    PackageInstaller.STATUS_SUCCESS -> {
                        AuroraApp.enqueuedInstalls.remove(packageName)
                        InstallerBase.notifyInstallation(context, displayName, packageName)
                        if (Preferences.getBoolean(context, PREFERENCE_AUTO_DELETE)) {
                            PathUtil.getAppDownloadDir(context, packageName, versionCode)
                                .deleteRecursively()
                        }
                        postStatus(status, packageName, extra, context, identity)
                    }

                    else -> {
                        AuroraApp.enqueuedInstalls.remove(packageName)
                        if (status != PackageInstaller.STATUS_FAILURE_ABORTED) {
                            notifyUser(context, packageName, displayName, status)
                        }
                        postStatus(status, packageName, extra, context, identity)
                    }
                }
            } catch (error: Exception) {
                // Fail closed: a database error must never authorize an uncorrelated callback.
                Log.e(TAG, "Unable to reconcile installer callback for $packageName", error)
            } finally {
                pendingResult.finish()
            }
        }
    }

    private fun notifyUser(
        context: Context,
        packageName: String,
        displayName: String,
        status: Int
    ) {
        NotificationUtil.notifyInstallFailed(
            context,
            packageName,
            displayName,
            InstallerBase.getErrorString(context, status)
        )
    }

    internal fun promptUser(context: Context, intent: Intent) {
        runOnUiThread {
            val launchIntent = IntentCompat.getParcelableExtra(
                intent,
                Intent.EXTRA_INTENT,
                Intent::class.java
            )

            if (launchIntent == null) {
                Log.w(TAG, "No launch intent found in the installation request.")
                return@runOnUiThread
            }

            launchIntent.putExtra(Intent.EXTRA_NOT_UNKNOWN_SOURCE, true)
            launchIntent.putExtra(Intent.EXTRA_INSTALLER_PACKAGE_NAME, context.packageName)
            launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

            if (!AuroraApp.isForeground) {
                Log.i(TAG, "Aurora is backgrounded, notifying instead of prompting")
                val packageName = intent.getStringExtra(EXTRA_PACKAGE_NAME) ?: return@runOnUiThread
                NotificationUtil.notifyInstallPrompt(
                    context = context,
                    packageName = packageName,
                    displayName = intent.getStringExtra(EXTRA_DISPLAY_NAME) ?: packageName,
                    confirmIntent = launchIntent
                )
                return@runOnUiThread
            }

            try {
                context.startActivity(launchIntent)
            } catch (exception: Exception) {
                Log.e(TAG, "Failed to launch intent!", exception)
            }
        }
    }

    open fun doAppropriatePrompt(context: Context, intent: Intent, sessionId: Int) {
        promptUser(context, intent)
    }

    open fun postStatus(
        status: Int,
        packageName: String,
        extra: String?,
        context: Context,
        attempt: InstallAttempt? = null
    ) {
        val event = when (status) {
            PackageInstaller.STATUS_SUCCESS -> InstallerEvent.Installed(
                packageName = packageName,
                attempt = attempt
            )

            else -> InstallerEvent.Failed(
                packageName = packageName,
                error = InstallerBase.getErrorString(context, status),
                extra = extra,
                cancelled = status == PackageInstaller.STATUS_FAILURE_ABORTED,
                attempt = attempt
            )
        }

        AuroraApp.events.send(event)
    }
}
