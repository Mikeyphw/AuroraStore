/*
 * SPDX-FileCopyrightText: 2021 Aurora OSS
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

package com.aurora.store.data.installer

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.content.pm.PackageInstaller
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import com.aurora.services.IPrivilegedCallback
import com.aurora.services.IPrivilegedService
import com.aurora.store.AuroraApp
import com.aurora.store.BuildConfig
import com.aurora.store.R
import com.aurora.store.data.installer.base.InstallerBase
import com.aurora.store.data.model.Installer
import com.aurora.store.data.model.InstallerInfo
import com.aurora.store.data.room.download.Download
import dagger.hilt.android.qualifiers.ApplicationContext
import java.util.concurrent.atomic.AtomicBoolean
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
@Deprecated("Deprecated in favour of RootInstaller")
class ServiceInstaller @Inject constructor(
    @ApplicationContext private val context: Context
) : InstallerBase(context) {

    companion object {
        const val ACTION_INSTALL_REPLACE_EXISTING = 2
        const val PRIVILEGED_EXTENSION_PACKAGE_NAME = "com.aurora.services"
        const val PRIVILEGED_EXTENSION_SERVICE_INTENT = "com.aurora.services.IPrivilegedService"
        private const val CALLBACK_TIMEOUT_MS = 45_000L

        val installerInfo: InstallerInfo
            get() = InstallerInfo(
                id = 3,
                installer = Installer.SERVICE,
                installerPackageNames = listOf(PRIVILEGED_EXTENSION_PACKAGE_NAME),
                title = R.string.pref_install_mode_services,
                subtitle = R.string.services_installer_subtitle,
                description = R.string.services_installer_desc
            )
    }

    override fun install(download: Download) {
        super.install(download)
        // Reserve before posting asynchronous binder work; a second caller must not
        // bind the same request while the first bind is still pending.
        val reserved = synchronized(AuroraApp.enqueuedInstalls) {
            AuroraApp.enqueuedInstalls.add(download.packageName)
        }
        if (!reserved) return
        if (!AppInstaller.hasAuroraService(context)) {
            removeFromInstallQueue(download.packageName)
            postError(
                download.packageName,
                context.getString(R.string.installer_status_failure),
                context.getString(R.string.installer_service_unavailable),
                download
            )
            return
        }
        val files = getFiles(download.packageName, download.versionCode)
        if (files.isEmpty()) {
            removeFromInstallQueue(download.packageName)
            postError(download.packageName, "No APK files for Aurora Services", null, download)
            return
        }
        val uris = files.map { file ->
            getUri(file).also { uri ->
                context.grantUriPermission(
                    PRIVILEGED_EXTENSION_PACKAGE_NAME,
                    uri,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION
                )
            }
        }
        val main = Handler(Looper.getMainLooper())
        val finished = AtomicBoolean(false)
        val packageName = download.packageName
        var bound = false
        lateinit var connection: ServiceConnection

        fun complete(returnCode: Int, error: String?) {
            if (!finished.compareAndSet(false, true)) return
            AuroraApp.enqueuedInstalls.remove(packageName)
            if (bound) main.post { runCatching { context.unbindService(connection) } }
            if (returnCode == PackageInstaller.STATUS_SUCCESS) {
                onInstallationSuccess(download)
            } else {
                postError(
                    packageName,
                    getErrorString(context, returnCode),
                    error,
                    download
                )
            }
        }

        connection = object : ServiceConnection {
            override fun onServiceConnected(name: ComponentName, binder: IBinder) {
                if (finished.get()) return
                val service = IPrivilegedService.Stub.asInterface(binder)
                try {
                    check(service != null && service.hasPrivilegedPermissions()) {
                        "Aurora Services missing privileged permission"
                    }
                    val callback = object : IPrivilegedCallback.Stub() {
                        override fun handleResult(packageName: String, returnCode: Int) {
                            if (packageName == download.packageName) complete(returnCode, null)
                        }

                        override fun handleResultX(
                            packageName: String,
                            returnCode: Int,
                            extra: String?
                        ) {
                            if (packageName == download.packageName) complete(returnCode, extra)
                        }
                    }
                    // Choose a single AIDL method, never retry another after an uncertain
                    // binder failure: a fallback could submit the same APK twice.
                    if (service.isMoreMethodImplemented) {
                        service.installSplitPackageMore(
                            packageName,
                            uris,
                            ACTION_INSTALL_REPLACE_EXISTING,
                            BuildConfig.APPLICATION_ID,
                            callback,
                            files.map { it.absolutePath }
                        )
                    } else {
                        service.installSplitPackageX(
                            packageName,
                            uris,
                            ACTION_INSTALL_REPLACE_EXISTING,
                            BuildConfig.APPLICATION_ID,
                            callback
                        )
                    }
                } catch (error: Exception) {
                    complete(PackageInstaller.STATUS_FAILURE, error.localizedMessage)
                }
            }

            override fun onServiceDisconnected(name: ComponentName) {
                complete(PackageInstaller.STATUS_FAILURE, "Aurora Services disconnected")
            }
        }

        main.post {
            if (finished.get()) return@post
            try {
                val intent = Intent(PRIVILEGED_EXTENSION_SERVICE_INTENT).apply {
                    setPackage(PRIVILEGED_EXTENSION_PACKAGE_NAME)
                }
                bound = context.bindService(intent, connection, Context.BIND_AUTO_CREATE)
                if (!bound) {
                    complete(PackageInstaller.STATUS_FAILURE, "Aurora Services binding refused")
                } else if (finished.get()) {
                    // A synchronous callback may finish before bindService returns.
                    runCatching { context.unbindService(connection) }
                }
            } catch (error: Exception) {
                complete(PackageInstaller.STATUS_FAILURE, error.localizedMessage)
            }
        }
        main.postDelayed(
            { complete(PackageInstaller.STATUS_FAILURE, "Aurora Services timeout") },
            CALLBACK_TIMEOUT_MS
        )
    }
}
