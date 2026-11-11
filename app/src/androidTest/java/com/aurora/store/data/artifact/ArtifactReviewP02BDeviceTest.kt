/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Process
import android.os.SystemClock
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.CheckBox
import android.widget.ScrollView
import android.widget.Spinner
import android.widget.TextView
import androidx.core.view.ViewCompat
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith

/**
 * P02B: independent API36 lifecycle / accessibility evidence. The host owns
 * font-scale changes and an actual process force-stop between instrumentations.
 * No PackageInstaller session, browser, Play receipt, or accessibility service
 * is enabled here. Accessibility semantics are NOT a live TalkBack test.
 */
@RunWith(AndroidJUnit4::class)
class ArtifactReviewP02BDeviceTest {
    private val cls = ArtifactImportActivity::class.java

    private fun all(view: View): List<View> = buildList {
        add(view)
        if (view is ViewGroup) {
            for (i in 0 until view.childCount) addAll(all(view.getChildAt(i)))
        }
    }

    private fun views(a: ArtifactImportActivity): List<View> =
        all(a.findViewById(android.R.id.content))

    private fun install(ui: List<View>): Button = ui.filterIsInstance<Button>().single {
        it.text.toString() == "Request Android installation"
    }

    private fun reportPid(key: String) {
        val bundle = Bundle()
        bundle.putString(key, Process.myPid().toString())
        InstrumentationRegistry.getInstrumentation().sendStatus(0, bundle)
    }

    private fun waitFor(
        scenario: ActivityScenario<ArtifactImportActivity>,
        wanted: String
    ) {
        var last = ""
        repeat(200) {
            scenario.onActivity { activity ->
                last = views(activity).filterIsInstance<TextView>()
                    .joinToString("\n") { it.text.toString() }
            }
            if (last.contains(wanted)) return
            SystemClock.sleep(250)
        }
        throw AssertionError("P02B real activity did not reach expected state: $wanted; ${last.take(350)}")
    }

    @Test fun realSystemFontScaleChangesActivityConfigurationWithoutConsent() {
        assertThat(Build.VERSION.SDK_INT).isEqualTo(36)
        ActivityScenario.launch(cls).use { scenario ->
            scenario.onActivity { activity ->
                // The host changed Android's real system setting before this
                // process launched. No fake in-test SP adjustment is credited.
                assertThat(activity.resources.configuration.fontScale).isAtLeast(1.4f)
                val ui = views(activity)
                val scroll = ui.filterIsInstance<ScrollView>().single()
                assertThat(scroll.isFillViewport).isTrue()
                assertThat(scroll.getChildAt(0)).isNotNull()
                assertThat(install(ui).isEnabled).isFalse()
                assertThat(ui.filterIsInstance<CheckBox>().all { !it.isChecked }).isTrue()
            }
        }
    }

    @Test fun accessibleNodeHierarchyExposesSectionsAndSafeActions() {
        assertThat(Build.VERSION.SDK_INT).isEqualTo(36)
        ActivityScenario.launch(cls).use { scenario ->
            scenario.onActivity { activity ->
                val ui = views(activity)
                val headings = ui.filterIsInstance<TextView>().filter {
                    it.text.toString() in listOf(
                        "Verification receipt", "Android installation outcome",
                        "Installation permissions for this verified file"
                    )
                }
                assertThat(headings).hasSize(3)
                assertThat(headings.all { ViewCompat.isAccessibilityHeading(it) }).isTrue()
                headings.forEach { heading ->
                    val node = requireNotNull(heading.createAccessibilityNodeInfo())
                    try {
                        assertThat(node).isNotNull()
                        assertThat(node.isHeading).isTrue()
                        assertThat(node.text.toString()).isEqualTo(heading.text.toString())
                    } finally { node.recycle() }
                }
                val spinner = ui.filterIsInstance<Spinner>().single()
                assertThat(spinner.contentDescription.toString()).contains("Import source or provider")
                val action = install(ui)
                val node = requireNotNull(action.createAccessibilityNodeInfo())
                try {
                    assertThat(node).isNotNull()
                    assertThat(node.isEnabled).isFalse()
                    assertThat(node.text.toString()).contains("Request Android installation")
                } finally { node.recycle() }
                val announcements = ui.filterIsInstance<TextView>()
                    .count { it.accessibilityLiveRegion == View.ACCESSIBILITY_LIVE_REGION_POLITE }
                assertThat(announcements).isAtLeast(3)
            }
        }
    }

