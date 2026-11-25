#!/usr/bin/env python3
"""Fail-closed source-contract checks for R2B installer callback ordering."""
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("R2B_CONTRACT_REFUSED: " + message)


def main() -> None:
    event = read("app/src/main/java/com/aurora/store/data/event/BusEvent.kt")
    session = read("app/src/main/java/com/aurora/store/data/installer/SessionInstaller.kt")
    info = read("app/src/main/java/com/aurora/store/data/model/SessionInfo.kt")
    callback = read("app/src/main/java/com/aurora/store/data/receiver/BaseInstallerStatusReceiver.kt")
    helper = read("app/src/main/java/com/aurora/store/data/helper/DownloadHelper.kt")
    dao = read("app/src/main/java/com/aurora/store/data/room/download/DownloadDao.kt")
    policy = read("app/src/main/java/com/aurora/store/data/installer/InstallResultPolicy.kt")
    tests = read("app/src/test/java/com/aurora/store/data/installer/InstallResultPolicyTest.kt")
    workflow = read(".github/workflows/aurora-foundation.yml")
    app_installer = read("app/src/main/java/com/aurora/store/data/installer/AppInstaller.kt")

    tests_to_run = {
        "immutable event identity": "data class InstallAttempt(" in event and "val downloadedAt: Long" in event,
        "event identity propagated": event.count("override val attempt: InstallAttempt? = null") >= 4,
        "session keeps attempt": "val downloadedAt: Long" in info,
        "session includes parent": "val parentPackageName: String" in info,
        "pending-intent attempt": "putExtra(EXTRA_ATTEMPT_KEY, sessionInfo.downloadedAt)" in session,
        "pending-intent parent": "putExtra(EXTRA_PARENT_PACKAGE_NAME, sessionInfo.parentPackageName)" in session,
        "progress carries attempt": "attempt = InstallAttempt(" in session,
        "app installer constants": "const val EXTRA_ATTEMPT_KEY" in app_installer
        and "const val EXTRA_PARENT_PACKAGE_NAME" in app_installer,
        "receiver async lifecycle": "val pendingResult = goAsync()" in callback
        and "pendingResult.finish()" in callback,
        "receiver rejects mismatched attempt": "InstallResultPolicy.matches(" in callback,
        "receiver uses atomic transition": "downloadDao.transitionInstallAttempt(" in callback,
        "receiver guards side effects": callback.index("downloadDao.transitionInstallAttempt(")
        < callback.index("InstallerBase.notifyInstallation("),
        "receiver rejects missing attempt": "if (downloadedAt < 0L)" in callback,
        "pending user action sentinel": "PackageInstaller.EXTRA_STATUS, Int.MIN_VALUE" in callback
        and "status == Int.MIN_VALUE" in callback
        and "status == -1" not in callback,
        "shared-library parent handling": "parentPackageName != packageName" in callback,
        "observer uses exact identity": "InstallResultPolicy.matches(" in helper,
        "observer uses atomic transition": "downloadDao.transitionInstallAttempt(" in helper,
        "observer checks unscoped success": "val installedVersion = PackageUtil.getInstalledVersionCode(" in helper,
        "no unscoped status overwrite": "downloadDao.updateStatus(event.packageName" not in helper
        and "downloadDao.updateStatus(packageName" not in callback,
        "dao CAS conditions": all(
            field in dao for field in (
                "AND downloadedAt = :attemptKey AND downloadStatus = :expected",
                "suspend fun transitionInstallAttempt(",
            )
        ),
        "policy terminal success": "DownloadStatus.INSTALLED" in policy
        and "result?.takeIf { it != current }" in policy,
        "policy JVM tests": tests.count("@Test") >= 9,
        "foundation CI gate": "python3 -B scripts/ci/check_r2b.py" in workflow,
        "sqlite replay gate": "python3 -B scripts/ci/test_r2b_sql_cas.py" in workflow,
    }
    for name, passed in tests_to_run.items():
        require(passed, name)
        print("R2B_SOURCE_PASS", name)
    print(f"R2B_SOURCE_CONTRACT_PASS: {len(tests_to_run)} checks")


if __name__ == "__main__":
    main()
