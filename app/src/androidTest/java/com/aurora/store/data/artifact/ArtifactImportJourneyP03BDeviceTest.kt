/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import android.content.pm.ActivityInfo
import android.graphics.Bitmap
import android.net.Uri
import android.os.Build
import android.os.SystemClock
import android.util.TypedValue
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.ScrollView
import android.widget.Spinner
import android.widget.TextView
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.google.common.truth.Truth.assertThat
import java.io.File
import org.junit.Test
import org.junit.runner.RunWith

/**
 * P03B: real hosted Android 36 activity, genuine signed fixture through SAF
 * content provider, retry and OS configuration. No browser, PackageInstaller,
 * Play availability or accessibility-service activation in this default gate.
 */
@RunWith(AndroidJUnit4::class)
class ArtifactImportJourneyP03BDeviceTest {
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val activityClass = ArtifactImportActivity::class.java

    private fun all(root: View): List<View> = buildList {
        add(root)
        if (root is ViewGroup) {
            for (i in 0 until root.childCount) addAll(all(root.getChildAt(i)))
        }
    }

    private fun views(activity: ArtifactImportActivity) =
        all(activity.findViewById(android.R.id.content))
    private fun button(ui: List<View>, title: String) =
        ui.filterIsInstance<Button>().single { it.text.toString() == title }
    private fun texts(ui: List<View>) = ui.filterIsInstance<TextView>()
        .joinToString("\n") { it.text.toString() }

    private fun await(scenario: ActivityScenario<ArtifactImportActivity>, needle: String) {
        var observed = ""
        repeat(240) {
            scenario.onActivity { observed = texts(views(it)) }
            if (observed.contains(needle)) return
            SystemClock.sleep(250)
        }
        throw AssertionError("P03B UI did not reach: $needle; ${observed.take(250)}")
    }

    private fun select(activity: ArtifactImportActivity, name: String) {
        val method = activityClass.getDeclaredMethod("handlePickedFile", Uri::class.java)
        method.isAccessible = true
        method.invoke(activity, Uri.parse("content://com.aurora.store.debug.r3c07p02/$name"))
    }

    private fun local(scenario: ActivityScenario<ArtifactImportActivity>) {
        scenario.onActivity { views(it).filterIsInstance<Spinner>().single().setSelection(1) }
        await(scenario, "Local file not selected or verified")
    }

    private fun screenshot(name: String) {
        val capture = instrumentation.uiAutomation.takeScreenshot()
        assertThat(capture).isNotNull()
        requireNotNull(capture).useBitmap { bitmap ->
            val file = File(instrumentation.targetContext.filesDir, name)
            file.outputStream().use { stream ->
                assertThat(bitmap.compress(Bitmap.CompressFormat.PNG, 100, stream)).isTrue()
                stream.flush()
            }
            assertThat(file.length()).isGreaterThan(1024L)
        }
    }

    private inline fun Bitmap.useBitmap(action: (Bitmap) -> Unit) {
        try { action(this) } finally { recycle() }
    }

    @Test fun explicitProviderChoiceAndRefusalNeverAutoNavigatesOrInstalls() {
        assertThat(Build.VERSION.SDK_INT).isEqualTo(36)
        ActivityScenario.launch(activityClass).use { scenario ->
            scenario.onActivity { activity ->
                val ui = views(activity)
                assertThat(button(ui, "Request Android installation").isEnabled).isFalse()
                assertThat(texts(ui)).contains("Exact-version availability: UNKNOWN")
                val choices = ui.filterIsInstance<Spinner>().single()
                choices.setSelection(4) // APKMirror, browser handoff only
            }
            await(scenario, "Listing not checked; official browser handoff only")
            scenario.onActivity { activity ->
                val ui = views(activity)
                assertThat(button(ui, "Request Android installation").isEnabled).isFalse()
                button(ui, "Open chosen provider (manual browser handoff)").performClick()
            }
            await(scenario, "Approve this alternative provider")
            scenario.onActivity { activity ->
                assertThat(texts(views(activity))).doesNotContain("Android reported installation SUCCESS")
                assertThat(button(views(activity), "Request Android installation").isEnabled).isFalse()
            }
            screenshot("r3c07_p03b_provider_choice.png")
        }
    }

