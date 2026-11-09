/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import com.google.common.truth.Truth.assertThat
import org.junit.Test

class ArtifactArchivePolicyTest {
    @Test
    fun formatsAreStrict() {
        for (name in listOf("foo.apk", "foo.apks", "foo.apkm", "foo.xapk")) {
            assertThat(ArtifactArchivePolicy.format(name)).isNotNull()
        }
        for (name in listOf("foo.aab", "foo.zip", "foo.apk.exe", "foo")) {
            assertThat(ArtifactArchivePolicy.format(name)).isNull()
        }
    }

    @Test

    fun archivePathsRejectTraversalAndAbsoluteNames() {
        for (name in listOf("../evil.apk", "root/../evil.apk", "/root.apk", ".//evil.apk",
            "foo\\evil.apk", "foo//evil.apk", "x\n.apk", "./base.apk")) {
            assertThat(ArtifactArchivePolicy.classify(name, false)).isNull()
        }
    }

    @Test

    fun archiveRejectsObbAndExecutables() {
        for (name in listOf("Android/obb/app/main.obb", "malware.sh", "foo.dex", "bar.so")) {
            assertThat(ArtifactArchivePolicy.classify(name, false)).isNull()
        }
    }

    @Test

    fun ordinaryApkAndMetadataFilesCanBeClassified() {
        assertThat(ArtifactArchivePolicy.classify("split/base.apk", false))
            .isEqualTo(ArtifactArchivePolicy.Entry.APK)
        assertThat(ArtifactArchivePolicy.classify("manifest.json", false))
            .isEqualTo(ArtifactArchivePolicy.Entry.METADATA)
    }

    @Test

    fun compressionBombSizesFailClosed() {
        assertThat(ArtifactArchivePolicy.safeSize(200000000, 1000, true)).isFalse()
        assertThat(ArtifactArchivePolicy.safeSize(10, 0, true)).isFalse()
        assertThat(ArtifactArchivePolicy.safeSize(-1, 1, true)).isFalse()
        assertThat(ArtifactArchivePolicy.safeSize(300L * 1024 * 1024, 3000000, true)).isFalse()
        assertThat(ArtifactArchivePolicy.safeSize(1024, 512, true)).isTrue()
    }
}
