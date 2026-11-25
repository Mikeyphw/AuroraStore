#!/usr/bin/env python3
"""R2A source-contract gate; Android compilation/tests only in hosted GitHub Actions."""
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
def load(path):
    return (ROOT / path).read_text(encoding='utf-8')

app = load('app/src/main/java/com/aurora/store/AuroraApp.kt')
helper = load('app/src/main/java/com/aurora/store/data/helper/DownloadHelper.kt')
installer = load('app/src/main/java/com/aurora/store/data/installer/SessionInstaller.kt')
policy = load('app/src/main/java/com/aurora/store/data/installer/InstallRecoveryPolicy.kt')
dao = load('app/src/main/java/com/aurora/store/data/room/download/DownloadDao.kt')
tests = load('app/src/test/java/com/aurora/store/data/installer/InstallRecoveryPolicyTest.kt')
workflow = load('.github/workflows/aurora-foundation.yml')

checks = {
    'no blanket session abandonment on application startup':
        'CommonUtil.cleanupInstallationSessions(applicationContext)' not in app,
    'recovery at startup and periodically':
        'reconcileInstallationRows(downloads, includeCompleted = true)' in helper and
        'reconcileInstallationRows(downloadDao.downloads().firstOrNull().orEmpty())' in helper,
    'recovery respects actual installed package version and owned sessions':
        'PackageUtil.getInstalledVersionCode(context, item.packageName)' in helper and
        'packageInstaller.mySessions' in helper and
        'hasLiveSession = item.packageName in livePackages' in helper,
    'recovery uses generation scoped CAS instead of unconditional DB updates':
        'downloadDao.reconcileInstallStatus(' in helper and
        'AND downloadedAt = :attemptKey' in dao and
        "downloadStatus IN ('COMPLETED', 'INSTALLING', 'AWAITING_INSTALL')" in dao,
    'never claim successful self update by previous installing flag':
        'finalizeStaleSelfUpdate(' not in helper,
    'restart skips committed Android session':
        'committedOwnedSession' in installer and 'session.isSealed' in installer,
    'empty sessions cannot be committed':
        'if (stagingFailed || stagedSessions.isEmpty())' in installer,
    'stage exceptions abandon session and report failure':
        'packageInstaller.abandonSession(sessionId)' in installer and
        'getFiles(packageName, versionCode, sharedLibPkgName)' in installer,
    'duplicate install request cannot recommit in flight':
        'commitNextPending()' in installer and
        'sessionSet.none { it.sessionId in committedSessions }' in installer,
    'explicit policy covers failed and awaiting outcomes':
        'hasLiveSession -> DownloadStatus.AWAITING_INSTALL' in policy and
        'else -> DownloadStatus.FAILED' in policy,
    'unit tests exercise recovery matrix':
        tests.count('@Test') >= 10,
    'hosted foundation runs source gate and Gradle JVM tests':
        'python3 -B scripts/ci/check_r2a.py' in workflow and
        'testVanillaDebugUnitTest' in workflow,
}
for label, ok in checks.items():
    print(('PASS' if ok else 'FAIL') + ' R2A ' + label)
if not all(checks.values()):
    raise SystemExit('R2A_SOURCE_CONTRACT_FAILED')
print('R2A_SOURCE_CONTRACT_PASS')
