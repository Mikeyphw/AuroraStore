/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.artifact

import android.net.Uri
import android.os.Build
import android.os.SystemClock
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.CheckBox
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.google.common.truth.Truth.assertThat
import android.content.Intent
import android.content.pm.PackageManager
import java.io.ByteArrayInputStream
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.atomic.AtomicBoolean
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.junit.Test
import org.junit.runner.RunWith

/** R3C08 P02-P04: read-only Android adversarial checks; no install, network or Play writes.
 * Real process death and OS install rollback are NOT qualified by this suite.
 */
@RunWith(AndroidJUnit4::class)
class ArtifactR3C08AdversarialDeviceTest {
    private val target get() = InstrumentationRegistry.getInstrumentation().targetContext
    private fun api36() { assertThat(Build.VERSION.SDK_INT).isEqualTo(36) }
    private fun descendants(v: View): List<View> = buildList {
        add(v)
        if (v is ViewGroup) for (i in 0 until v.childCount) addAll(descendants(v.getChildAt(i)))
    }
    private fun stages(): Set<String> =
        File(target.cacheDir, "artifact-imports").listFiles().orEmpty()
            .filter { it.isDirectory }.map { it.name }.toSet()
    private fun review(signature: Boolean, match: Boolean?, installed: Long?,
        approved: Boolean, unknown: Boolean, downgrade: Boolean, publisher: Boolean = false) =
        ArtifactImportDecision.Review("org.example.boundary", 19L, signature, match,
            installed, publisher, approved, unknown, downgrade)

    @Test fun p02_cancelledLeaseRejectsNewStreamAndClosesOwnedInput() {
        api36()
        val closed = AtomicBoolean(false)
        val input = object : ByteArrayInputStream(byteArrayOf(1, 2, 3)) {
            override fun close() { closed.set(true); super.close() }
        }
        val lease = ArtifactCopyCancellation()
        lease.attach(input)
        lease.cancel()
        assertThat(closed.get()).isTrue()
        assertThat(lease.isCancelled()).isTrue()
        assertThat(runCatching { lease.attach(ByteArrayInputStream(byteArrayOf(9))) }.isFailure).isTrue()
        lease.detach(input)
        lease.cancel()
        assertThat(lease.isCancelled()).isTrue()
    }

    @Test fun p02_preCancelledPrivateStagingCleansNewDirectory() {
        api36()
        val before = stages()
        val ticket = ArtifactCopyCancellation()
        ticket.cancel()
        val signed = Uri.parse("content://com.aurora.store.debug.r3c07p02/signed.apk")
        val rejected = runCatching {
            ArtifactPrivateStager.stage(target, signed, "signed.apk", ticket) { ticket.isCancelled() }
        }
        assertThat(rejected.isFailure).isTrue()
        assertThat(stages()).containsExactlyElementsIn(before)
        // In-flight cancellation during a genuine private copy: this is not
        // merely a pre-cancelled token or a policy-layer simulation.
        val large = File(target.cacheDir, "r3c08-inflight-cancel.apk")
        large.writeBytes(ByteArray(192 * 1024) { (it % 251).toByte() })
        try {
            var checks = 0
            val midflight = ArtifactCopyCancellation()
            val rejectedDuringCopy = runCatching {
                ArtifactPrivateStager.stage(target, Uri.fromFile(large), large.name, midflight) {
                    ++checks
                    if (checks >= 5) midflight.cancel() // close the ACTUAL attached input
                    midflight.isCancelled()
                }
            }
            assertThat(rejectedDuringCopy.isFailure).isTrue()
            assertThat(checks).isAtLeast(5)
            assertThat(midflight.isCancelled()).isTrue()
            assertThat(stages()).containsExactlyElementsIn(before)
        } finally { large.delete() }
    }

