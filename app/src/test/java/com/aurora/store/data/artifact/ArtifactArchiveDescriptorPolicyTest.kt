/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.artifact

import com.google.common.truth.Truth.assertThat
import org.junit.Test

class ArtifactArchiveDescriptorPolicyTest {
    private val model = ArtifactArchiveDescriptorPolicy
    private val apkm = ArtifactArchivePolicy.Format.APKM
    private val xapk = ArtifactArchivePolicy.Format.XAPK
    private fun declined(action: () -> Unit) = runCatching(action).isFailure

    @Test fun apkmAllowsOnlyExactKnownOuterMetadata() {
        for (path in listOf("info.json", "icon.png", "APKM_installer.url",
            "META-INF/MANIFEST.MF", "META-INF/APKMIRRO.SF", "META-INF/APKMIRRO.RSA")) {
            assertThat(model.allowsMetadata(apkm, path)).isTrue()
        }
        for (path in listOf("toc.pb", "evil.url", "META-INF/CERT.RSA", "manifest.json",
            "nested/APKM_installer.url")) assertThat(model.allowsMetadata(apkm, path)).isFalse()
    }
    @Test fun completeApkmOuterSignatureIsOnlyStructureNotPublisherProof() {
        model.checkMemberLayout(apkm, listOf("info.json", "META-INF/MANIFEST.MF",
            "META-INF/APKMIRRO.SF", "META-INF/APKMIRRO.RSA"))
    }
    @Test fun partialOuterSignatureRefused() {
        assertThat(declined { model.checkMemberLayout(apkm,
            listOf("META-INF/MANIFEST.MF", "META-INF/APKMIRRO.SF")) }).isTrue()
    }
    @Test fun apksTocRemainsUntrustedOnlyInApks() {
        assertThat(model.allowsMetadata(ArtifactArchivePolicy.Format.APKS,"toc.pb")).isTrue()
        assertThat(model.allowsMetadata(apkm,"toc.pb")).isFalse()
        assertThat(model.allowsMetadata(xapk,"toc.pb")).isFalse()
    }
    @Test fun xapkAllowsOnlyRootManifestAndCommonIcons() {
        assertThat(model.allowsMetadata(xapk,"manifest.json")).isTrue()
        assertThat(model.allowsMetadata(xapk,"META-INF/MANIFEST.MF")).isFalse()
    }
    @Test fun archiveInfoMatchesSignedPackageAndVersion() {
        val c=ArtifactArchiveDescriptorPolicy.Claim(apkm,"com.example.a",42)
        model.checkAgainstSignedApks(c,apkm,"com.example.a",42,listOf("base.apk"),listOf(null))
    }
    @Test fun wrongPackageRefusesEvenWithValidSignedApk() {
        val c=ArtifactArchiveDescriptorPolicy.Claim(apkm,"com.example.a",42)
        assertThat(declined { model.checkAgainstSignedApks(c,apkm,"com.example.b",42,
            listOf("base.apk"),listOf(null)) }).isTrue()
    }
    @Test fun wrongVersionOrRelabeledContainerRefused() {
        val c=ArtifactArchiveDescriptorPolicy.Claim(apkm,"com.example.a",42)
        assertThat(declined { model.checkAgainstSignedApks(c,apkm,"com.example.a",43,
            listOf("base.apk"),listOf(null)) }).isTrue()
        assertThat(declined { model.checkAgainstSignedApks(c,xapk,"com.example.a",42,
            listOf("base.apk"),listOf(null)) }).isTrue()
    }
    @Test fun xapkMustIndexExactlyAllArchivedApks() {
        val c=ArtifactArchiveDescriptorPolicy.Claim(xapk,"com.example.a",42,
            mapOf("base.apk" to null,"config.en.apk" to "config.en"))
        model.checkAgainstSignedApks(c,xapk,"com.example.a",42,
            listOf("base.apk","config.en.apk"),listOf(null,"config.en"))
        assertThat(declined {model.checkAgainstSignedApks(c,xapk,"com.example.a",42,
            listOf("base.apk"),listOf(null))}).isTrue()
    }
    @Test fun xapkWrongSignedSplitIdRefused() {
        val c=ArtifactArchiveDescriptorPolicy.Claim(xapk,"com.example.a",42,
            mapOf("base.apk" to null,"config.en.apk" to "config.en"))
        assertThat(declined {model.checkAgainstSignedApks(c,xapk,"com.example.a",42,
            listOf("base.apk","config.en.apk"),listOf(null,"config.fr"))}).isTrue()
    }
    @Test fun xapkCannotDeclareTwoBases() {
        val c=ArtifactArchiveDescriptorPolicy.Claim(xapk,"com.example.a",42,
            mapOf("base.apk" to null,"copy.apk" to null))
        assertThat(declined {model.checkAgainstSignedApks(c,xapk,"com.example.a",42,
            listOf("base.apk","copy.apk"),listOf(null,"config.en"))}).isTrue()
    }
    @Test fun noArchiveMetadataCanMintPlayOrPublisherTrust() {
        assertThat(ArtifactArchiveDescriptorPolicy.Claim::class.java.declaredFields
            .any { it.name.contains("trust",true) || it.name.contains("play",true) }).isFalse()
    }
}
