/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.artifact

import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
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
        println("R3C06_FIXTURE_PRIVATE_STAGE_PASS sha256=$expected")
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
        println("R3C06_FIXTURE_PRIVATE_CLEANUP_PASS sha256=$expected")
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
        println("R3C06_API36_OS_RESULT=${expected.uppercase(Locale.ROOT)} session=$session")
    }
}