    @Test fun p02_providerOpenFailureCleansPrivateStageAndDisablesInstall() {
        api36()
        val before = stages()
        // Android provider denies unknown document; this is a controlled failure,
        // not proof of an actual killed provider process.
        val missing = Uri.parse("content://com.aurora.store.debug.r3c07p02/missing.apk")
        assertThat(runCatching {
            ArtifactPrivateStager.stage(target, missing, "missing.apk") { false }
        }.isFailure).isTrue()
        assertThat(stages()).containsExactlyElementsIn(before)
        ActivityScenario.launch(ArtifactImportActivity::class.java).use { scenario ->
            scenario.onActivity { a ->
                val widgets = descendants(a.findViewById(android.R.id.content))
                assertThat(widgets.filterIsInstance<Button>()
                    .single { it.text.toString() == "Request Android installation" }.isEnabled).isFalse()
                assertThat(widgets.filterIsInstance<CheckBox>().all { !it.isChecked }).isTrue()
                // Deliberately queue a genuine provider read and revoke it on
                // the UI thread before an earlier worker can publish a receipt.
                val method = ArtifactImportActivity::class.java
                    .getDeclaredMethod("handlePickedFile", Uri::class.java)
                method.isAccessible = true
                method.invoke(a, Uri.parse(
                    "content://com.aurora.store.debug.r3c07p02/signed.apk"))
                widgets.filterIsInstance<Button>().single {
                    it.text.toString() == "Cancel current import"
                }.performClick()
            }
            SystemClock.sleep(700)
            scenario.onActivity { activity ->
                val active = ArtifactImportActivity::class.java.getDeclaredField("active")
                active.isAccessible = true
                assertThat(active.get(activity)).isNull()
                val now = descendants(activity.findViewById(android.R.id.content))
                assertThat(now.filterIsInstance<Button>().single {
                    it.text.toString() == "Request Android installation"
                }.isEnabled).isFalse()
                assertThat(now.filterIsInstance<CheckBox>().all { !it.isChecked }).isTrue()
            }
        }
        // No stale worker may publish an installable receipt after cancellation.
        var clean = false
        for (attempt in 0 until 20) {
            if (stages()==before) { clean = true; break }
            SystemClock.sleep(100)
        }
        assertThat(clean).isTrue()
        assertThat(stages()).containsExactlyElementsIn(before)
    }

    private fun withLocalProvider(scenario: ActivityScenario<ArtifactImportActivity>) {
        scenario.onActivity { activity ->
            descendants(activity.findViewById(android.R.id.content))
                .filterIsInstance<android.widget.Spinner>().single().setSelection(1)
        }
        awaitLabel(scenario, "Local file not selected or verified")
    }

    private fun awaitLabel(scenario: ActivityScenario<ArtifactImportActivity>, message: String) {
        var recent = ""
        for (tryNumber in 0 until 160) {
            scenario.onActivity { activity ->
                recent = descendants(activity.findViewById(android.R.id.content))
                    .filterIsInstance<android.widget.TextView>()
                    .joinToString("\n") { it.text.toString() }
            }
            if (recent.contains(message)) return
            SystemClock.sleep(250)
        }
        throw AssertionError("R3C08 P02 UI timeout: $message; ${recent.take(320)}")
    }

    private fun selectUri(activity: ArtifactImportActivity, uri: Uri) {
        val method = ArtifactImportActivity::class.java.getDeclaredMethod(
            "handlePickedFile", Uri::class.java)
        method.isAccessible = true
        method.invoke(activity, uri)
    }

    private fun noInstallConsent(activity: ArtifactImportActivity) {
        val views = descendants(activity.findViewById(android.R.id.content))
        assertThat(views.filterIsInstance<Button>()
            .single { it.text.toString() == "Request Android installation" }.isEnabled).isFalse()
        assertThat(views.filterIsInstance<CheckBox>().all { !it.isChecked }).isTrue()
    }

