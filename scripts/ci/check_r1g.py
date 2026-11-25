#!/usr/bin/env python3
"""R1G source-contract gate; does not substitute for hosted device qualification."""
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import re

root = Path(__file__).resolve().parents[2]

def read(p): return (root / p).read_text(encoding='utf-8')
vm = read('app/src/main/java/com/aurora/store/viewmodel/downloads/DownloadsViewModel.kt')
worker = read('app/src/main/java/com/aurora/store/data/work/DownloadWorker.kt')
legacy = read('scripts/ci/r1d2_emulator_ci.sh')
r1f = read('scripts/ci/r1f_emulator_ci.sh')
r1g = read('scripts/ci/r1g_emulator_ci.sh')
gate = read('scripts/ci/r1g_evidence_gate.py')
device = read('app/src/androidTest/java/com/aurora/store/compose/ui/downloads/DownloadFinalUiDeviceTest.kt')
foundation = read('.github/workflows/aurora-foundation.yml')
emulator = read('.github/workflows/aurora-r1d-emulator.yml')
physical = read('scripts/ci/r1g_physical_device.sh')
docs = read('docs/R1G_FINAL_QUALIFICATION.md')

checks = {
 'install and export reread persisted current attempt':
     vm.count('currentAttempt(download) ?: return@launch') == 2 and
     'downloadHelper.getDownload(selected.packageName)' in vm and
     'current.versionCode == selected.versionCode' in vm and
     'current.downloadedAt == selected.downloadedAt' in vm,
 'install refuses absent or unverified cache':
     'if (!current.canInstall(context)) return@launch' in vm and
     'getPreferredInstaller(notifyOnFallback = true).install(current)' in vm,
 'export rejects missing payload and stale selected attempt':
     'PathUtil.getExportableFiles(context, current).isEmpty()' in vm and
     'ExportWorker.exportDownloadedApp(context, current, uri)' in vm,
 'debug loopback only fixture still separate from installer':
     'BuildConfig.DEBUG && R1EOfflineGate.enabled(inputData)' in worker and
     'private suspend fun downloadOfflineFixture()' in worker,
 'legacy emulator entry and all previous 36 tests remain intact':
     'bash scripts/ci/r1d_emulator_ci.sh' in legacy and
     'run_suite worker-r1e "$R1E_SUITE" 8' in legacy and
     'bash scripts/ci/r1f_emulator_ci.sh' in legacy and
     legacy.index('bash scripts/ci/r1f_emulator_ci.sh') < legacy.index('bash scripts/ci/r1g_emulator_ci.sh') and
     'run_suite ux-r1f "$R1F_SUITE" 4' in r1f and
     'script: bash scripts/ci/r1d2_emulator_ci.sh' in emulator,
 'four real final Compose tests drive actual action sheet':
     len(re.findall(r'@Test\s+fun ', device)) == 4 and
     '@RunWith(AndroidJUnit4::class)' in device and
     'DownloadActionsSheet(' in device and 'DownloadListItem(' in device and
     '.performClick()' in device,
 'legacy verifying cancellation requirement remains':
     'verifyingDownloadStillAllowsCancellation' in device and
     'DownloadStatus.VERIFYING' in device and
     'if (download.isActive)' in read('app/src/main/java/com/aurora/store/compose/ui/sheets/DownloadActionsSheet.kt'),
 'no unsound cached install, queued cancellation or false retry':
     'missingCachedApkShowsRetryWithoutInstallation' in device and
     'installingDoesNotExposeCancelOrRetry' in device and
     'cancelledShowsAccurateStatusWithoutFakeTransferStats' in device,
 'exact four tests and five verifiable PNG receipts':
     'OK \\(4 tests\\)' in r1g and
     'r1g_awaiting_retry.png' in r1g and 'r1g_cancelled.png' in r1g and
     "'device_tests': 40" in gate and "'sha256': hashlib.sha256(data).hexdigest()" in gate and
     'zlib.crc32(kind + payload)' in gate,
 'evidence fails closed on missing or mismatched source and unverified results':
     'source_sha' in gate and 'run_id' in gate and
     "result.get('overall') != 'PASS'" in gate and
     'R1G_EVIDENCE_REFUSED' in gate and
     "'release_qualified': False" in gate and
     "'physical_device_qualified': False" in gate,
 'one original pinned GitHub-hosted API36 emulator':
     'ReactiveCircus/android-emulator-runner@a421e43855164a8197daf9d8d40fe71c6996bb0d' in emulator and
     'api-level: 36' in emulator and
     'python3 -B scripts/ci/check_r1g.py' in emulator and
     'aurora-r1g-emulator/' in emulator,
 'release candidate build is unsigned and never published':
     ':app:assembleVanillaRelease' in foundation and
     'test ! -f app/signing.properties' in foundation and
     '"release_signed": False' in foundation and
     '"release_qualified": False' in foundation and
     'actions/upload-artifact@330a01c490aca151604b8cf639adc76d48f6c5d4' in foundation,
 'physical acceptance is manual and never auto-certified':
     'R1G_DEVICE_PENDING' in physical and
     "'physical_device_qualified': False" in physical and
     "'overall': 'PENDING_MANUAL'" in physical and
     'physical device' in docs.lower(),
 'R0–R1F source checks run before R1G':
     'python3 -B scripts/ci/check_r1f.py' in emulator and
     'python3 -B scripts/ci/check_r1g.py' in emulator,
}
for name, good in checks.items():
    print(('PASS ' if good else 'FAIL ') + name)
if not all(checks.values()):
    raise SystemExit('R1G_SOURCE_CONTRACT_FAIL')
print(f'R1G_SOURCE_CONTRACT_PASS checks={len(checks)}')
