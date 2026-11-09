/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.os.Build
import android.util.Log

/** Only the app-owned PendingIntent may report installation outcome; Android is authoritative. */
class ArtifactInstallStatusReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val session = intent.getIntExtra(ArtifactInstallSession.EXTRA_SESSION, -1)
        val generation = intent.getLongExtra(ArtifactInstallSession.EXTRA_GENERATION, -1)
        val status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, Int.MIN_VALUE)
        if (!ArtifactInstallSession.recordStatus(context, session, generation, status)) {
            Log.w("AuroraArtifactImport", "Ignoring stale installation callback")
            return
        }
        if (status != PackageInstaller.STATUS_PENDING_USER_ACTION) return
        val confirmation = if (Build.VERSION.SDK_INT >= 33) {
            intent.getParcelableExtra(Intent.EXTRA_INTENT, Intent::class.java)
        } else {
            @Suppress("DEPRECATION")
            intent.getParcelableExtra(Intent.EXTRA_INTENT)
        }
        if (confirmation == null) {
            Log.e("AuroraArtifactImport", "Android confirmation intent missing")
            return
        }
        // This Intent is supplied by Android PackageInstaller, not a provider or archive.
        runCatching {
            confirmation.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(confirmation)
        }.onFailure {
            Log.e("AuroraArtifactImport", "Unable to present system confirmation", it)
        }
    }
}
