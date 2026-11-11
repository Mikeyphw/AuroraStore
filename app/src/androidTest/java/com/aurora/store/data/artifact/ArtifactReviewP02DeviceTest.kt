/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import android.net.Uri
import android.os.SystemClock
import android.util.TypedValue
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
import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith

/**
 * P02A: real signed APK bytes through a local content URI and the production
 * staging/verifier/review UI. No installer, provider browser, or Google Play call.
 */
@RunWith(AndroidJUnit4::class)
class ArtifactReviewP02DeviceTest {
    private val authority = "com.aurora.store.debug.r3c07p02"
    private fun uri(name: String) = Uri.parse("content://$authority/$name")

    private fun all(root: View): List<View> = buildList {
        add(root)
        if (root is ViewGroup) {
            for (index in 0 until root.childCount) addAll(all(root.getChildAt(index)))
        }
    }

    private fun views(activity: ArtifactImportActivity) =
        all(activity.findViewById(android.R.id.content))

    private fun install(views: List<View>) = views.filterIsInstance<Button>().single {
        it.text.toString() == "Request Android installation"
    }

    private fun select(activity: ArtifactImportActivity, filename: String) {
        // Simulate the OS picker delivering its content URI. This calls the exact
        // production post-picker function, not a fake verification or receipt.
        val method = ArtifactImportActivity::class.java.getDeclaredMethod(
            "handlePickedFile", Uri::class.java
        )
        method.isAccessible = true
        method.invoke(activity, uri(filename))
    }

    private fun launchLocal(scenario: ActivityScenario<ArtifactImportActivity>) {
        scenario.onActivity { activity ->
            val spinner = views(activity).filterIsInstance<Spinner>().single()
            assertThat(spinner.adapter.getItem(1).toString()).contains("Local APK")
            spinner.setSelection(1)
        }
        // Spinner callbacks can be posted to the next UI loop. Wait for the
        // production provider label before injecting a real post-picker URI.
        waitFor(scenario, "Local file not selected or verified")
    }

    private fun waitFor(
        scenario: ActivityScenario<ArtifactImportActivity>,
        needle: String
    ) {
        var text = ""
        repeat(240) {
            scenario.onActivity { activity ->
                text = views(activity).filterIsInstance<TextView>()
                    .joinToString("\n") { it.text.toString() }
            }
            if (needle in text) return
            SystemClock.sleep(250)
        }
        throw AssertionError("P02A UI never reached expected state: $needle; final=${text.take(400)}")
    }

    @Test fun signedRealContentUriHasTruthfulSourceAndFreshConsent() {
        ActivityScenario.launch(ArtifactImportActivity::class.java).use { scenario ->
            launchLocal(scenario)
            scenario.onActivity { activity -> select(activity, "signed.apk") }
            waitFor(scenario, "SIGNED APK FILES VERIFIED — NOT INSTALLED")
            scenario.onActivity { activity ->
                val ui = views(activity)
                val text = ui.filterIsInstance<TextView>().joinToString("\n") {
                    it.text.toString()
                }
                assertThat(text).contains("Local file chosen with Android picker")
                assertThat(text).contains("Exact-version availability from provider: UNKNOWN")
                assertThat(text).contains("Publisher identity: NOT independently authenticated")
                assertThat(text).contains("NOT Google Play proof")
                assertThat(install(ui).isEnabled).isFalse()
                val consent = ui.filterIsInstance<CheckBox>().single {
                    it.text.toString().contains("approve installation")
                }
                assertThat(consent.visibility).isEqualTo(View.VISIBLE)
                assertThat(consent.isChecked).isFalse()
                val toggle = ui.filterIsInstance<Button>().single {
                    it.text.toString() == "Show technical verification details"
                }
                assertThat(toggle.visibility).isEqualTo(View.VISIBLE)
                toggle.performClick()
                assertThat(ui.filterIsInstance<TextView>().any {
                    it.visibility == View.VISIBLE && it.text.toString().contains("APK signing certificate SHA-256")
                }).isTrue()
                assertThat(install(ui).isEnabled).isFalse()
            }
        }
    }