    @Test fun p02_remoteProviderDeathRefusesImportAndRestartsInNewProcess() {
        api36()
        val control = Uri.parse("content://com.aurora.store.r3c08.control")
        val crash = Uri.parse("content://com.aurora.store.r3c08.document/crash.apk")
        val signed = Uri.parse("content://com.aurora.store.r3c08.document/signed.apk")
        val before = stages()
        fun request(method: String) {
            val result = target.contentResolver.call(control, method, null, null)
            assertThat(result?.getString("r3c08_result")).isEqualTo(method)
        }
        var signedGranted = false
        var crashGranted = false
        try {
            request("grant")
            signedGranted = true
            request("grant_crash")
            crashGranted = true
            assertThat(target.checkUriPermission(crash, android.os.Process.myPid(),
                android.os.Process.myUid(), Intent.FLAG_GRANT_READ_URI_PERMISSION))
                .isEqualTo(PackageManager.PERMISSION_GRANTED)
            ActivityScenario.launch(ArtifactImportActivity::class.java).use { scenario ->
                withLocalProvider(scenario)
                scenario.onActivity { selectUri(it, crash) }
                awaitLabel(scenario, "Import refused")
                scenario.onActivity { activity ->
                    noInstallConsent(activity)
                    val field = ArtifactImportActivity::class.java.getDeclaredField("active")
                    field.isAccessible = true
                    assertThat(field.get(activity)).isNull()
                }
            }
            // A fresh open must come from a newly started OS provider process;
            // the host also checks distinct START/KILL/START process IDs.
            var recovered = false
            for (attempt in 0 until 30) {
                val byte = runCatching {
                    target.contentResolver.openInputStream(signed)?.use { it.read() }
                }.getOrNull()
                if (byte != null && byte >= 0) { recovered = true; break }
                SystemClock.sleep(150)
            }
            assertThat(recovered).isTrue()
        } finally {
            // If the second grant fails, still revoke the first. Never leave
            // test-only permission behind after a partial fixture setup.
            try {
                if (crashGranted) request("revoke_crash")
            } finally {
                if (signedGranted) request("revoke")
            }
        }
        var clean = false
        for (attempt in 0 until 40) {
            if (stages() == before) { clean = true; break }
            SystemClock.sleep(100)
        }
        assertThat(clean).isTrue()
        assertThat(stages()).containsExactlyElementsIn(before)
    }

    @Test fun p02_failedProviderRetryResetsAllApprovalsAndCleansCache() {
        api36()
        val before = stages()
        ActivityScenario.launch(ArtifactImportActivity::class.java).use { scenario ->
            withLocalProvider(scenario)
            scenario.onActivity { activity ->
                selectUri(activity, Uri.parse(
                    "content://com.aurora.store.debug.r3c07p02/missing.apk"))
            }
            awaitLabel(scenario, "Import refused")
            scenario.onActivity { noInstallConsent(it) }
            scenario.onActivity { activity ->
                selectUri(activity, Uri.parse(
                    "content://com.aurora.store.debug.r3c07p02/signed.apk"))
            }
            awaitLabel(scenario, "SIGNED APK FILES VERIFIED — NOT INSTALLED")
            scenario.onActivity { activity ->
                noInstallConsent(activity)
                descendants(activity.findViewById(android.R.id.content))
                    .filterIsInstance<Button>().single {
                        it.text.toString() == "Cancel current import"
                    }.performClick()
                noInstallConsent(activity)
                val field = ArtifactImportActivity::class.java.getDeclaredField("active")
                field.isAccessible = true
                assertThat(field.get(activity)).isNull()
            }
        }
        var clean = false
        for (attempt in 0 until 40) {
            if (stages() == before) { clean = true; break }
            SystemClock.sleep(100)
        }
        assertThat(clean).isTrue()
        assertThat(stages()).containsExactlyElementsIn(before)
    }

    @Test fun p03_traversalZipRejectedBeforeExtraction() {
        api36()
        val source = File(target.cacheDir, "r3c08-zip-slip.apks")
        try {
            ZipOutputStream(FileOutputStream(source)).use { out ->
                out.putNextEntry(ZipEntry("../escape.apk"))
                out.write(byteArrayOf(0x11, 0x22))
                out.closeEntry()
            }
            assertThat(runCatching { ArtifactZipPreflight.inspect(source) }.isFailure).isTrue()
            assertThat(ArtifactArchivePolicy.classify("../escape.apk", false)).isNull()
            assertThat(ArtifactArchivePolicy.classify("/escape.apk", false)).isNull()
        } finally { source.delete() }
    }

