#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
OUT="${RUNNER_TEMP:?}/aurora-r1d2-emulator"
mkdir -p "$OUT"

# Retain the previously qualified 14-case R1D gate in the same hosted emulator.
bash scripts/ci/r1d_emulator_ci.sh
[[ "$(adb shell getprop ro.build.version.sdk | tr -d '\r')" == '36' ]] || {
  echo 'R1D2_REFUSED: device is not API36' >&2
  exit 1
}
TARGET='com.aurora.store.debug'
RUNNER="$(adb shell pm list instrumentation | tr -d '\r' | \
  sed -nE '/target=com\.aurora\.store\.debug\)/s/^instrumentation:([^ ]+).*/\1/p' | \
  grep 'HiltInstrumentationTestRunner' | head -n 1)"
[[ -n "$RUNNER" ]] || { echo 'R1D2_REFUSED: Hilt runner missing' >&2; exit 1; }

run_suite() {
  local name="$1" selector="$2" expected="$3"
  timeout 300 adb shell am instrument -w -r -e class "$selector" "$RUNNER" \
    | tee "$OUT/${name}.txt"
  if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|INSTRUMENTATION_STATUS_CODE: -[12]' \
    "$OUT/${name}.txt"; then
    echo "R1D2_TEST_FAIL: $name" >&2
    exit 1
  fi
  grep -Eq "^OK \(${expected} tests?\)" "$OUT/${name}.txt" || {
    echo "R1D2_REFUSED: expected $expected successful tests in $name" >&2
    exit 1
  }
  echo "R1D2_PASS: $name"
}
HTTP='com.aurora.store.data.work.OfflineHttpResumeDeviceTest'
WORK='com.aurora.store.data.work.OfflineWorkManagerDeviceTest'
run_suite http "$HTTP" 6
run_suite work-cancel "$WORK#cancellationOfOldAttemptDoesNotCancelNewAttempt" 1
run_suite work-execute "$WORK#offlineWorkerExecutesWithExpectedAttempt" 1
run_suite work-seed "$WORK#seedPersistentAttemptAcrossForceStop" 1
adb shell am force-stop "$TARGET"
run_suite work-reopen "$WORK#verifyPersistentAttemptAfterForceStop" 1

python3 - "$OUT/R1D2_EMULATOR_RECEIPT.json" <<'PY'
import json, os, sys
from pathlib import Path
receipt = {
    'overall': 'PASS', 'mode': 'hosted-api36-google_apis-x86_64',
    'source_sha': os.getenv('GITHUB_SHA', ''), 'run_id': os.getenv('GITHUB_RUN_ID', ''),
    'prior_r1d_device_tests': 14, 'new_r1d2_device_tests': 10, 'total_device_tests': 24,
    'real_local_http_sockets': True, 'real_android_workmanager_worker': True,
    'real_force_stop_between_workmanager_runs': True,
    'google_play_delivery_performed': False, 'production_download_worker_executed': False,
    'physical_device_qualified': False, 'release_qualified': False,
}
Path(sys.argv[1]).write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
PY

# Run the real Hilt-assisted DownloadWorker with an offline, loopback-only transport.
R1E_OUT="${RUNNER_TEMP:?}/aurora-r1e-emulator"
mkdir -p "$R1E_OUT"
R1E_SUITE='com.aurora.store.data.work.DownloadWorkerOfflineDeviceTest'
run_suite worker-r1e "$R1E_SUITE" 8
python3 - "$R1E_OUT/R1E_EMULATOR_RECEIPT.json" <<'PYR1E'
import json, os, sys
from pathlib import Path
receipt = {
    'overall': 'PASS',
    'source_sha': os.getenv('GITHUB_SHA', ''),
    'run_id': os.getenv('GITHUB_RUN_ID', ''),
    'hosted_api36': True,
    'previous_device_tests': 24,
    'real_download_worker_offline_tests': 8,
    'total_device_tests': 32,
    'hilt_assisted_real_download_worker_executed': True,
    'direct_test_worker_builder_not_workmanager_scheduled': True,
    'loopback_only_transport': True,
    'google_play_delivery_performed': False,
    'real_apk_installation_performed': False,
    'physical_device_qualified': False,
    'release_qualified': False,
}
Path(sys.argv[1]).write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
PYR1E

echo 'R1E_EMULATOR_ACCEPTANCE_PASS: 32 offline Android device tests'

# R1F adds UI acceptance after all 32 previous tests and their receipts pass.
bash scripts/ci/r1f_emulator_ci.sh