    @Test fun pendingRejectionAndPresentationFailureNeverAppearAsSuccess() {
        val states = listOf(
            ArtifactSessionReceiptPolicy.State.AWAITING_ANDROID,
            ArtifactSessionReceiptPolicy.State.AWAITING_USER_APPROVAL,
            ArtifactSessionReceiptPolicy.State.APPROVAL_UI_UNAVAILABLE,
            ArtifactSessionReceiptPolicy.State.ANDROID_REJECTED
        )
        for (state in states) {
            val label = ArtifactReviewPresentation.androidResult(state)
            assertThat(label).doesNotContain("SUCCESS")
            if (state == ArtifactSessionReceiptPolicy.State.ANDROID_REJECTED) {
                assertThat(label).contains("REJECTED")
            } else {
                assertThat(label).contains("NOT confirmed")
            }
        }
        assertThat(ArtifactReviewPresentation.androidResult(null))
            .contains("No authenticated Android install outcome")
        assertThat(ArtifactReviewPresentation.androidResult(
            ArtifactSessionReceiptPolicy.State.INSTALLED_BY_ANDROID)).contains("SUCCESS")
        // These are state-string tests only, not forged Android OS callbacks.
    }

    @Test fun verifiedConsentIsTransientBeforeHostForceStop() {
        assertThat(Build.VERSION.SDK_INT).isEqualTo(36)
        // Deliberately leave the Activity open for the subsequent host-side
        // app force-stop, without ever clicking its installation action.
        val scenario = ActivityScenario.launch(cls)
        scenario.onActivity { activity ->
            views(activity).filterIsInstance<Spinner>().single().setSelection(1)
        }
        waitFor(scenario, "Local file not selected or verified")
        scenario.onActivity { activity ->
            val pickerResult = cls.getDeclaredMethod("handlePickedFile", Uri::class.java)
            pickerResult.isAccessible = true
            pickerResult.invoke(activity,
                Uri.parse("content://com.aurora.store.debug.r3c07p02/signed.apk"))
        }
        waitFor(scenario, "SIGNED APK FILES VERIFIED — NOT INSTALLED")
        scenario.onActivity { activity ->
            val ui = views(activity)
            assertThat(install(ui).isEnabled).isFalse()
            val consent = ui.filterIsInstance<CheckBox>().single {
                it.text.toString().contains("approve installation")
            }
            assertThat(consent.isChecked).isFalse()
            consent.isChecked = true
            assertThat(install(ui).isEnabled).isTrue()
            assertThat(ui.filterIsInstance<TextView>().joinToString(" ") {
                it.text.toString()
            }).contains("Publisher identity: NOT independently authenticated")
        }
        reportPid("r3c07_p02b_seed_pid")
    }

    @Test fun newProcessNeverRestoresVerifiedConsentOrSelectedBytes() {
        assertThat(Build.VERSION.SDK_INT).isEqualTo(36)
        ActivityScenario.launch(cls).use { scenario ->
            scenario.onActivity { activity ->
                val ui = views(activity)
                assertThat(install(ui).isEnabled).isFalse()
                assertThat(ui.filterIsInstance<CheckBox>().all { !it.isChecked }).isTrue()
                val labels = ui.filterIsInstance<TextView>().joinToString(" ") {
                    it.text.toString()
                }
                assertThat(labels).contains("No verified files")
                assertThat(ui.filterIsInstance<Button>().single {
                    it.text.toString() == "Show technical verification details"
                }.visibility).isEqualTo(View.GONE)
            }
            reportPid("r3c07_p02b_reopen_pid")
        }
    }
}
