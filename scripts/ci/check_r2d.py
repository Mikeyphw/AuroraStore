#!/usr/bin/env python3
"""R2D host/emulator acceptance gate. No claim of physical or live-provider qualification."""
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]

def load(path):
    return (ROOT / path).read_text(encoding="utf-8")

requirements = {
    ".github/workflows/aurora-r2d-install-emulator.yml": (
        "api-level: 36", "r2d_build_fixture.sh", "r2d_emulator_ci.sh",
        "assembleVanillaDebug", "assembleVanillaDebugAndroidTest", "timeout-minutes: 90",
        "R2D_INSTALL_LIFECYCLE_RECEIPT.json", "ReactiveCircus/android-emulator-runner@"
    ),
    "scripts/ci/r2d_build_fixture.sh": (
        "aapt2", "apksigner", "keytool", "r2d-fixture.apk", "sha256sum"
    ),
    "scripts/ci/r2d_emulator_ci.sh": (
        "pm install-create", "pm install-write", "pm install-commit", "am force-stop",
        "seedInterruptedInstallAndOwnedSession", "reconcileRealInstallAfterForceStop",
        "installed-version.txt", "real_android_apk_installed", "physical_device_qualified': False",
        "production-app-restart.txt", "am start -W -n"
    ),
    "scripts/ci/fixture_r2d/AndroidManifest.xml": (
        'package="com.aurora.r2d.fixture"', 'android:versionCode="73"',
        'android:hasCode="false"'
    ),
    "app/src/androidTest/java/com/aurora/store/data/room/download/InstallLifecycleRestartDeviceTest.kt": (
        "@RunWith(AndroidJUnit4::class)", "Room.databaseBuilder", "createSession(params)",
        "DownloadStatus.INSTALLING", "PackageUtil.getInstalledVersionCode", "aurora_database",
        "transitionInstallAttempt", "installer.abandonSession(sessionId)",
        "The separate production AuroraApp process must have performed recovery"
    ),
}
for path, fragments in requirements.items():
    source = load(path)
    if path.endswith("InstallLifecycleRestartDeviceTest.kt"):
        if "reconcileInstallStatus(" in source or "InstallRecoveryPolicy.resolve(" in source:
            raise SystemExit("R2D_CONTRACT_REFUSED: instrumentation is doing its own recovery")
    if path.endswith("r2d_build_fixture.sh") and '"$KEY"' in source:
        raise SystemExit("R2D_CONTRACT_REFUSED: undefined signing-key variable")
    for fragment in fragments:
        if fragment not in source:
            raise SystemExit(f"R2D_CONTRACT_REFUSED: {path}: missing {fragment}")
    print("R2D_CONTRACT_PASS:", path)
host_test = load("scripts/ci/test_r2d_host_contract.py")
for marker in ("commit_failure", "missing_version", "startup_failure", "instrumentation_failure"):
    if marker not in host_test:
        raise SystemExit(f"R2D_CONTRACT_REFUSED: missing host regression {marker}")
for shell in ("scripts/ci/r2d_build_fixture.sh", "scripts/ci/r2d_emulator_ci.sh"):
    subprocess.run(["bash", "-n", str(ROOT / shell)], check=True)
print(f"R2D_SOURCE_CONTRACT_PASS files={len(requirements)}")
