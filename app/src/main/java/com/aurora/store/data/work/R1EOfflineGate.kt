/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.work

import android.content.Context
import androidx.work.Data
import java.io.File
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull

/**
 * An intentionally narrow offline acceptance seam used only by DEBUG DownloadWorker instances.
 * This is never an alternate Google Play delivery source for a release build.
 */
internal object R1EOfflineGate {
    const val ENABLED = "R1E_OFFLINE_FIXTURE"
    const val URL = "R1E_URL"
    const val SIZE = "R1E_SIZE"
    const val SHA256 = "R1E_SHA256"

    private val fixturePackage = Regex("com\\.aurora\\.r1e\\.fixture\\.[a-z0-9_]+")
    private val sha256 = Regex("[0-9a-f]{64}")

    fun enabled(data: Data): Boolean = data.getBoolean(ENABLED, false)

    fun allowed(packageName: String, data: Data): Boolean {
        if (!enabled(data) || !fixturePackage.matches(packageName)) return false
        val endpoint = data.getString(URL)?.toHttpUrlOrNull() ?: return false
        val bytes = data.getLong(SIZE, -1L)
        val checksum = data.getString(SHA256) ?: return false
        return endpoint.scheme == "http" &&
            endpoint.host == "127.0.0.1" &&
            endpoint.port >= 1024 &&
            endpoint.username.isEmpty() &&
            endpoint.password.isEmpty() &&
            endpoint.query == null &&
            bytes in 1L..1_048_576L &&
            sha256.matches(checksum)
    }

    fun file(context: Context, packageName: String, attemptKey: Long): File =
        File(context.cacheDir, "r1e-$packageName-$attemptKey.apk")
}
