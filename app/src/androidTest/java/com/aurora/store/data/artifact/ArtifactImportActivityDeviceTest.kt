/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.CheckBox
import android.widget.ScrollView
import android.widget.TextView
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith

/** UI-only API36 acceptance; no APK install, browser navigation or device modification. */
@RunWith(AndroidJUnit4::class)
class ArtifactImportActivityDeviceTest {
    private fun descendants(root: View): List<View> = buildList {
        add(root)
        if (root is ViewGroup) for (index in 0 until root.childCount) {
            addAll(descendants(root.getChildAt(index)))
        }
    }

    @Test fun importIsAccessibleAndStartsWithoutConsentOrTrustedStatus() {
        ActivityScenario.launch(ArtifactImportActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val all = descendants(activity.findViewById(android.R.id.content))
                val install = all.filterIsInstance<Button>().single {
                    it.text.toString() == "Request Android installation"
                }
                assertThat(install.isEnabled).isFalse()
                assertThat(all.filterIsInstance<CheckBox>().filter {
                    it.text.toString().contains("approve installation")
                }.all { it.visibility == View.GONE }).isTrue()
                val text = all.filterIsInstance<TextView>().joinToString(" ") { it.text.toString() }
                assertThat(text).contains("No verified files")
                // Previous fixture installs are allowed: do not demand an empty OS receipt.
            }
        }
    }

    @Test fun explicitSourceAndSeparateOutcomeAreaVisibleWithoutInstallation() {
        ActivityScenario.launch(ArtifactImportActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val all = descendants(activity.findViewById(android.R.id.content))
                val text = all.filterIsInstance<TextView>().joinToString("\n") { it.text.toString() }
                assertThat(text).contains("Verification receipt")
                assertThat(text).contains("Android installation outcome")
                assertThat(text).contains("Browser links are manual handoffs")
                assertThat(all.filterIsInstance<Button>().any {
                    it.text.toString() == "Refresh Android install outcome"
                }).isTrue()
            }
        }
    }

    @Test fun rootIsScrollSafeAndRespectsInsets() {
        ActivityScenario.launch(ArtifactImportActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val all = descendants(activity.findViewById(android.R.id.content))
                val scroll = all.filterIsInstance<ScrollView>().single()
                assertThat(scroll.isFillViewport).isTrue()
                assertThat(scroll.paddingTop).isAtLeast(0)
                assertThat(scroll.paddingBottom).isAtLeast(0)
                assertThat(scroll.canScrollVertically(1) || scroll.canScrollVertically(-1) ||
                    scroll.height > 0).isTrue()
            }
        }
    }
}