    @Test fun p03_archiveMetadataCannotOverrideSignedIdentity() {
        api36()
        val format = ArtifactArchivePolicy.Format.XAPK
        val claim = ArtifactArchiveDescriptorPolicy.Claim(format, "org.example.other", 12L)
        assertThat(runCatching {
            ArtifactArchiveDescriptorPolicy.checkAgainstSignedApks(
                claim, format, "org.example.actual", 12L, listOf("base.apk"), listOf(null))
        }.isFailure).isTrue()
        assertThat(runCatching {
            ArtifactArchiveDescriptorPolicy.checkMemberLayout(ArtifactArchivePolicy.Format.APKM,
                listOf("META-INF/APKMIRRO.RSA"))
        }.isFailure).isTrue()
        // Exercise production verification on actual unsigned bytes, not just
        // an unsigned metadata claim; never create a PackageInstaller session.
        val unsigned = File(target.cacheDir, "r3c08-unsigned.apk")
        unsigned.writeBytes(ByteArray(128) { 0x2a.toByte() })
        var staged: ArtifactPrivateStager.Staged? = null
        try {
            staged = ArtifactPrivateStager.stage(target, Uri.fromFile(unsigned),
                unsigned.name) { false }
            val provenance = ArtifactProvenance(ArtifactSource.LOCAL_DOCUMENT, "unsigned.apk")
            assertThat(runCatching {
                ArtifactApkVerifier.verify(target, requireNotNull(staged), provenance) { false }
            }.isFailure).isTrue()
        } finally { staged?.discard(); unsigned.delete() }
    }

    @Test fun p03_conflictingSignedSplitTargetsNeverAutoSelect() {
        api36()
        assertThat(runCatching {
            ArtifactSplitCompatibilityPolicy.check(ArtifactArchivePolicy.Format.APKS,
                listOf(null, "config.arm64_v8a", "config.x86_64"), listOf("arm64-v8a"))
        }.isFailure).isTrue()
        assertThat(runCatching {
            ArtifactSplitCompatibilityPolicy.check(ArtifactArchivePolicy.Format.APKS,
                listOf(null, "config.arm64_v8a", "config.arm64_v8a"), listOf("arm64-v8a"))
        }.isFailure).isTrue()
    }

    /** P03: corrupt a real STORED ZIP local CRC while the central CRC remains valid.
     * The pre-index audit, and the complete private staging path, must reject it.
     */
    @Test fun p03_localHeaderCrcTamperingRefusedBeforeStaging() {
        api36()
        val before = stages()
        val source = File(target.cacheDir, "r3c08-local-crc-${System.nanoTime()}.apks")
        try {
            val payload = ByteArray(257) { (it % 251).toByte() }
            val crc = java.util.zip.CRC32().apply { update(payload) }.value
            ZipOutputStream(FileOutputStream(source)).use { zip ->
                val entry = ZipEntry("base.apk").apply {
                    method = ZipEntry.STORED
                    size = payload.size.toLong()
                    compressedSize = payload.size.toLong()
                    this.crc = crc
                }
                zip.putNextEntry(entry)
                zip.write(payload)
                zip.closeEntry()
            }
            // A STORED member has explicit CRC at offset 14 of the local header.
            val corrupt = source.readBytes()
            assertThat(corrupt.size).isGreaterThan(64)
            assertThat(corrupt[0].toInt() and 255).isEqualTo(0x50)
            assertThat(corrupt[1].toInt() and 255).isEqualTo(0x4b)
            assertThat(corrupt[6].toInt() and 0x08).isEqualTo(0) // no descriptor
            corrupt[14] = (corrupt[14].toInt() xor 0x01).toByte()
            source.writeBytes(corrupt)
            assertThat(runCatching { ArtifactZipPreflight.inspect(source) }.isFailure).isTrue()
            assertThat(runCatching {
                ArtifactPrivateStager.stage(target, Uri.fromFile(source), source.name) { false }
            }.isFailure).isTrue()
            assertThat(stages()).containsExactlyElementsIn(before)
        } finally { source.delete() }
    }

