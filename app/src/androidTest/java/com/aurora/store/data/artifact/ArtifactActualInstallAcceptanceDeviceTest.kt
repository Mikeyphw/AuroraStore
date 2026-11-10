/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.artifact

import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.SystemClock
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.security.MessageDigest
import java.util.Locale

/** Manually dispatched, destructive-ONLY-to-its-own-synthetic-fixture API36 gate.
 * The host must explicitly click/reject Android's system installer confirmation.
 * No root / privileged install / Play receipt. NEVER run in targeted PR CI.
 */
@RunWith(AndroidJUnit4::class)
class ArtifactActualInstallAcceptanceDeviceTest {
    @Test fun androidInstallerActuallyAcceptsOrRejectsFixture() {
        val inst = InstrumentationRegistry.getInstrumentation()
        val context = inst.targetContext
        assertThat(Build.VERSION.SDK_INT).isEqualTo(36)
        val expected = requireNotNull(
            InstrumentationRegistry.getArguments().getString("r3c06_expected")
        ) { "Required r3c06_expected argument must be accept or deny" }
        assertThat(expected).isAnyOf("accept", "deny")
        val fixture = File(context.cacheDir, "r3c06-fixture.apk")
        assertThat(fixture.isFile).isTrue()
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