    @Test fun invalidDocumentGetsSafeManualRetryAndFreshSignedReview() {
        ActivityScenario.launch(activityClass).use { scenario ->
            local(scenario)
            scenario.onActivity { select(it, "invalid.apk") }
            await(scenario, "Nothing installed. Choose a file again manually")
            scenario.onActivity { activity ->
                val ui = views(activity)
                assertThat(button(ui, "Retry file selection").visibility).isEqualTo(View.VISIBLE)
                assertThat(button(ui, "Request Android installation").isEnabled).isFalse()
                assertThat(texts(ui)).doesNotContain("content://")
                assertThat(ui.filterIsInstance<CheckBox>().all { !it.isChecked }).isTrue()
            }
            screenshot("r3c07_p03b_failed_retry.png")
            scenario.onActivity { select(it, "signed.apk") }
            await(scenario, "SIGNED APK FILES VERIFIED — NOT INSTALLED")
            scenario.onActivity { activity ->
                val ui = views(activity)
                assertThat(button(ui, "Retry file selection").visibility).isEqualTo(View.GONE)
                assertThat(button(ui, "Request Android installation").isEnabled).isFalse()
                assertThat(ui.filterIsInstance<CheckBox>().all { !it.isChecked }).isTrue()
                assertThat(texts(ui)).contains("Publisher identity: NOT independently authenticated")
            }
            screenshot("r3c07_p03b_signed_review.png")
        }
    }

    @Test fun requestedVersionMismatchBlocksRealSignedFileConsent() {
        ActivityScenario.launch(activityClass).use { scenario ->
            local(scenario)
            scenario.onActivity { activity ->
                val version = views(activity).filterIsInstance<EditText>().single {
                    it.hint.toString().contains("version code")
                }
                version.setText("9223372036854775808")
                select(activity, "signed.apk")
            }
            await(scenario, "SIGNED APK FILES VERIFIED — NOT INSTALLED")
            scenario.onActivity { activity ->
                val ui = views(activity)
                assertThat(texts(ui)).contains("No installation approval is possible")
                assertThat(button(ui, "Request Android installation").isEnabled).isFalse()
                ui.filterIsInstance<CheckBox>().filter { it.visibility == View.VISIBLE }
                    .forEach { it.isChecked = true }
                assertThat(button(ui, "Request Android installation").isEnabled).isFalse()
            }
        }
    }

    @Test fun userSourceChangeAndActivityRecreateDiscardAllOldConsent() {
        ActivityScenario.launch(activityClass).use { scenario ->
            local(scenario)
            scenario.onActivity { select(it, "signed.apk") }
            await(scenario, "SIGNED APK FILES VERIFIED — NOT INSTALLED")
            scenario.onActivity { activity ->
                val ui = views(activity)
                ui.filterIsInstance<CheckBox>().filter { it.visibility == View.VISIBLE }
                    .forEach { it.isChecked = true }
                views(activity).filterIsInstance<Spinner>().single().setSelection(4)
            }
            await(scenario, "Provider changed. Select a new file")
            scenario.recreate()
            scenario.onActivity { activity ->
                val ui = views(activity)
                assertThat(button(ui, "Request Android installation").isEnabled).isFalse()
                assertThat(ui.filterIsInstance<CheckBox>().all { !it.isChecked }).isTrue()
                assertThat(texts(ui)).contains("No verified files")
            }
        }
    }

    @Test fun realLandscapeConfigurationAndLargeTextRetainSafeActions() {
        ActivityScenario.launch(activityClass).use { scenario ->
            scenario.onActivity { activity ->
                activity.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE
            }
            await(scenario, "Exact-version availability: UNKNOWN")
            scenario.onActivity { activity ->
                val ui = views(activity)
                val scroll = ui.filterIsInstance<ScrollView>().single()
                assertThat(scroll.isFillViewport).isTrue()
                ui.filterIsInstance<TextView>().filter { it.visibility == View.VISIBLE }
                    .forEach { it.setTextSize(TypedValue.COMPLEX_UNIT_SP, 26f) }
                assertThat(button(ui, "Request Android installation").isEnabled).isFalse()
                val retry = button(ui, "Retry file selection")
                assertThat(retry.contentDescription.toString()).contains("manual")
                assertThat(texts(ui)).doesNotContain("Android reported installation SUCCESS")
            }
        }
    }
}