    /** P03: an EOCD central-directory extent forgery cannot reach ZipFile indexing. */
    @Test fun p03_centralDirectoryExtentTamperingRefusedBeforeStaging() {
        api36()
        val before = stages()
        val source = File(target.cacheDir, "r3c08-central-extent-${System.nanoTime()}.apks")
        try {
            ZipOutputStream(FileOutputStream(source)).use { zip ->
                zip.putNextEntry(ZipEntry("base.apk"))
                zip.write(byteArrayOf(2, 4, 6, 8, 10))
                zip.closeEntry()
            }
            val corrupt = source.readBytes()
            val eocd = corrupt.size - 22
            assertThat(corrupt[eocd].toInt() and 255).isEqualTo(0x50)
            assertThat(corrupt[eocd + 1].toInt() and 255).isEqualTo(0x4b)
            corrupt[eocd + 12] = (corrupt[eocd + 12].toInt() xor 0x01).toByte()
            source.writeBytes(corrupt)
            assertThat(runCatching { ArtifactZipPreflight.inspect(source) }.isFailure).isTrue()
            assertThat(runCatching {
                ArtifactPrivateStager.stage(target, Uri.fromFile(source), source.name) { false }
            }.isFailure).isTrue()
            assertThat(stages()).containsExactlyElementsIn(before)
        } finally { source.delete() }
    }

    /** P03: a signed feature manifest's requirement is a veto, not split selection. */
    @Test fun p03_featureDependencyCyclesAndMissingSplitsRefused() {
        api36()
        // Valid dependency first: prove the policy is not an always-reject stub.
        ArtifactFeatureDependencyPolicy.check(
            listOf(null, "featureA", "featureB"), listOf(null, null, "featureA"))
        for (requirements in listOf(
            listOf(null, "featureB", "featureA"), // dependency cycle
            listOf(null, "absentFeature", null), // unavailable feature
            listOf(null, "featureA", null) // self dependency
        )) {
            assertThat(runCatching {
                ArtifactFeatureDependencyPolicy.check(
                    listOf(null, "featureA", "featureB"), requirements)
            }.isFailure).isTrue()
        }
        assertThat(runCatching {
            ArtifactFeatureDependencyPolicy.check(
                listOf(null, "config.arm64_v8a"), listOf(null, "featureA"))
        }.isFailure).isTrue()
    }

    /** P03: signer lineage history and archive-parser labels cannot authenticate a candidate. */
    @Test fun p03_platformIdentityAndSignerHistoryCannotGrantCompatibility() {
        api36()
        val status = ArtifactApkIdentityPolicy.installedSignerStatus(
            setOf("old"), setOf("current"), setOf("old", "current"))
        assertThat(status).isEqualTo(
            ArtifactApkIdentityPolicy.InstalledSignerStatus.HISTORY_ONLY_UNVERIFIED)
        assertThat(ArtifactApkIdentityPolicy.installedSignerStatus(
            setOf("current"), setOf("current"), setOf("old", "current")))
            .isEqualTo(ArtifactApkIdentityPolicy.InstalledSignerStatus.ACTIVE_MATCH)
        assertThat(runCatching {
            ArtifactApkIdentityPolicy.requirePlatformAgreement(
                "org.example.safe", 42L, true, "org.example.other", 42L)
        }.isFailure).isTrue()
        assertThat(runCatching {
            ArtifactApkIdentityPolicy.requirePlatformAgreement(
                "org.example.safe", 42L, true, null, null)
        }.isFailure).isTrue()
    }

    /** P03: ABI and orphaned configuration qualifiers cannot trigger invented targeting. */
    @Test fun p03_unsupportedAbiAndOrphanConfigTargetsRefused() {
        api36()
        val format = ArtifactArchivePolicy.Format.APKS
        assertThat(runCatching {
            ArtifactSplitCompatibilityPolicy.check(format,
                listOf(null, "config.x86_64"), listOf("arm64-v8a"))
        }.isFailure).isTrue()
        assertThat(runCatching {
            ArtifactSplitCompatibilityPolicy.check(format,
                listOf(null, "missingFeature.config.xhdpi"), listOf("arm64-v8a"))
        }.isFailure).isTrue()
        val safe = ArtifactSplitCompatibilityPolicy.check(format,
            listOf(null, "config.arm64_v8a"), listOf("arm64-v8a"))
        assertThat(safe.installabilityConfirmed).isFalse() // Android still decides
    }

