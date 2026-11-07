#!/usr/bin/env python3
"""R1D source contract. Device behavior is independently checked by AndroidJUnit4."""
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import os
import re
import sys

root = Path(os.environ.get('R1D_SOURCE_ROOT', Path(__file__).resolve().parents[2]))


def read(path):
    return (root / path).read_text(encoding='utf-8')


lifecycle = read('app/src/androidTest/java/com/aurora/store/data/room/download/DownloadLifecycleDeviceTest.kt')
restart = read('app/src/androidTest/java/com/aurora/store/data/room/download/DownloadProcessRestartDeviceTest.kt')
stall = read('app/src/androidTest/java/com/aurora/store/data/work/TransferStallWatchdogDeviceTest.kt')
script = read('scripts/ci/r1d_emulator_ci.sh')
workflow = read('.github/workflows/aurora-r1d-emulator.yml')
doc = read('docs/R1D_EMULATOR_ACCEPTANCE.md')

checks = {
    '9 production Room DAO device tests': len(re.findall(r'@Test\s+fun ', lifecycle)) == 9 and
        'Room.inMemoryDatabaseBuilder(context, AuroraDatabase::class.java)' in lifecycle and
        '.addTypeConverter(DownloadConverter(' in lifecycle and
        'database.downloadDao()' in lifecycle,
    'Room protects cancelled transfer': 'cancellationDuringDownloadCannotBeResurrected' in lifecycle and
        'dao.cancelActiveDownload(' in lifecycle and 'dao.updateWorkerProgress(' in lifecycle,
    'Room protects verifier and installer handoff':
        'cancellationDuringVerificationRemainsPossible' in lifecycle and
        'installerHandoffDoesNotAcceptCancellationOrWorkerReentry' in lifecycle,
    'Room isolates same-version attempts and stale notifications':
        'sameVersionRetryCreatesNewAttemptAndRejectsOldWorker' in lifecycle and
        'obsoleteCancelCannotCancelFreshAttempt' in lifecycle,
    'Room guards superseded version and old clear action':
        'supersededVersionCannotMutateNewVersion' in lifecycle and
        'oldClearActionCannotDeleteReplacement' in lifecycle,
    'Room guards orphan and installed terminal state':
        'orphanRecoveryOnlyChangesMatchingAttempt' in lifecycle and
        'finishedInstallCannotBeRetroactivelyMarkedAsDownloadFailure' in lifecycle,
    '3 production watchdog device tests': len(re.findall(r'@Test\s+fun ', stall)) == 3 and
        'TransferStallWatchdog(' in stall and 'watchdog.onBytes(0)' in stall,
    '2 persistent Room device test phases': len(re.findall(r'@Test\s+fun ', restart)) == 2 and
        'Room.databaseBuilder(context, AuroraDatabase::class.java, DATABASE)' in restart and
        'dao.failOrphanedDownload(' in restart,
    'force-stop separates persistent phases':
        'adb shell am force-stop "$TARGET_PACKAGE"' in script and
        script.index('run_suite seed ') < script.index('adb shell am force-stop ') < script.index('run_suite reopen '),
    'exact production Hilt runner and API 36':
        'HiltInstrumentationTestRunner' in script and
        "== '36'" in script and
        'com.aurora.store.debug' in script,
    'device execution rejects failures and wrong test totals':
        'INSTRUMENTATION_FAILED' in script and 'R1D_REFUSED: unexpected test count' in script and
        'run_suite lifecycle ' in script and 'run_suite stall ' in script,
    'source-bound and non-release evidence':
        'source_sha' in script and 'real_download_worker_executed' in script and
        '"release_qualified": False' in script,
    'KVM API36 and pinned proven emulator action':
        'api-level: 36' in workflow and 'target: google_apis' in workflow and
        'arch: x86_64' in workflow and
        'ReactiveCircus/android-emulator-runner@a421e43855164a8197daf9d8d40fe71c6996bb0d' in workflow and
        'test -c /dev/kvm' in workflow,
    'Java21 and Android37.0 compile SDK platform retained':
        "java-version: '21'" in workflow and "'platforms;android-37.0'" in workflow,
    'both APKs compiled only on hosted runner':
        ':app:assembleVanillaDebug :app:assembleVanillaDebugAndroidTest' in workflow and
        'adb install -r "${APP_APKS[0]}"' in script and
        'adb install -r "${TEST_APKS[0]}"' in script,
    'fail closed if hosted tests did not execute':
        '"overall":"NOT_RUN"' in workflow and
        '"overall": "PASS"' in script,
    'offline fixtures explicitly avoid Play downloads':
        'Google Play delivery tests' in doc and
        '"google_play_download_performed": False' in script,
}
failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(('PASS ' if ok else 'FAIL ') + name)
if failed:
    print('R1D_CONTRACT_FAIL', file=sys.stderr)
    raise SystemExit(1)
print(f'R1D_CONTRACT_PASS checks={len(checks)}')
