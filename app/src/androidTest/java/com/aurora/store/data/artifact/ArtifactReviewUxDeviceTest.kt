/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

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

/** Pure read-only UI acceptance; never picks files, launches browsers or installs APKs. */
@RunWith(AndroidJUnit4::class)
class ArtifactReviewUxDeviceTest {
    private fun all(root: View): List<View> = buildList {
        add(root)
        if (root is ViewGroup) {
            for (i in 0 until root.childCount) addAll(all(root.getChildAt(i)))
        }
    }

    private fun root(activity: ArtifactImportActivity) =
        all(activity.findViewById(android.R.id.content))

    private fun install(views: List<View>): Button = views.filterIsInstance<Button>()
        .single { it.text.toString() == "Request Android installation" }

    @Test fun technicalReceiptCannotBeOpenedBeforeActualVerification() {
        ActivityScenario.launch(ArtifactImportActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val views = root(activity)
                val toggle = views.filterIsInstance<Button>().single {
                    it.text.toString() == "Show technical verification details"
                }
                assertThat(toggle.visibility).isEqualTo(View.GONE)
                assertThat(views.filterIsInstance<TextView>().single {
                    it.text.toString().contains("Technical verification details unavailable")
                }.visibility).isEqualTo(View.GONE)
                assertThat(install(views).isEnabled).isFalse()
            }
        }
    }

    @Test fun rotationNeverRestoresPriorApprovalOrVerifiedReceipt() {
        ActivityScenario.launch(ArtifactImportActivity::class.java).use { scenario ->
            scenario.recreate()
            scenario.onActivity { activity ->
                val views = root(activity)
                assertThat(install(views).isEnabled).isFalse()
                assertThat(views.filterIsInstance<CheckBox>().filter {
                    it.text.toString().contains("approve installation") ||
                        it.text.toString().contains("unverified") ||
                        it.text.toString().contains("older version")
                }.all { !it.isChecked }).isTrue()
                assertThat(views.filterIsInstance<TextView>().joinToString(" ") {
                    it.text.toString()
                }).contains("No verified files")
            }
        }
    }

    @Test fun reviewOutcomeAndConsentSectionsAreAccessibilityHeadings() {
        ActivityScenario.launch(ArtifactImportActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val sections = root(activity).filterIsInstance<TextView>().filter {
                    it.text.toString() in listOf(
                        "Verification receipt", "Android installation outcome",
                        "Installation permissions for this verified file")
                }
                assertThat(sections).hasSize(3)
                assertThat(sections.all { ViewCompat.isAccessibilityHeading(it) }).isTrue()
            }
        }
    }

    @Test fun statusAndAndroidResultAnnounceUpdatesPolitely() {
        ActivityScenario.launch(ArtifactImportActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val status = root(activity).filterIsInstance<TextView>().single {
                    it.text.toString().contains("Select an APK or bundle to verify")
                }
                assertThat(status.accessibilityLiveRegion)
                    .isEqualTo(View.ACCESSIBILITY_LIVE_REGION_POLITE)
                val outcome = root(activity).filterIsInstance<TextView>()
                    .firstOrNull { it.accessibilityLiveRegion == View.ACCESSIBILITY_LIVE_REGION_POLITE && it !== status }
                assertThat(outcome).isNotNull()
            }
        }
    }

    @Test fun providerSwitchNeverEnablesInstallOrHidesScrollableConsentSurface() {
        ActivityScenario.launch(ArtifactImportActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val views = root(activity)
                views.filterIsInstance<Spinner>().single().setSelection(6)
                assertThat(install(root(activity)).isEnabled).isFalse()
                assertThat(root(activity).filterIsInstance<ScrollView>().single().isFillViewport).isTrue()
                assertThat(root(activity).filterIsInstance<Button>().single {
                    it.text.toString() == "Show technical verification details"
                }.visibility).isEqualTo(View.GONE)
            }
        }
    }
}