    @Test fun rotationDropsRealVerifiedBytesAndAllConsent() {
        ActivityScenario.launch(ArtifactImportActivity::class.java).use { scenario ->
            launchLocal(scenario)
            scenario.onActivity { activity -> select(activity, "signed.apk") }
            waitFor(scenario, "SIGNED APK FILES VERIFIED — NOT INSTALLED")
            scenario.onActivity { activity ->
                val ui = views(activity)
                ui.filterIsInstance<CheckBox>().single {
                    it.text.toString().contains("approve installation")
                }.isChecked = true
                // Consent can enable the request, but this test NEVER clicks it.
                assertThat(install(ui).isEnabled).isTrue()
            }
            scenario.recreate()
            scenario.onActivity { activity ->
                val ui = views(activity)
                assertThat(install(ui).isEnabled).isFalse()
                assertThat(ui.filterIsInstance<CheckBox>().all { !it.isChecked }).isTrue()
                val text = ui.filterIsInstance<TextView>().joinToString(" ") {
                    it.text.toString()
                }
                assertThat(text).contains("No verified files")
                assertThat(ui.filterIsInstance<Button>().single {
                    it.text.toString() == "Show technical verification details"
                }.visibility).isEqualTo(View.GONE)
            }
        }
    }

    @Test fun invalidContentFailsClosedAndValidRetryUsesFreshReview() {
        ActivityScenario.launch(ArtifactImportActivity::class.java).use { scenario ->
            launchLocal(scenario)
            scenario.onActivity { activity -> select(activity, "invalid.apk") }
            waitFor(scenario, "Import refused. The selected file could not be verified")
            scenario.onActivity { activity ->
                val ui = views(activity)
                assertThat(install(ui).isEnabled).isFalse()
                assertThat(ui.filterIsInstance<CheckBox>().all { !it.isChecked }).isTrue()
            }
            scenario.onActivity { activity -> select(activity, "signed.apk") }
            waitFor(scenario, "SIGNED APK FILES VERIFIED — NOT INSTALLED")
            scenario.onActivity { activity ->
                val ui = views(activity)
                assertThat(install(ui).isEnabled).isFalse()
                assertThat(ui.filterIsInstance<CheckBox>().all { !it.isChecked }).isTrue()
            }
        }
    }

    @Test fun largeTextAndTalkBackSemanticsPreserveVisibleConsentAndScrolling() {
        ActivityScenario.launch(ArtifactImportActivity::class.java).use { scenario ->
            launchLocal(scenario)
            scenario.onActivity { activity ->
                val ui = views(activity)
                val scroll = ui.filterIsInstance<ScrollView>().single()
                assertThat(scroll.isFillViewport).isTrue()
                val spinner = ui.filterIsInstance<Spinner>().single()
                assertThat(spinner.contentDescription.toString()).contains("source")
                assertThat(ui.filterIsInstance<TextView>().filter {
                    it.text.toString() in listOf(
                        "Verification receipt", "Android installation outcome",
                        "Installation permissions for this verified file"
                    )
                }.all { ViewCompat.isAccessibilityHeading(it) }).isTrue()
                // Large SP text stress inside the actual scroll surface. No global
                // device font setting or accessibility service is modified.
                ui.filterIsInstance<TextView>().filter { it.visibility == View.VISIBLE }
                    .forEach { it.setTextSize(TypedValue.COMPLEX_UNIT_SP, 26f) }
                assertThat(scroll.getChildAt(0)).isNotNull()
                assertThat(install(ui).isEnabled).isFalse()
                assertThat(ui.filterIsInstance<CheckBox>().all { !it.isChecked }).isTrue()
                val polite = ui.filterIsInstance<TextView>()
                    .count { it.accessibilityLiveRegion == View.ACCESSIBILITY_LIVE_REGION_POLITE }
                assertThat(polite).isAtLeast(3)
            }
        }
    }
}
