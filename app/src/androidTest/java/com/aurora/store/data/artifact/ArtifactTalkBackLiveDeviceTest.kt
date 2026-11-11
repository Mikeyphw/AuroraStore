/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import android.accessibilityservice.AccessibilityServiceInfo
import android.app.UiAutomation
import android.content.Context
import android.os.Build
import android.os.SystemClock
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityManager
import android.widget.Button
import android.widget.TextView
import androidx.core.view.ViewCompat
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith

/** P03 opt-in API36 ONLY. A real TalkBack package and active service are required.
 * No installation, browser navigation, mock service, or forged Android result.
 * Host script must restore its exact secure accessibility settings afterwards.
 */
@RunWith(AndroidJUnit4::class)
class ArtifactTalkBackLiveDeviceTest {
    private val inst get() = InstrumentationRegistry.getInstrumentation()
    private val expectedPackage = "com.google.android.marvin.talkback"
    private val expectedService = "com.google.android.accessibility.talkback.TalkBackService"

    private fun requireLiveTalkBack() {
        assertThat(Build.VERSION.SDK_INT).isEqualTo(36)
        val manager = inst.targetContext.getSystemService(Context.ACCESSIBILITY_SERVICE)
            as AccessibilityManager
        assertThat(manager.isEnabled).isTrue()
        assertThat(manager.isTouchExplorationEnabled).isTrue()
        val active = manager.getEnabledAccessibilityServiceList(AccessibilityServiceInfo.FEEDBACK_ALL_MASK)
        assertThat(active.any {
            it.resolveInfo.serviceInfo.packageName == expectedPackage &&
                it.resolveInfo.serviceInfo.name == expectedService
        }).isTrue()
    }

    private fun all(root: View): List<View> = buildList {
        add(root)
        if (root is ViewGroup) {
            for (i in 0 until root.childCount) addAll(all(root.getChildAt(i)))
        }
    }

    @Test fun talkBackServiceIsActuallyRunningDuringReview() {
        requireLiveTalkBack()
        ActivityScenario.launch(ArtifactImportActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val ui = all(activity.findViewById(android.R.id.content))
                val headings = ui.filterIsInstance<TextView>().filter {
                    it.text.toString() in listOf(
                        "Verification receipt", "Android installation outcome",
                        "Installation permissions for this verified file")
                }
                assertThat(headings).hasSize(3)
                assertThat(headings.all { ViewCompat.isAccessibilityHeading(it) }).isTrue()
                val install = ui.filterIsInstance<Button>().single {
                    it.text.toString() == "Request Android installation"
                }
                assertThat(install.isEnabled).isFalse()
            }
        }
    }

    /** Injects real Android touch events while TalkBack's actual service remains
     * enabled. The emitted accessibility-focus events must refer to distinct
     * controls in Aurora's live import screen; no programmatic focus action.
     */
    private fun swipeRight(automation: UiAutomation, width: Int, height: Int) {
        val y = height * 0.48f
        val start = width * 0.22f
        val end = width * 0.78f
        val downTime = SystemClock.uptimeMillis()
        for (step in 0..9) {
            val action = when (step) {
                0 -> MotionEvent.ACTION_DOWN
                9 -> MotionEvent.ACTION_UP
                else -> MotionEvent.ACTION_MOVE
            }
            val x = start + (end - start) * step.toFloat() / 9f
            val event = MotionEvent.obtain(downTime, downTime + step * 18L,
                action, x, y, 0)
            try { assertThat(automation.injectInputEvent(event, true)).isTrue() }
            finally { event.recycle() }
        }
    }

    @Test fun twoRealTalkBackSwipeFocusEventsChangeTargets() {
        requireLiveTalkBack()
        val automation = inst.getUiAutomation(UiAutomation.FLAG_DONT_SUPPRESS_ACCESSIBILITY_SERVICES)
        ActivityScenario.launch(ArtifactImportActivity::class.java).use { scenario ->
            var width = 0
            var height = 0
            scenario.onActivity { activity ->
                val decor = activity.window.decorView
                width = decor.width
                height = decor.height
                assertThat(width).isGreaterThan(100)
                assertThat(height).isGreaterThan(100)
            }
            val focused = mutableListOf<String>()
            repeat(2) {
                val event = automation.executeAndWaitForEvent(
                    { swipeRight(automation, width, height) },
                    { e: AccessibilityEvent ->
                        e.eventType == AccessibilityEvent.TYPE_VIEW_ACCESSIBILITY_FOCUSED &&
                            e.packageName?.toString() == inst.targetContext.packageName
                    }, 12_000L
                )
                try {
                    val source = event.source
                    try {
                        val text = listOfNotNull(source?.text?.toString(),
                            source?.contentDescription?.toString(),
                            source?.viewIdResourceName).joinToString(" ").trim()
                        assertThat(text).isNotEmpty()
                        focused.add(text)
                    } finally { source?.recycle() }
                } finally { event.recycle() }
            }
            assertThat(focused).hasSize(2)
            assertThat(focused[0]).isNotEqualTo(focused[1])
        }
    }
}
