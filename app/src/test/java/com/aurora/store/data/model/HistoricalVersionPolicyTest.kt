/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.model

import com.google.common.truth.Truth.assertThat
import org.junit.Test

class HistoricalVersionPolicyTest {
    @Test
    fun rejectsInvalidAndOverflowedVersionCodes() {
        for (candidate in listOf("", "0", "-1", " 42", "42 ", "4.2", "2e4", "1x")) {
            assertThat(HistoricalVersionPolicy.parseVersionCode(candidate)).isNull()
        }
        assertThat(HistoricalVersionPolicy.parseVersionCode("9223372036854775808")).isNull()
        assertThat(HistoricalVersionPolicy.parseVersionCode("00073")).isEqualTo(73L)
        assertThat(HistoricalVersionPolicy.parseVersionCode(Long.MAX_VALUE.toString()))
            .isEqualTo(Long.MAX_VALUE)
    }

    @Test
    fun versionHistoryIsNumericDeduplicatedAndSorted() {
        val input = listOf(
            "7",
            "20",
            "0007",
            "-8",
            "19",
            "20",
            "0",
            "broken",
            "999999999999999999999"
        )
        assertThat(HistoricalVersionPolicy.knownVersions(input))
            .containsExactly(20L, 19L, 7L).inOrder()
    }

    @Test
    fun historySelectionUsesCanonicalPositiveCodes() {
        assertThat(HistoricalVersionPolicy.canonicalVersionCode("00073")).isEqualTo("73")
        assertThat(HistoricalVersionPolicy.canonicalVersionCode("0")).isNull()
        assertThat(HistoricalVersionPolicy.canonicalVersionCode("9223372036854775808"))
            .isNull()
    }

    @Test
    fun downgradeConsentRejectsChangedSelectionOrInstalledVersion() {
        val policy = HistoricalVersionPolicy
        assertThat(policy.mayConfirmDowngrade(73L, 74L, 74L, "00073")).isTrue()
        assertThat(policy.mayConfirmDowngrade(73L, 74L, 75L, "73")).isFalse()
        assertThat(policy.mayConfirmDowngrade(73L, 74L, 74L, "72")).isFalse()
        assertThat(policy.mayConfirmDowngrade(73L, 73L, 73L, "73")).isFalse()
        assertThat(policy.mayConfirmDowngrade(73L, 0L, 0L, "73")).isFalse()
    }

    @Test
    fun onlyAnOlderVersionOfAnInstalledAppIsADowngrade() {
        assertThat(HistoricalVersionPolicy.isDowngrade(73L, 74L)).isTrue()
        assertThat(HistoricalVersionPolicy.isDowngrade(74L, 74L)).isFalse()
        assertThat(HistoricalVersionPolicy.isDowngrade(75L, 74L)).isFalse()
        assertThat(HistoricalVersionPolicy.isDowngrade(73L, 0L)).isFalse()
        assertThat(HistoricalVersionPolicy.isDowngrade(0L, 74L)).isFalse()
    }
}