    /** P04: a forged publisher tier may never become Play or verified-publisher evidence.
     * This synthetic in-memory VerifiedImport is a policy fixture, NOT a signed APK.
     */
    @Test fun p04_forgedPublisherEvidenceCannotMintPlayProof() {
        api36()
        val part = ArtifactPrivateStager.CopiedApk(
            File(target.cacheDir, "r3c08-never-created-policy-only.apk"), "a".repeat(64), 101L)
        val stage = ArtifactPrivateStager.Staged(
            File(target.cacheDir, "r3c08-never-created-policy-only"),
            ArtifactArchivePolicy.Format.APK, listOf(part), "b".repeat(64), 101L)
        val attempt = ArtifactAttempt("org.example.boundary", 19L, 919L,
            ArtifactProvenance(ArtifactSource.GITHUB_RELEASE, "github.com"))
        fun candidate(tier: ArtifactTrustTier) = ArtifactApkVerifier.VerifiedImport(
            stage, attempt, setOf("c".repeat(64)), tier,
            null, null, listOf(null), 101L, listOf(null))
        val validClaim = ArtifactIndependentEvidence.fromVerifiedImport(
            candidate(ArtifactTrustTier.APK_SIGNER_VALID_PUBLISHER_UNANCHORED))
        assertThat(validClaim.isPlayEvidence).isFalse()
        assertThat(validClaim.hasPublisherAttestation).isFalse()
        assertThat(validClaim.assurance).isEqualTo(
            ArtifactOriginAssurance.SIGNED_APK_PUBLISHER_UNANCHORED)
        assertThat(runCatching { ArtifactIndependentEvidence.fromVerifiedImport(
            candidate(ArtifactTrustTier.VERIFIED_PUBLISHER_IDENTITY)) }.isFailure).isTrue()
        assertThat(runCatching { ArtifactIndependentEvidence.fromVerifiedImport(
            candidate(ArtifactTrustTier.UNKNOWN)) }.isFailure).isTrue()
        assertThat(stage.directory.exists()).isFalse() // no real file staged/installed
    }

    /** P04: successful browser navigation still has a strict exact-source, time-bound lease. */
    @Test fun p04_browserAttributionExpiresAndRejectsChangedHostOrSource() {
        api36()
        val url = "https://github.com/example/repo/releases"
        val handoff = requireNotNull(ArtifactSourceHandoff.parse(
            url, ArtifactSource.GITHUB_RELEASE, false))
        val opened = ArtifactHandoffClaimPolicy.afterSuccessfulLaunch(url, handoff, 1000L)
        fun select(input: String, source: ArtifactSource, whenMs: Long) =
            ArtifactHandoffClaimPolicy.selection(
                selected = source, enteredUrl = input, apkPureOptIn = false,
                launched = opened, untrustedFilename = "safe.apk", nowMonotonicMs = whenMs)
        val fresh = select(url, ArtifactSource.GITHUB_RELEASE, 1050L)
        assertThat(fresh.source).isEqualTo(ArtifactSource.GITHUB_RELEASE)
        assertThat(fresh.isVerifiedPlayDelivery).isFalse()
        assertThat(ArtifactOriginBoundary.claimOnly(fresh.source))
            .isEqualTo(ArtifactOriginAssurance.UNVERIFIED_SOURCE_CLAIM)
        assertThat(select("https://github.com/other/repo/releases",
            ArtifactSource.GITHUB_RELEASE, 1050L).source).isEqualTo(ArtifactSource.LOCAL_DOCUMENT)
        assertThat(select(url, ArtifactSource.DEVELOPER_WEBSITE, 1050L).source)
            .isEqualTo(ArtifactSource.LOCAL_DOCUMENT)
        assertThat(select(url, ArtifactSource.GITHUB_RELEASE, 601001L).source)
            .isEqualTo(ArtifactSource.LOCAL_DOCUMENT)
        assertThat(select(url, ArtifactSource.GITHUB_RELEASE, 999L).source)
            .isEqualTo(ArtifactSource.LOCAL_DOCUMENT)
    }

