/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.artifact

import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.SystemClock
import android.util.Base64
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.io.FileOutputStream
import java.security.MessageDigest
import java.util.Locale

/** Manually dispatched, destructive-ONLY-to-its-own-synthetic-fixture API36 gate.
 * The host must explicitly click/reject Android's system installer confirmation.
 * No root / privileged install / Play receipt. NEVER run in targeted PR CI.
 */
@RunWith(AndroidJUnit4::class)
class ArtifactActualInstallAcceptanceDeviceTest {
    private val maxFixtureBytes = 64 * 1024
    private val fixtureName = "r3c06-fixture.apk"
    private val hexSha256 = Regex("[0-9a-f]{64}")

    /** Explicit, structured Android instrumentation evidence. println() writes to
     * logcat and is NOT an am-instrument status receipt. Report only after the
     * real verification, stage or cleanup operation has succeeded.
     */
    private fun reportStatus(key: String, value: String) {
        require(key in setOf("r3c06_fixture_stage_sha256",
                             "r3c06_fixture_cleanup_sha256", "r3c06_os_result",
                             "r3c06_foreground_activity",
                             "r3c06_unknown_sources_effective")) {
            "Unexpected instrumentation evidence key"
        }
        val status = Bundle()
        status.putString(key, value)
        InstrumentationRegistry.getInstrumentation().sendStatus(0, status)
    }

    private fun fixtureFile(): File {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val base = context.cacheDir.canonicalFile
        val file = File(base, fixtureName)
        require(file.parentFile?.canonicalFile == base && file.canonicalFile.parentFile == base) {
            "Fixture path must remain in Aurora private cache"
        }
        return file
    }

    private fun requiredFixtureDigest(): String {
        val value = requireNotNull(
            InstrumentationRegistry.getArguments().getString("r3c06_fixture_sha256")
        ) { "Missing expected signed fixture SHA-256" }
        require(hexSha256.matches(value)) { "Malformed signed fixture SHA-256" }
        return value
    }

