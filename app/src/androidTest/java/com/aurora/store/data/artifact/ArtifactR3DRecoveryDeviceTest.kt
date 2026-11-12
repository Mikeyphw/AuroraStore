/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.artifact

import android.content.Context
import android.content.pm.PackageInstaller
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/** API36 read-only receipt replay/race tests. NO installer session is created. */
@RunWith(AndroidJUnit4::class)
class ArtifactR3DRecoveryDeviceTest {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val prefs get() = context.getSharedPreferences("artifact_import_session_receipts", Context.MODE_PRIVATE)

    private fun withReceipt(session: Int, generation: Long = 994776L, test: (String) -> Unit) {
        val prefix = "session_${session}_"
        assertThat(prefs.edit().putLong(prefix + "generation", generation)
            .putString(prefix + "state", ArtifactSessionReceiptPolicy.State.AWAITING_ANDROID.name)
            .commit()).isTrue()
        try { test(prefix) } finally {
            prefs.edit().remove(prefix + "generation").remove(prefix + "state")
                .remove(prefix + "android_status_code").commit()
        }
    }

    @Test fun racingSuccessAndRejectionCannotOverwriteTerminalReceipt() {
        withReceipt(991901) { prefix ->
            val workers = Executors.newFixedThreadPool(2)
            val ready = CountDownLatch(2)
            val start = CountDownLatch(1)
            try {
                val events = listOf(PackageInstaller.STATUS_SUCCESS, PackageInstaller.STATUS_FAILURE)
                val results = events.map { code -> workers.submit<Boolean> {
                    ready.countDown()
                    if (!start.await(10, TimeUnit.SECONDS)) return@submit false
                    ArtifactInstallSession.recordStatus(context, 991901, 994776L, 991901, code)
                }}
                assertThat(ready.await(10, TimeUnit.SECONDS)).isTrue()
                start.countDown()
                assertThat(results.count { it.get(15, TimeUnit.SECONDS) }).isEqualTo(1)
                val state = prefs.getString(prefix + "state", "")
                assertThat(state).isAnyOf(
                    ArtifactSessionReceiptPolicy.State.INSTALLED_BY_ANDROID.name,
                    ArtifactSessionReceiptPolicy.State.ANDROID_REJECTED.name
                )
                assertThat(ArtifactInstallSession.recordStatus(
                    context, 991901, 994776L, 991901, PackageInstaller.STATUS_SUCCESS)).isFalse()
            } finally { workers.shutdownNow() }
        }
    }

    @Test fun foreignAndStaleCallbacksCannotChangeStoredReceipt() {
        withReceipt(991902) { prefix ->
            assertThat(ArtifactInstallSession.recordStatus(context, 991902, 994775L,
                991902, PackageInstaller.STATUS_SUCCESS)).isFalse()
            assertThat(ArtifactInstallSession.recordStatus(context, 991902, 994776L,
                991903, PackageInstaller.STATUS_SUCCESS)).isFalse()
            assertThat(ArtifactInstallSession.recordStatus(context, 991902, 994776L,
                991902, 9999)).isFalse()
            assertThat(prefs.getString(prefix + "state", null))
                .isEqualTo(ArtifactSessionReceiptPolicy.State.AWAITING_ANDROID.name)
        }
    }

    @Test fun pendingUserApprovalCannotReplayConfirmationUi() {
        withReceipt(991903) { prefix ->
            assertThat(ArtifactInstallSession.recordStatus(context, 991903, 994776L,
                991903, PackageInstaller.STATUS_PENDING_USER_ACTION)).isTrue()
            assertThat(ArtifactInstallSession.recordStatus(context, 991903, 994776L,
                991903, PackageInstaller.STATUS_PENDING_USER_ACTION)).isFalse()
            assertThat(ArtifactInstallSession.recordPresentationFailure(
                context, 991903, 994776L)).isTrue()
            assertThat(prefs.getString(prefix + "state", ""))
                .isEqualTo(ArtifactSessionReceiptPolicy.State.APPROVAL_UI_UNAVAILABLE.name)
        }
    }

    @Test fun racingUiFailureAndTerminalResultDoesNotDowngradeOutcome() {
        withReceipt(991904) { prefix ->
            assertThat(ArtifactInstallSession.recordStatus(context, 991904, 994776L,
                991904, PackageInstaller.STATUS_PENDING_USER_ACTION)).isTrue()
            val workers=Executors.newFixedThreadPool(2)
            val gate=CountDownLatch(1)
            try {
                val ui=workers.submit<Boolean> { gate.await();
                    ArtifactInstallSession.recordPresentationFailure(context, 991904, 994776L) }
                val os=workers.submit<Boolean> { gate.await();
                    ArtifactInstallSession.recordStatus(context, 991904, 994776L, 991904,
                        PackageInstaller.STATUS_SUCCESS) }
                gate.countDown()
                ui.get(15, TimeUnit.SECONDS)
                assertThat(os.get(15, TimeUnit.SECONDS)).isTrue()
                assertThat(prefs.getString(prefix + "state", ""))
                    .isEqualTo(ArtifactSessionReceiptPolicy.State.INSTALLED_BY_ANDROID.name)
            } finally { workers.shutdownNow() }
        }
    }
}
