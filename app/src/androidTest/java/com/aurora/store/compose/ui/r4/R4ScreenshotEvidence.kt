/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.compose.ui.r4

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Color
import android.os.SystemClock
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.io.FileOutputStream
import kotlin.math.abs

/** The screenshot must visibly contain screen content, not merely a valid status bar PNG.
 * Screenshots come from the *real* emulator via UiAutomation, never a preview renderer.
 */
internal object R4ScreenshotEvidence {
    fun capture(context: Context, filename: String, waitForIdle: () -> Unit) {
        check(filename.matches(Regex("r4_[a-z0-9_]+\\.png"))) { "R4_SCREENSHOT_INVALID_NAME" }
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        var accepted: Bitmap? = null
        var observed = -1
        // Android 16 occasionally returns a blank compositor frame directly after a Compose draw.
        // Bounded retries are allowed, but a blank final image always fails acceptance.
        for (attempt in 1..8) {
            waitForIdle()
            val image = automation.takeScreenshot()
            if (image != null && image.width >= 320 && image.height >= 480) {
                observed = contentSamples(image)
                if (observed >= 42) {
                    accepted = image
                    break
                }
                image.recycle()
            }
            if (attempt < 8) SystemClock.sleep(300)
        }
        val image = checkNotNull(accepted) {
            "R4_SCREENSHOT_BLANK_OR_NOT_RENDERED $filename contentSamples=$observed"
        }
        val output = File(context.filesDir, filename)
        FileOutputStream(output).use { stream ->
            check(image.compress(Bitmap.CompressFormat.PNG, 100, stream)) {
                "R4_SCREENSHOT_ENCODE_FAILED $filename"
            }
        }
        image.recycle()
        check(output.length() > 2048L) { "R4_SCREENSHOT_EMPTY $filename" }
    }

    /** Deliberately ignore status/navigation bars and compare against the body background. */
    private fun contentSamples(bitmap: Bitmap): Int {
        val width = bitmap.width
        val height = bitmap.height
        val background = bitmap.getPixel(width / 2, height / 2)
        val r = Color.red(background)
        val g = Color.green(background)
        val b = Color.blue(background)
        var changed = 0
        for (y in (height / 20) until (height * 9 / 10) step 8) {
            for (x in (width / 50) until (width * 49 / 50) step 8) {
                val color = bitmap.getPixel(x, y)
                if (abs(Color.red(color) - r) + abs(Color.green(color) - g) +
                    abs(Color.blue(color) - b) >= 52
                ) changed++
            }
        }
        return changed
    }
}