    private fun fileDigest(file: File): String {
        val md = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(8192)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                if (count == 0) error("Fixture stream stalled")
                md.update(buffer, 0, count)
            }
        }
        return md.digest().joinToString("") { "%02x".format(Locale.ROOT, it.toInt() and 0xff) }
    }

    /** Only manually dispatched instrumentation can seed the isolated fixture.
     * The target app UID, not `adb run-as`/shared storage, owns these bytes.
     */
    @Test fun seedSignedFixtureIntoPrivateCache() {
        assertThat(Build.VERSION.SDK_INT).isEqualTo(36)
        // The app's effective Android permission, not adb appops text, is
        // authoritative. Preserve a DENIED status if the host setup was
        // ineffective, but refuse to stage bytes or request an OS session.
        val target = InstrumentationRegistry.getInstrumentation().targetContext
        val canRequest = target.packageManager.canRequestPackageInstalls()
        reportStatus("r3c06_unknown_sources_effective",
            if (canRequest) "ALLOWED" else "DENIED")
        require(canRequest) { "Aurora cannot request package installs on API36" }
        val expected = requiredFixtureDigest()
        val encoded = requireNotNull(
            InstrumentationRegistry.getArguments().getString("r3c06_fixture_base64")
        ) { "Missing signed fixture bytes" }
        require(encoded.length in 4..((maxFixtureBytes + 2) / 3 * 4)) {
            "Synthetic fixture exceeds bounded instrument argument"
        }
        require(Regex("[A-Za-z0-9+/]+={0,2}").matches(encoded)) { "Invalid fixture encoding" }
        val bytes = Base64.decode(encoded, Base64.NO_WRAP)
        require(bytes.isNotEmpty() && bytes.size <= maxFixtureBytes) { "Fixture size invalid" }
        val file = fixtureFile()
        require(!file.exists()) { "Private fixture already exists; cannot overwrite" }
        try {
            FileOutputStream(file).use { output ->
                output.write(bytes)
                output.fd.sync()
            }
            require(file.isFile && file.length() == bytes.size.toLong()) { "Fixture size changed" }
            require(fileDigest(file) == expected) { "Fixture SHA-256 changed in private cache" }
        } catch (failure: Exception) {
            file.delete()
            throw failure
        }
        reportStatus("r3c06_fixture_stage_sha256", expected)
    }

    /** Delete only the exact expected synthetic file, never another app's bytes. */
    @Test fun removeSignedFixtureFromPrivateCache() {
        assertThat(Build.VERSION.SDK_INT).isEqualTo(36)
        val expected = requiredFixtureDigest()
        val file = fixtureFile()
        if (file.exists()) {
            require(file.isFile && file.length() in 1L..maxFixtureBytes.toLong()) {
                "Private fixture is not a bounded regular file"
            }
            require(fileDigest(file) == expected) { "Unexpected private file; refuse deletion" }
            require(file.delete()) { "Private fixture cleanup failed" }
        }
        require(!file.exists()) { "Private fixture remains after cleanup" }
        reportStatus("r3c06_fixture_cleanup_sha256", expected)
    }
    /** Android 14+ restricts background starts from a broadcast receiver.
     * The real import screen must be visible before the OS confirmation is
     * requested. This is a runtime precondition, not fake approval.
     */
    private fun showForegroundImport(inst: android.app.Instrumentation) {
        val context = inst.targetContext
        val activity = inst.startActivitySync(
            Intent(context, ArtifactImportActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        )
        require(activity is ArtifactImportActivity && !activity.isFinishing) {
            "Actual Aurora import activity did not launch"
        }
        inst.waitForIdleSync()
        val deadline = SystemClock.elapsedRealtime() + 10_000L
        while (!activity.hasWindowFocus() && SystemClock.elapsedRealtime() < deadline) {
            SystemClock.sleep(200)
        }
        require(activity.hasWindowFocus()) {
            "Aurora import activity is not visible; refuse background installer launch"
        }
        reportStatus("r3c06_foreground_activity", "VISIBLE")
    }

    @Test fun androidInstallerActuallyAcceptsOrRejectsFixture() {
        val inst = InstrumentationRegistry.getInstrumentation()
        val context = inst.targetContext
        assertThat(Build.VERSION.SDK_INT).isEqualTo(36)
        val expected = requireNotNull(
            InstrumentationRegistry.getArguments().getString("r3c06_expected")
        ) { "Required r3c06_expected argument must be accept or deny" }
        assertThat(expected).isAnyOf("accept", "deny")
        val fixture = fixtureFile()
        assertThat(fixture.isFile).isTrue()
        assertThat(fixture.length()).isAtMost(maxFixtureBytes.toLong())
        assertThat(fileDigest(fixture)).isEqualTo(requiredFixtureDigest())
        val expectedPackage = "com.aurora.r3c06.fixture"
        assertThat(runCatching { context.packageManager.getPackageInfo(expectedPackage, 0) }
            .isFailure).isTrue()
        val staged = ArtifactPrivateStager.stage(context, Uri.fromFile(fixture), fixture.name) { false }
        val verified = try {
            ArtifactApkVerifier.verify(context, staged,
                ArtifactProvenance(ArtifactSource.LOCAL_DOCUMENT)) { false }
        } catch (e: Exception) { staged.discard(); throw e }
        assertThat(verified.attempt.packageName).isEqualTo(expectedPackage)
        assertThat(verified.installedVersion).isNull()
        assertThat(verified.signerMatchesInstalled).isNull()
        assertThat(verified.signerSha256).isNotEmpty()
        val verifiedCerts = verified.signerSha256
        showForegroundImport(inst)
        // User-app consent is explicit. Android system consent still must be
        // separately exercised by a human or a tightly verified host UI driver.
        val session = ArtifactInstallSession.install(
            context, verified, approvedInstall=true,
            approvedUnknownPublisher=true, approvedDowngrade=false
        ) { false }
        assertThat(session).isGreaterThan(0)
        val timeout = SystemClock.elapsedRealtime() + 180_000L
        var state: String
        while (true) {
            state = ArtifactInstallSession.lastResult(context)
            if ("INSTALLED_BY_ANDROID" in state || "ANDROID_REJECTED" in state) break
            if (SystemClock.elapsedRealtime() >= timeout) {
                throw AssertionError("System installation callback never became terminal: $state")
            }
            SystemClock.sleep(450)
        }
        if (expected == "deny") {
            assertThat(state).contains("ANDROID_REJECTED")
            assertThat(runCatching { context.packageManager.getPackageInfo(expectedPackage, 0) }
                .isFailure).isTrue()
        } else {
            assertThat(state).contains("INSTALLED_BY_ANDROID")
            val installed = context.packageManager.getPackageInfo(
                expectedPackage, PackageManager.GET_SIGNING_CERTIFICATES
            )
            assertThat(installed.longVersionCode).isEqualTo(17L)
            val installedCerts = installed.signingInfo?.apkContentsSigners.orEmpty().map {
                MessageDigest.getInstance("SHA-256").digest(it.toByteArray())
                    .joinToString("") { b -> "%02x".format(Locale.ROOT, b.toInt() and 0xff) }
            }.toSet()
            assertThat(installedCerts).isEqualTo(verifiedCerts)
        }
        // Hosted gate owns fixture uninstall/cleanup and must prove it completed.
        reportStatus("r3c06_os_result", expected.uppercase(Locale.ROOT))
    }
}