    /** P04: an APKPure browser claim is not reusable after either approval is lost. */
    @Test fun p04_apkpureRequiresCurrentOptInAndAlternativeConsent() {
        api36()
        val url = "https://apkpure.com/app/example"
        assertThat(ArtifactSourceHandoff.parse(url, ArtifactSource.APKPURE_OPT_IN, false))
            .isNull()
        val handoff = requireNotNull(ArtifactSourceHandoff.parse(
            url, ArtifactSource.APKPURE_OPT_IN, true))
        val opened = ArtifactHandoffClaimPolicy.afterSuccessfulLaunch(url, handoff, 2000L)
        fun selected(optIn: Boolean, alternative: Boolean) =
            ArtifactHandoffClaimPolicy.selection(
                selected = ArtifactSource.APKPURE_OPT_IN, enteredUrl = url,
                apkPureOptIn = optIn, launched = opened,
                untrustedFilename = "selected.apk", alternativeConsent = alternative,
                nowMonotonicMs = 2100L)
        assertThat(selected(false, true).source).isEqualTo(ArtifactSource.LOCAL_DOCUMENT)
        assertThat(selected(true, false).source).isEqualTo(ArtifactSource.LOCAL_DOCUMENT)
        val acceptedClaim = selected(true, true)
        assertThat(acceptedClaim.source).isEqualTo(ArtifactSource.APKPURE_OPT_IN)
        assertThat(acceptedClaim.isVerifiedPlayDelivery).isFalse()
        assertThat(ArtifactOriginBoundary.claimOnly(acceptedClaim.source))
            .isEqualTo(ArtifactOriginAssurance.UNVERIFIED_SOURCE_CLAIM)
    }

    /** P04: separate user approvals cannot turn missing/invalid OS evidence into success. */
    @Test fun p04_unverifiedInstalledIdentityAndIndependentApprovalMatrix() {
        api36()
        val inconsistent = ArtifactImportDecision.blockers(review(true, true, null,
            true, true, true))
        assertThat(inconsistent).contains(ArtifactImportDecision.Blocker.SIGNER_MISMATCH)
        val missing = ArtifactImportDecision.blockers(review(true, null, 20L,
            true, true, true))
        assertThat(missing).contains(ArtifactImportDecision.Blocker.SIGNER_MISMATCH)
        val denied = ArtifactImportDecision.blockers(review(true, null, null,
            false, false, false))
        assertThat(denied).contains(ArtifactImportDecision.Blocker.EXPLICIT_INSTALL_CONSENT_REQUIRED)
        assertThat(denied).contains(ArtifactImportDecision.Blocker.UNANCHORED_PUBLISHER_CONSENT_REQUIRED)
        val noPublisherApproval = ArtifactImportDecision.blockers(review(true, null, null,
            true, false, true))
        assertThat(noPublisherApproval).contains(
            ArtifactImportDecision.Blocker.UNANCHORED_PUBLISHER_CONSENT_REQUIRED)
        val noDowngradeApproval = ArtifactImportDecision.blockers(review(true, true, 20L,
            true, true, false))
        assertThat(noDowngradeApproval).contains(
            ArtifactImportDecision.Blocker.DOWNGRADE_CONSENT_REQUIRED)
        val stillUnsigned = ArtifactImportDecision.blockers(review(false, true, 20L,
            true, true, true))
        assertThat(stillUnsigned).contains(ArtifactImportDecision.Blocker.UNVERIFIED_SIGNATURE)
    }

