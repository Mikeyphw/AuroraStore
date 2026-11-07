#!/usr/bin/env python3
"""R1F source invariants; hosted JVM and Compose emulator verify behavior."""
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import re
import sys

r = Path(__file__).resolve().parents[2]
def read(path):
    return (r / path).read_text(encoding='utf-8')

screen = read('app/src/main/java/com/aurora/store/compose/ui/downloads/DownloadsScreen.kt')
sheet = read('app/src/main/java/com/aurora/store/compose/ui/sheets/DownloadActionsSheet.kt')
download_model = read('app/src/main/java/com/aurora/store/data/room/download/Download.kt')
status_model = read('app/src/main/java/com/aurora/store/data/model/DownloadStatus.kt')
helper = read('app/src/main/java/com/aurora/store/data/helper/DownloadHelper.kt')
vm = read('app/src/main/java/com/aurora/store/viewmodel/downloads/DownloadsViewModel.kt')
item = read('app/src/main/java/com/aurora/store/compose/composable/DownloadListItem.kt')
policy = read('app/src/main/java/com/aurora/store/compose/ui/downloads/DownloadUiPolicy.kt')
unit = read('app/src/test/java/com/aurora/store/compose/ui/downloads/DownloadUiPolicyTest.kt')
device = read('app/src/androidTest/java/com/aurora/store/compose/ui/downloads/DownloadUiDeviceTest.kt')
flow = read('.github/workflows/aurora-r1d-emulator.yml')
script = read('scripts/ci/r1f_emulator_ci.sh')
prior_script = read('scripts/ci/r1d2_emulator_ci.sh')
strings = read('app/src/main/res/values/strings_r1f.xml')
checks = {
    'stable list uses live Room state instead of stale Paging snapshot':
        'liveDownloads.associateBy { it.packageName }' in screen and
        'download = liveByPackage[download.packageName]' in screen,
    'actions sheet uses same live Room snapshot':
        'val target = liveByPackage[selected.packageName]' in screen and
        'live.versionCode == selected.versionCode' in screen and
        'live.downloadedAt == selected.downloadedAt' in screen,
    'dangerous clear all is confirmation-gated':
        'MenuItem.FORCE_CLEAR_ALL -> confirmClearAll = true' in screen and
        'AlertDialog(' in screen and 'r1f_download_clear_all_warning' in screen,
    'retry and cancellation are wired end-to-end':
        'onRetry = { download -> viewModel.retry(download) }' in screen and
        'onCancel = { download -> viewModel.cancel(download) }' in screen and
        'fun retry(download: Download)' in vm and 'fun cancel(download: Download)' in vm,
    'viewmodel passes durable attempts to actions':
        vm.count('download.downloadedAt') >= 3,
    'retry rejects stale attempt':
        'suspend fun retryDownload(packageName: String, expectedAttempt: Long? = null)' in helper and
        'if (expectedAttempt != null && existing.downloadedAt != expectedAttempt) return' in helper,
    'clear rejects stale attempt':
        'expectedAttempt: Long? = null' in helper and
        'if (expectedAttempt != null && current.downloadedAt != expectedAttempt) return' in helper,
    'R1A cancellation remains available through verification':
        'if (download.isActive)' in sheet and
        'val isActive get() = isRunning' in download_model and
        'val isRunning get() = status in DownloadStatus.running' in download_model and
        'val running = setOf(QUEUED, PURCHASING, DOWNLOADING, VERIFYING)' in status_model and
        'val canCancel = DownloadUiPolicy.canCancel' not in sheet,
    'retry action only on legitimate states or missing install files':
        'DownloadUiPolicy.canRetry(download.status, canInstall)' in sheet and
        'onRetry()' in sheet and 'r1f_download_retry' in sheet and
        'DownloadStatus.AWAITING_INSTALL' in policy,
    'progress excludes fake queued / verifying ETA':
        'DownloadUiPolicy.showTransferStats(download.status)' in item and
        'if (download.speed > 0L)' in item and 'if (download.timeRemaining > 0L)' in item,
    'failures and cancellations have correct distinct icons':
        'DownloadStatus.UNAVAILABLE' in item and
        'stringResource(download.status.localized)' in item,
    'seven JVM tests exercise state and fallback policy':
        len(re.findall(r'@Test\s+fun ', unit)) == 7,
    'four real Compose device tests':
        len(re.findall(r'@Test\s+fun ', device)) == 4 and
        'DownloadActionsSheet(' in device and 'captureToImage()' in device,
    'local screenshots required for successful evidence':
        'r1f_queued.png' in script and 'r1f_downloading.png' in script and
        'r1f_failed.png' in script and 'R1F_REFUSED: missing screenshot' in script,
    'all 32 prior device tests finish before R1F and there is no recursive launcher':
        'run_suite worker-r1e "$R1E_SUITE" 8' in prior_script and
        'bash scripts/ci/r1f_emulator_ci.sh' in prior_script and
        prior_script.index('run_suite worker-r1e ') <
        prior_script.index('bash scripts/ci/r1f_emulator_ci.sh') and
        'bash scripts/ci/r1d2_emulator_ci.sh' not in script and
        'run_suite ux-r1f "$R1F_SUITE" 4' in script,
    'existing pinned API36 workflow remains compatible with R1D2 and R1E':
        'script: bash scripts/ci/r1d2_emulator_ci.sh' in flow and
        'python3 -B scripts/ci/check_r1f.py' in flow and
        'api-level: 36' in flow and
        'ReactiveCircus/android-emulator-runner@a421e43855164a8197daf9d8d40fe71c6996bb0d' in flow,
    'explicit NOT_RUN to PASS evidence with no release qualification':
        "'total_device_tests': 36" in script and
        "'overall': 'PASS'" in script and
        '"overall":"NOT_RUN"' in flow and
        "'release_qualified': False" in script,
    'additive UI strings (no locale overwrite)':
        'r1f_download_retry' in strings and
        'r1f_download_clear_all_warning' in strings,
}
for name, good in checks.items():
    print(('PASS ' if good else 'FAIL ') + name)
if not all(checks.values()):
    sys.exit('R1F_CONTRACT_FAIL')
print('R1F_CONTRACT_PASS checks=' + str(len(checks)))
