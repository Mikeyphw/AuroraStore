#!/usr/bin/env python3
"""R2C source contract. Hosted Kotlin/JVM and Android CI provide compilation evidence."""
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def load(path):
    return (ROOT / path).read_text(encoding="utf-8")

cases = [
    ("backend success is conditional on PM exit and receipt",
     "app/src/main/java/com/aurora/store/data/installer/InstallerBackendPolicy.kt",
     ("commandSucceeded(exitOk", "successPattern.containsMatchIn", "isInstalled(")),
    ("root requires each write and terminal commit to succeed",
     "app/src/main/java/com/aurora/store/data/installer/RootInstaller.kt",
     ("InstallerBackendPolicy.createdSession(", "pm install-abandon", "onInstallationSuccess(download)",
      "InstallerBackendPolicy.commandSucceeded(")),
    ("Shizuku does not report textual PM failures as success",
     "app/src/main/java/com/aurora/store/data/installer/ShizukuInstaller.kt",
     ("InstallerBackendPolicy.commandSucceeded(", "install-abandon", "onInstallationSuccess(download)",
      "!installPackage(download, library.packageName)")),
    ("Aurora Services callback accepts legacy ABI and one terminal outcome",
     "app/src/main/java/com/aurora/store/data/installer/ServiceInstaller.kt",
     ("AtomicBoolean(false)", "compareAndSet(false, true)", "handleResult(", "handleResultX(",
      "CALLBACK_TIMEOUT_MS", "installSplitPackageMore", "installSplitPackageX", "download",
      "val reserved = synchronized(AuroraApp.enqueuedInstalls)", "else if (finished.get())")),
    ("microG launch holds generation identity and requires APKs",
     "app/src/main/java/com/aurora/store/data/installer/MicroGInstaller.kt",
     ("files.isEmpty()", "MicroGInstallerActivity.launch(context, download, files)",
      "fun isAvailable(context: Context)", "resolveActivity(")),
    ("preferred microG installer falls back when target activity is not available",
     "app/src/main/java/com/aurora/store/data/installer/AppInstaller.kt",
     ("Installer.MICROG -> if (MicroGInstaller.isAvailable(context))",)),
    ("microG activity returns only OS-confirmed installed success",
     "app/src/main/java/com/aurora/store/data/activity/MicroGInstallerActivity.kt",
     ("EXTRA_VERSION", "EXTRA_ATTEMPT", "InstallerBackendPolicy.isInstalled(",
      "InstallerEvent.Installed(packageName, attempt)", "reportFailure(")),
    ("base event includes immutable attempt, never unconditionally notifies success",
     "app/src/main/java/com/aurora/store/data/installer/base/InstallerBase.kt",
     ("InstallAttempt(it.versionCode, it.downloadedAt)", "fun onInstallationSuccess(",
      "attempt = identified?.let")),
    ("Room CAS and OS package state are required for first-success side effects",
     "app/src/main/java/com/aurora/store/data/helper/DownloadHelper.kt",
     ("PackageUtil.getInstalledVersionCode(", "if (event is InstallerEvent.Installed)",
      "transitionInstallAttempt(", "if (installedVersion < current.versionCode)")),
    ("Kotlin unit tests cover success, failure, session and version policies",
     "app/src/test/java/com/aurora/store/data/installer/InstallerBackendPolicyTest.kt",
     ("fun acceptsValidSession()", "fun rejectsNonSuccessResponseWithZeroExit()",
      "fun requiresInstalledTargetVersion()")),
    ("Foundation runs R2C and R2D contracts",
     ".github/workflows/aurora-foundation.yml",
     ("scripts/ci/check_r2c.py", "scripts/ci/check_r2d.py")),
]
for label, path, required in cases:
    source = load(path)
    for fragment in required:
        if fragment not in source:
            raise SystemExit(f"R2C_CONTRACT_REFUSED: {label}: missing {fragment}")
    print("R2C_CONTRACT_PASS:", label)
if "notifyInstallation(context, it.displayName, it.packageName)" in load(
    "app/src/main/java/com/aurora/store/data/installer/base/InstallerBase.kt"
):
    raise SystemExit("R2C_CONTRACT_REFUSED: privileged backend has unconditional side effects")
print(f"R2C_CONTRACT_PASS checks={len(cases)}")
