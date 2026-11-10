/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import com.google.common.truth.Truth.assertThat
import org.junit.Test

class ArtifactPickerPolicyTest {
    @Test
    fun ordinaryFilenameRetained() {
        assertThat(ArtifactPickerPolicy.safeDisplayLabel("downloads/release.apk"))
            .isEqualTo("release.apk")
    }

    @Test
    fun maliciousUriAndTokenLabelsDiscarded() {
        for (s in listOf("https://evil/file.apk", "repo?token=123", "content://foo")) {
            assertThat(ArtifactPickerPolicy.safeDisplayLabel(s)).isNull()
        }
    }

    @Test
    fun controlCharactersNeverBecomeProvenance() {
        for (s in listOf("app\n.apk", "app\u0000.apk", "\u0001apk", "x\r.apk")) {
            assertThat(ArtifactPickerPolicy.safeDisplayLabel(s)).isNull()
        }
    }

    @Test
    fun emptyOrWhitespaceNamesDiscarded() {
        assertThat(ArtifactPickerPolicy.safeDisplayLabel("   ")).isNull()
        assertThat(ArtifactPickerPolicy.safeDisplayLabel("/ ")).isNull()
    }

    @Test
    fun nameIsBoundedWithoutReadingProviderPath() {
        assertThat(ArtifactPickerPolicy.safeDisplayLabel("x".repeat(800))?.length)
            .isEqualTo(150)
    }
}
