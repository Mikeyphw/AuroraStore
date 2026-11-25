#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

OUT="${RUNNER_TEMP:?}/aurora-r1d-emulator"
mkdir -p "$OUT"

[[ "$(adb shell getprop ro.build.version.sdk | tr -d '\r')" == '36' ]] || {
  echo 'R1D_REFUSED: emulator is not API 36' >&2
  exit 1
}

mapfile -t APP_APKS < <(find app/build/outputs/apk/vanilla/debug -type f -name '*.apk' | sort)
mapfile -t TEST_APKS < <(find app/build/outputs/apk/androidTest -type f -name '*.apk' | sort)
if (( ${#APP_APKS[@]} != 1 || ${#TEST_APKS[@]} != 1 )); then
  printf 'R1D_REFUSED: expected one vanillaDebug APK and one AndroidTest APK (app=%s, test=%s)\n' \
    "${#APP_APKS[@]}" "${#TEST_APKS[@]}" >&2
  exit 1
fi

adb install -r "${APP_APKS[0]}"
adb install -r "${TEST_APKS[0]}"

TARGET_PACKAGE='com.aurora.store.debug'
RUNNER="$(adb shell pm list instrumentation | tr -d '\r' | \
    sed -nE '/target=com\.aurora\.store\.debug\)/s/^instrumentation:([^ ]+).*/\1/p' | \
    grep 'HiltInstrumentationTestRunner' | head -n 1)"
[[ -n "$RUNNER" ]] || { echo 'R1D_REFUSED: Hilt instrumentation runner not installed' >&2; exit 1; }

run_suite() {
  local label="$1" selector="$2" expected="$3"
  echo "R1D_START: $label $selector"
  timeout 300 adb shell am instrument -w -r -e class "$selector" "$RUNNER" \
    | tee "$OUT/${label}.txt"
  if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|INSTRUMENTATION_STATUS_CODE: -[12]' "$OUT/${label}.txt"; then
    echo "R1D_TEST_FAIL: $label" >&2
    exit 1
  fi
  grep -Eq "^OK \(${expected} tests?\)" "$OUT/${label}.txt" || {
    echo "R1D_REFUSED: unexpected test count for $label (expected $expected)" >&2
    exit 1
  }
  echo "R1D_PASS: $label"
}

run_suite lifecycle 'com.aurora.store.data.room.download.DownloadLifecycleDeviceTest' 9
run_suite stall 'com.aurora.store.data.work.TransferStallWatchdogDeviceTest' 3
run_suite seed 'com.aurora.store.data.room.download.DownloadProcessRestartDeviceTest#seedPersistedProcessingAttempt' 1

# A new instrumentation process must reopen the persisted database after an actual force-stop.
adb shell am force-stop "$TARGET_PACKAGE"
run_suite reopen 'com.aurora.store.data.room.download.DownloadProcessRestartDeviceTest#verifyPersistedAttemptAfterForceStop' 1

# No live Google account, anonymous Play token, network download or APK installation occurs.
python3 - "$OUT/R1D_EMULATOR_RECEIPT.json" <<'PY'
import json
import os
import sys
from pathlib import Path
receipt = {
    "overall": "PASS",
    "mode": "hosted-api36-x86_64-google_apis",
    "source_sha": os.environ.get("GITHUB_SHA", ""),
    "run_id": os.environ.get("GITHUB_RUN_ID", ""),
    "android_device_tests": 14,
    "suites": {"lifecycle": 9, "stall": 3, "seed": 1, "reopen": 1},
    "real_process_force_stop_between_seed_and_reopen": True,
    "production_room_dao": True,
    "google_play_download_performed": False,
    "live_network_interruptions_tested": False,
    "real_download_worker_executed": False,
    "physical_device_qualified": False,
    "release_qualified": False,
}
Path(sys.argv[1]).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
PY

echo 'R1D_API36_INSTRUMENTATION_PASS: 14 deterministic device tests'
