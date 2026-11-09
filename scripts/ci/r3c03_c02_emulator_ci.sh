#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
: "${RUNNER_TEMP:?}"
OUT="$RUNNER_TEMP/aurora-r3c03-c02"
mkdir -p "$OUT"
[[ "$(adb shell getprop ro.build.version.sdk | tr -d '\r')" == "36" ]] || {
  echo 'R3C03_C02_EMULATOR_REFUSED: requires API36' >&2
  exit 1
}
RUNNER="$(adb shell pm list instrumentation | tr -d '\r' |
  sed -nE '/target=com\.aurora\.store\.debug\)/s/^instrumentation:([^ ]+).*/\1/p' |
  grep 'HiltInstrumentationTestRunner' | head -n 1)"
[[ -n "$RUNNER" ]] || {
  echo 'R3C03_C02_EMULATOR_REFUSED: missing Hilt runner' >&2
  exit 1
}
CLASS='com.aurora.store.data.room.play.PlayVerifiedEvidenceDeviceTest'
timeout 300 adb shell am instrument -w -r -e class "$CLASS" "$RUNNER" |
  tee "$OUT/c02_room_evidence.txt"
if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|INSTRUMENTATION_STATUS_CODE: -[12]' \
  "$OUT/c02_room_evidence.txt"; then
  echo 'R3C03_C02_EMULATOR_REFUSED: instrumentation failed' >&2
  exit 1
fi
grep -Eq '^OK \(8 tests\)' "$OUT/c02_room_evidence.txt" || {
  echo 'R3C03_C02_EMULATOR_REFUSED: 8 Room tests were not reported' >&2
  exit 1
}
python3 - "$OUT/C02_EMULATOR_RECEIPT.json" <<'PY'
import json, os, sys
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps({
    'overall': 'PASS',
    'source_sha': os.environ.get('GITHUB_SHA', ''),
    'run_id': os.environ.get('GITHUB_RUN_ID', ''),
    'android_api': 36,
    'production_room_database_used': True,
    'room_evidence_tests': 8,
    'play_delivery_performed': False,
    'real_signed_apk_verified_by_c02_tests': False,
    'live_installation_performed': False,
    'physical_device_qualified': False,
    'release_qualified': False
}, indent=2, sort_keys=True) + '\n')
PY
echo 'R3C03_C02_EMULATOR_PASS: 8 actual Room tests on API36'
