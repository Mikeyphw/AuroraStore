/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.work

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ResumeRangePolicyTest {
    @Test
    fun validPartialResponseWithKnownTotal() {
        assertTrue(ResumeRangePolicy.matches("bytes 4-9/10", 4L))
        assertTrue(ResumeRangePolicy.matches("bytes 0-9/10", 0L))
    }

    @Test
    fun validPartialResponseWithUnknownTotal() {
        assertTrue(ResumeRangePolicy.matches("bytes 5-11/*", 5L))
    }

    @Test
    fun rejectsWrongOffsetAndMalformedRanges() {
        assertFalse(ResumeRangePolicy.matches("bytes 3-9/10", 4L))
        assertFalse(ResumeRangePolicy.matches("broken", 4L))
        assertFalse(ResumeRangePolicy.matches(null, 4L))
    }

    @Test
    fun rejectsInvalidBoundsAndOverflow() {
        assertFalse(ResumeRangePolicy.matches("bytes 4-3/10", 4L))
        assertFalse(ResumeRangePolicy.matches("bytes 4-10/10", 4L))
        assertFalse(ResumeRangePolicy.matches("bytes 4-9/4", 4L))
        assertFalse(ResumeRangePolicy.matches("bytes 999999999999999999999-10/12", 0L))
    }

    @Test
    fun onlyNonemptyPartialRequires416Restart() {
        assertTrue(ResumeRangePolicy.requiresRestart(416, 10L))
        assertFalse(ResumeRangePolicy.requiresRestart(416, 0L))
        assertFalse(ResumeRangePolicy.requiresRestart(200, 10L))
    }
}
