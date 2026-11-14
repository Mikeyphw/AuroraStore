/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import android.view.View
import android.view.ViewGroup
import android.widget.CheckBox
import android.widget.Spinner
import android.widget.TextView
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith

/** Read-only API36 UI tests: no browser, downloading, Play session or APK install. */
@RunWith(AndroidJUnit4::class)
class ArtifactProviderDiscoveryDeviceTest {
    private fun allViews(root: View): List<View> = buildList {
        add(root)
        if (root is ViewGroup) for (i in 0 until root.childCount) {
            addAll(allViews(root.getChildAt(i)))
        }
    }

    @Test fun providerChooserIncludesSeparatePlayAndAllManualSources() {
        ActivityScenario.launch(ArtifactImportActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val spinner = allViews(activity.findViewById(android.R.id.content))
                    .filterIsInstance<Spinner>().single()
                assertThat(spinner.adapter.count).isEqualTo(7)
                assertThat(spinner.adapter.getItem(0).toString()).contains("Google Play")
                assertThat(spinner.adapter.getItem(1).toString()).contains("Local APK")
                assertThat(spinner.adapter.getItem(6).toString()).contains("APKPure")
            }
        }
    }

    @Test fun alternativeVisitsAreNotPreapproved() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        context.getSharedPreferences("artifact_source_preferences", 0).edit().putBoolean("apkpure_opt_in", false).commit()
        ActivityScenario.launch(ArtifactImportActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val checks = allViews(activity.findViewById(android.R.id.content))
                    .filterIsInstance<CheckBox>()
                val mirror = checks.single { it.text.toString().contains("explicitly choose this alternative") }
                val apkpure = checks.single { it.text.toString().contains("Enable APKPure") }
                assertThat(mirror.isChecked).isFalse()
                assertThat(apkpure.isChecked).isFalse()
            }
        }
    }

    @Test fun discoveryScreenRefusesToClaimPublisherOrPlayVerification() {
        ActivityScenario.launch(ArtifactImportActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val text = allViews(activity.findViewById(android.R.id.content))
                    .filterIsInstance<TextView>().joinToString(" ") { it.text.toString() }
                assertThat(text).contains("automatic Play fallback")
                assertThat(text).contains("availability is UNKNOWN")
                assertThat(text).contains("Verification receipt")
            }
        }
    }
}
