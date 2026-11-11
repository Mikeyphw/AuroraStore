/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.artifact

import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Process
import android.os.SystemClock
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.CheckBox
import android.widget.Spinner
import android.widget.TextView
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.google.common.truth.Truth.assertThat
import java.io.FileNotFoundException
import org.junit.After
import org.junit.Test
import org.junit.runner.RunWith

/** R3C08 P01: actual OS grant/revoke in a separate test APK, then production importer.
 * Never calls PackageInstaller, enables TalkBack, changes account state, or downloads.
 * No claim that revoking a permission invalidates an ALREADY OPEN file descriptor.
 */
@RunWith(AndroidJUnit4::class)
class ArtifactR3C08P01DeviceTest {
    private val instrument get() = InstrumentationRegistry.getInstrumentation()
    private val target get() = instrument.targetContext
    private val doc = Uri.parse("content://com.aurora.store.r3c08.document/signed.apk")
    private val control = Uri.parse("content://com.aurora.store.r3c08.control")
    private val activityClass = ArtifactImportActivity::class.java

    private fun control(method: String) {
        val answer = target.contentResolver.call(control, method, null, null)
        assertThat(answer?.getString("r3c08_result")).isEqualTo(method)
    }
    private fun permission(): Int = target.checkUriPermission(
        doc, Process.myPid(), Process.myUid(), Intent.FLAG_GRANT_READ_URI_PERMISSION
    )
    private fun all(view: View): List<View> = buildList {
        add(view)
        if (view is ViewGroup) for (i in 0 until view.childCount) addAll(all(view.getChildAt(i)))
    }
    private fun ui(activity: ArtifactImportActivity): List<View> =
        all(activity.findViewById(android.R.id.content))
    private fun action(ui: List<View>, text: String): Button =
        ui.filterIsInstance<Button>().single { it.text.toString() == text }
    private fun labels(ui: List<View>): String =
        ui.filterIsInstance<TextView>().joinToString("\n") { it.text.toString() }
    private fun waitFor(scenario: ActivityScenario<ArtifactImportActivity>, text: String) {
        var current = ""
        repeat(200) {
            scenario.onActivity { current = labels(ui(it)) }
            if (text in current) return
            SystemClock.sleep(250)
        }
        throw AssertionError("R3C08 UI failed to reach $text; ${current.take(320)}")
    }
    private fun local(scenario: ActivityScenario<ArtifactImportActivity>) {
        scenario.onActivity { ui(it).filterIsInstance<Spinner>().single().setSelection(1) }
        waitFor(scenario, "Local file not selected or verified")
    }
    private fun select(activity: ArtifactImportActivity, uri: Uri) {
        val f = activityClass.getDeclaredMethod("handlePickedFile", Uri::class.java)
        f.isAccessible = true
        f.invoke(activity, uri)
    }
    private fun assertNoActiveSelection(activity: ArtifactImportActivity) {
        val f = activityClass.getDeclaredField("active")
        f.isAccessible = true
        assertThat(f.get(activity)).isNull()
        val views = ui(activity)
        assertThat(action(views, "Request Android installation").isEnabled).isFalse()
        assertThat(views.filterIsInstance<CheckBox>().all { !it.isChecked }).isTrue()
    }

    @After fun revokeAnyOutstandingTestGrant() = control("revoke")

    @Test fun realAndroidUriGrantAndRevocationRejectFreshOpens() {
        assertThat(Build.VERSION.SDK_INT).isEqualTo(36)
        control("revoke")
        assertThat(permission()).isEqualTo(PackageManager.PERMISSION_DENIED)
        control("grant")
        assertThat(permission()).isEqualTo(PackageManager.PERMISSION_GRANTED)
        val firstByte = requireNotNull(target.contentResolver.openInputStream(doc)).use { it.read() }
        assertThat(firstByte).isAtLeast(0)
        control("revoke")
        assertThat(permission()).isEqualTo(PackageManager.PERMISSION_DENIED)
        val denied = runCatching {
            target.contentResolver.openInputStream(doc)?.use { it.read() }
                ?: throw FileNotFoundException("No stream after revoked permission")
        }
        assertThat(denied.isFailure).isTrue()
        val evidence = Bundle().apply {
            putString("r3c08_grant_before", "DENIED")
            putString("r3c08_grant_during", "GRANTED")
            putString("r3c08_grant_after", "DENIED")
        }
        instrument.sendStatus(0, evidence)
    }

    @Test fun revokedDocumentIsRefusedByProductionImportWithoutConsent() {
        assertThat(Build.VERSION.SDK_INT).isEqualTo(36)
        control("grant")
        assertThat(permission()).isEqualTo(PackageManager.PERMISSION_GRANTED)
        control("revoke")
        assertThat(permission()).isEqualTo(PackageManager.PERMISSION_DENIED)
        ActivityScenario.launch(activityClass).use { scenario ->
            local(scenario)
            scenario.onActivity { select(it, doc) }
            waitFor(scenario, "Import refused")
            scenario.onActivity { activity ->
                assertNoActiveSelection(activity)
                assertThat(labels(ui(activity))).doesNotContain("Android reported installation SUCCESS")
                assertThat(labels(ui(activity))).doesNotContain("content://")
            }
        }
    }

    @Test fun cancellingVerifiedSignedFileDiscardsSelectionAndAllConsent() {
        assertThat(Build.VERSION.SDK_INT).isEqualTo(36)
        ActivityScenario.launch(activityClass).use { scenario ->
            local(scenario)
            scenario.onActivity { activity ->
                select(activity, Uri.parse("content://com.aurora.store.debug.r3c07p02/signed.apk"))
            }
            waitFor(scenario, "SIGNED APK FILES VERIFIED — NOT INSTALLED")
            scenario.onActivity { activity ->
                val views = ui(activity)
                views.filterIsInstance<CheckBox>()
                    .filter { it.visibility == View.VISIBLE }
                    .forEach { it.isChecked = true }
                action(views, "Cancel current import").performClick()
                assertNoActiveSelection(activity)
                assertThat(labels(ui(activity))).contains("No verified files")
            }
        }
    }
}
