/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import com.google.common.truth.Truth.assertThat
import org.junit.Test

class ArtifactPickerPolicyTest {
    @Test fun systemPickerRejectsFileOrUntrustedSchemes() {
        assertThat(ArtifactPickerPolicy.acceptsPickerScheme("content")).isTrue()
        for (scheme in listOf(null, "file", "http", "https", "android.resource", "CONTENT")) {
            assertThat(ArtifactPickerPolicy.acceptsPickerScheme(scheme)).isFalse()
        }
    }

    @Test fun rejectsUntrustedProviderNamesBeforeArchiveClassification() {
        for (name in listOf(null, "", "/tmp/app.apk", "../release.apk",
            "release\\bad.apk", "https://host/a.apk", "app?token=123", "x".repeat(241))) {
            assertThat(ArtifactPickerPolicy.safeDocumentName(name)).isNull()
        }
        assertThat(ArtifactPickerPolicy.safeDocumentName("release.apks")).isEqualTo("release.apks")
    }
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
