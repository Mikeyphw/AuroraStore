#!/usr/bin/env python3
"""R1E source acceptance; actual Hilt/HTTP behavior is gated by hosted API36."""
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[2]
def read(rel): return (root / rel).read_text(encoding='utf-8')

worker = read('app/src/main/java/com/aurora/store/data/work/DownloadWorker.kt')
gate = read('app/src/main/java/com/aurora/store/data/work/R1EOfflineGate.kt')
tests = read('app/src/androidTest/java/com/aurora/store/data/work/DownloadWorkerOfflineDeviceTest.kt')
script = read('scripts/ci/r1d2_emulator_ci.sh')
flow = read('.github/workflows/aurora-r1d-emulator.yml')
versions = read('gradle/libs.versions.toml')
app = read('app/build.gradle.kts')

checks = {
    'stale worker skips auth before any Play calls':
        worker.index('current.downloadedAt != expectedAttempt') <
        worker.index('super.doWork()') < worker.index('deliveryClient = playClientFor('),
    'offline transport compiled out in production':
        'BuildConfig.DEBUG && R1EOfflineGate.enabled(inputData)' in worker,
    'offline gate rejects arbitrary packages and remote hosts':
        'fixturePackage.matches(packageName)' in gate and
        'endpoint.host == "127.0.0.1"' in gate and
        'endpoint.scheme == "http"' in gate,
    'offline bounds and sha required':
        'bytes in 1L..1_048_576L' in gate and 'sha256.matches(checksum)' in gate,
    'offline path executes production transfer':
        'transfer(url, file, expectedSize)' in worker and 'downloadOfflineFixture()' in worker,
    'offline path rejects corrupted content':
        'MessageDigest.getInstance("SHA-256")' in worker and
        'file.length() != expectedSize || digest != expectedDigest' in worker and
        'file.delete()' in worker,
    'offline result never calls production installer':
        'private suspend fun downloadOfflineFixture()' in worker and
        'appInstaller.getPreferredInstaller' not in worker.split('private suspend fun downloadOfflineFixture()', 1)[1].split('private suspend fun onSuccess()', 1)[0],
    'offline payload remains attempt-private':
        '"r1e-$packageName-$attemptKey.apk"' in gate,
    'production handles truncated HTTP as retry':
        'is IOException -> true' in worker and 'Result.retry()' in worker,
    'eight executable Hilt assisted-worker device tests':
        len(re.findall(r'@Test\s+fun ', tests)) == 8 and '@HiltAndroidTest' in tests and
        'TestListenableWorkerBuilder<DownloadWorker>' in tests and
        '.setWorkerFactory(workerFactory)' in tests,
    'offline tests actually drive HTTP sockets and database':
        'ServerSocket(0' in tests and 'dao.getDownload(pkg)' in tests and
        'invalidContentRangeDeletesPartialAndRequestsRetry' in tests,
    'work testing dependency only added to instrumentation':
        'androidx-work-testing = ' in versions and
        'androidTestImplementation(libs.androidx.work.testing)' in app,
    'old 24 device tests execute before the eight new tests':
        'bash scripts/ci/r1d_emulator_ci.sh' in script and
        'run_suite http "$HTTP" 6' in script and
        'run_suite worker-r1e "$R1E_SUITE" 8' in script and
        script.index('run_suite worker-r1e ') > script.index('run_suite work-reopen '),
    'single hosted emulator workflow and fail-closed new receipt':
        'python3 -B scripts/ci/check_r1e.py' in flow and
        '"overall":"NOT_RUN"' in flow and
        'R1E_EMULATOR_RECEIPT.json' in flow and
        'api-level: 36' in flow and
        'script: bash scripts/ci/r1d2_emulator_ci.sh' in flow,
    'receipt distinguishes worker builder from real scheduler':
        "'direct_test_worker_builder_not_workmanager_scheduled': True" in script and
        "'total_device_tests': 32" in script and
        "'release_qualified': False" in script,
}
for name, good in checks.items():
    print(('PASS ' if good else 'FAIL ') + name)
if not all(checks.values()):
    print('R1E_CONTRACT_FAIL', file=sys.stderr)
    raise SystemExit(1)
print(f'R1E_CONTRACT_PASS checks={len(checks)}')