    /** P04: only Android can report terminal results; replay cannot change/reverse one. */
    @Test fun p04_terminalInstallerReceiptReplayRefusedByStatePolicy() {
        api36()
        val initial = ArtifactSessionReceiptPolicy.State.AWAITING_ANDROID
        val approval = ArtifactSessionReceiptPolicy.State.AWAITING_USER_APPROVAL
        val unavailable = ArtifactSessionReceiptPolicy.State.APPROVAL_UI_UNAVAILABLE
        val installed = ArtifactSessionReceiptPolicy.State.INSTALLED_BY_ANDROID
        val rejected = ArtifactSessionReceiptPolicy.State.ANDROID_REJECTED
        val request = ArtifactSessionReceiptPolicy.Event.USER_APPROVAL_REQUIRED
        val lostUi = ArtifactSessionReceiptPolicy.Event.APPROVAL_PRESENTATION_FAILED
        val osSuccess = ArtifactSessionReceiptPolicy.Event.INSTALLED
        val osReject = ArtifactSessionReceiptPolicy.Event.REJECTED
        assertThat(ArtifactSessionReceiptPolicy.next(initial, request)).isEqualTo(approval)
        assertThat(ArtifactSessionReceiptPolicy.next(initial, lostUi)).isNull()
        assertThat(ArtifactSessionReceiptPolicy.next(approval, request)).isNull()
        assertThat(ArtifactSessionReceiptPolicy.next(approval, lostUi)).isEqualTo(unavailable)
        assertThat(ArtifactSessionReceiptPolicy.next(unavailable, request)).isEqualTo(approval)
        assertThat(ArtifactSessionReceiptPolicy.next(unavailable, osReject)).isEqualTo(rejected)
        for (terminal in listOf(installed, rejected)) {
            for (event in ArtifactSessionReceiptPolicy.Event.entries) {
                assertThat(ArtifactSessionReceiptPolicy.next(terminal, event)).isNull()
            }
        }
        assertThat(ArtifactSessionReceiptPolicy.next(initial, osSuccess)).isEqualTo(installed)
        assertThat(ArtifactSessionReceiptPolicy.next(initial, osReject)).isEqualTo(rejected)
        // These are pure state-transition checks, NOT actual OS install/rollback evidence.
    }

    @Test fun p04_consentCannotOverrideSignerMismatch() {
        api36()
        val bad = ArtifactImportDecision.blockers(review(true, false, 20L,
            true, true, true, publisher = true))
        assertThat(bad).contains(ArtifactImportDecision.Blocker.SIGNER_MISMATCH)
        val unsigned = ArtifactImportDecision.blockers(review(false, null, null,
            true, true, true, publisher = true))
        assertThat(unsigned).contains(ArtifactImportDecision.Blocker.UNVERIFIED_SIGNATURE)
    }

    @Test fun p04_browserClaimsNeverProducePlayOrPublisherProof() {
        api36()
        assertThat(ArtifactOriginBoundary.claimOnly(ArtifactSource.GITHUB_RELEASE))
            .isEqualTo(ArtifactOriginAssurance.UNVERIFIED_SOURCE_CLAIM)
        assertThat(ArtifactOriginBoundary.claimOnly(ArtifactSource.DEVELOPER_WEBSITE))
            .isEqualTo(ArtifactOriginAssurance.UNVERIFIED_SOURCE_CLAIM)
        assertThat(ArtifactOriginBoundary.family(ArtifactSource.APKMIRROR_BROWSER_HANDOFF))
            .isNotEqualTo(ArtifactOriginFamily.GOOGLE_PLAY)
        val stale = ArtifactHandoffClaimPolicy.selection(
            selected = ArtifactSource.GITHUB_RELEASE,
            enteredUrl = "https://github.com/org/repo/releases",
            apkPureOptIn = false, launched = null, untrustedFilename = "signed.apk")
        assertThat(stale.source).isEqualTo(ArtifactSource.LOCAL_DOCUMENT)
    }

    @Test fun p04_downgradeAndUnknownPublisherRequireIndependentConsent() {
        api36()
        val none = ArtifactImportDecision.blockers(review(true, true, 30L,
            false, false, false))
        assertThat(none).contains(ArtifactImportDecision.Blocker.EXPLICIT_INSTALL_CONSENT_REQUIRED)
        assertThat(none).contains(ArtifactImportDecision.Blocker.DOWNGRADE_CONSENT_REQUIRED)
        val installOnly = ArtifactImportDecision.blockers(review(true, true, 30L,
            true, false, false))
        assertThat(installOnly).contains(ArtifactImportDecision.Blocker.DOWNGRADE_CONSENT_REQUIRED)
        val first = ArtifactImportDecision.blockers(review(true, null, null,
            true, false, false))
        assertThat(first).contains(ArtifactImportDecision.Blocker.UNANCHORED_PUBLISHER_CONSENT_REQUIRED)
    }
}
