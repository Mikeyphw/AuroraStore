/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import android.content.Context
import android.content.pm.PackageInstaller
import android.net.Uri
import android.os.Build
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/** API36: verification and explicit consent gates, NO APK installation is committed. */
@RunWith(AndroidJUnit4::class)
class ArtifactInstallSessionDeviceTest {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val prefs get() = context.getSharedPreferences(
        "artifact_import_session_receipts", Context.MODE_PRIVATE
    )

    @Test
    fun signedInstalledApkCanBeRevalidatedWithoutOSInstall() {
        assertThat(Build.VERSION.SDK_INT).isEqualTo(36)
        val file = File(context.applicationInfo.sourceDir)
        val staged = ArtifactPrivateStager.stage(context, Uri.fromFile(file), "source.apk") { false }
        try {
            val import = ArtifactApkVerifier.verify(
                context, staged, ArtifactProvenance(ArtifactSource.LOCAL_DOCUMENT)
            ) { false }
            ArtifactApkVerifier.revalidateForInstall(context, import) { false }
            assertThat(import.signerMatchesInstalled).isTrue()
            assertThat(import.installedVersion).isNotNull()
        } finally {
            staged.discard()
        }
    }

    @Test
    fun missingInstallConsentNeverCreatesAnOSSession() {
        assertThat(Build.VERSION.SDK_INT).isEqualTo(36)
        val file = File(context.applicationInfo.sourceDir)
        val staged = ArtifactPrivateStager.stage(context, Uri.fromFile(file), "source.apk") { false }
        try {
            val import = ArtifactApkVerifier.verify(
                context, staged, ArtifactProvenance(ArtifactSource.LOCAL_DOCUMENT)
            ) { false }
            val before = context.packageManager.packageInstaller.mySessions.map { it.sessionId }.toSet()
            assertThat(runCatching {
                ArtifactInstallSession.install(context, import, false, false, false) { false }
            }.isFailure).isTrue()
            val after = context.packageManager.packageInstaller.mySessions.map { it.sessionId }.toSet()
            assertThat(after).containsExactlyElementsIn(before)
        } finally {
            staged.discard()
        }
    }

    @Test
    fun modifiedByteAfterVerificationIsRefusedBeforeCreatingSession() {
        assertThat(Build.VERSION.SDK_INT).isEqualTo(36)
        val file = File(context.applicationInfo.sourceDir)
        val staged = ArtifactPrivateStager.stage(context, Uri.fromFile(file), "source.apk") { false }
        try {
            val import = ArtifactApkVerifier.verify(
                context, staged, ArtifactProvenance(ArtifactSource.LOCAL_DOCUMENT)
            ) { false }
            val base = staged.apks.single().file
            assertThat(base.setWritable(true)).isTrue()
            base.appendBytes(byteArrayOf(9, 8, 7))
            assertThat(runCatching {
                ArtifactApkVerifier.revalidateForInstall(context, import) { false }
            }.isFailure).isTrue()
        } finally {
            staged.discard()
        }
    }

    @Test
    fun foreignSessionAndCallbackReplayAreRejected() {
        val session = 987234
        val generation = 998L
        val key = "session_${session}_"
        prefs.edit().putLong(key + "generation", generation)
            .putString(key + "state", ArtifactSessionReceiptPolicy.State.AWAITING_ANDROID.name)
            .commit()
        try {
            assertThat(ArtifactInstallSession.recordStatus(
                context, session, generation, session + 1,
                PackageInstaller.STATUS_PENDING_USER_ACTION
            )).isFalse()
            assertThat(ArtifactInstallSession.recordStatus(
                context, session, generation, session,
                PackageInstaller.STATUS_PENDING_USER_ACTION
            )).isTrue()
            assertThat(ArtifactInstallSession.recordStatus(
                context, session, generation, session,
                PackageInstaller.STATUS_PENDING_USER_ACTION
            )).isFalse()
            assertThat(ArtifactInstallSession.recordStatus(
                context, session, generation, session, PackageInstaller.STATUS_SUCCESS
            )).isTrue()
            assertThat(ArtifactInstallSession.recordStatus(
                context, session, generation, session, PackageInstaller.STATUS_FAILURE
            )).isFalse()
        } finally {
            prefs.edit().remove(key + "generation").remove(key + "state").commit()
        }
    }

    @Test
    fun separateSessionsRetainSeparateReceiptState() {
        val first = 987235
        val second = 987236
        val generation = 999L
        for (id in listOf(first, second)) {
            prefs.edit().putLong("session_${id}_generation", generation)
                .putString(
                    "session_${id}_state",
                    ArtifactSessionReceiptPolicy.State.AWAITING_ANDROID.name
                ).commit()
        }
        try {
            assertThat(ArtifactInstallSession.recordStatus(
                context, first, generation, first, PackageInstaller.STATUS_SUCCESS
            )).isTrue()
            assertThat(prefs.getString("session_${first}_state", null))
                .isEqualTo(ArtifactSessionReceiptPolicy.State.INSTALLED_BY_ANDROID.name)
            assertThat(prefs.getString("session_${second}_state", null))
                .isEqualTo(ArtifactSessionReceiptPolicy.State.AWAITING_ANDROID.name)
        } finally {
            for (id in listOf(first, second)) {
                prefs.edit().remove("session_${id}_generation")
                    .remove("session_${id}_state").commit()
            }
        }
    }
}
