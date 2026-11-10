/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.artifact

import com.google.common.truth.Truth.assertThat
import org.junit.Test

class ArtifactFeatureDependencyPolicyTest {
    private fun refused(ids: List<String?>, deps: List<String?>) =
        runCatching { ArtifactFeatureDependencyPolicy.check(ids, deps) }.isFailure

    @Test fun onlyBaseAllowed() {
        ArtifactFeatureDependencyPolicy.check(listOf(null), listOf(null))
    }
    @Test fun featureWithNoExplicitDependencyAllowed() {
        ArtifactFeatureDependencyPolicy.check(listOf(null, "camera"), listOf(null, null))
    }
    @Test fun declaredFeatureDependencyMustBePresent() {
        assertThat(refused(listOf(null, "camera"), listOf(null, "maps"))).isTrue()
    }
    @Test fun validChainOfFeatures() {
        ArtifactFeatureDependencyPolicy.check(listOf(null, "core", "camera"), listOf(null, null, "core"))
    }
    @Test fun cyclesRejected() {
        assertThat(refused(listOf(null,"a","b"), listOf(null,"b","a"))).isTrue()
    }
    @Test fun featureSelfDependenceRejected() {
        assertThat(refused(listOf(null,"a"), listOf(null,"a"))).isTrue()
    }
    @Test fun baseCannotDependOnFeature() {
        assertThat(refused(listOf(null,"a"), listOf("a",null))).isTrue()
    }
    @Test fun configSplitCannotRequireFeature() {
        assertThat(refused(listOf(null,"a","a.config.en"), listOf(null,null,"a"))).isTrue()
    }
    @Test fun dependencyCannotNameConfigSplit() {
        assertThat(refused(listOf(null,"a","a.config.en"), listOf(null,"a.config.en",null))).isTrue()
    }
    @Test fun duplicateBaseRejected() {
        assertThat(refused(listOf(null,null), listOf(null,null))).isTrue()
    }
    @Test fun indexesMustBeExact() {
        assertThat(refused(listOf(null,"a"), listOf(null))).isTrue()
    }
    @Test fun malformedDependencyRejected() {
        assertThat(refused(listOf(null,"a","b"), listOf(null,null,"bad/path"))).isTrue()
    }
}
