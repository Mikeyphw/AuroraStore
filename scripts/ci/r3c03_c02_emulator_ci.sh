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

# C03: one real Android Room v15 -> v16 upgrade with persisted download/account/binding.
# This is additive: never replace the original 40 R1D/R1G or eight C02 cases.
python3 -B scripts/ci/test_r3c03_c03_schema.py
MIGRATION_CLASS='com.aurora.store.data.room.play.RoomV15ToV16MigrationDeviceTest'
timeout 300 adb shell am instrument -w -r -e class "$MIGRATION_CLASS" "$RUNNER" |
  tee "$OUT/c03_real_room_migration.txt"
if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|INSTRUMENTATION_STATUS_CODE: -[12]' \
  "$OUT/c03_real_room_migration.txt"; then
  echo 'R3C03_C03_EMULATOR_REFUSED: Room migration failed' >&2
  exit 1
fi
grep -Eq '^OK \(1 test\)' "$OUT/c03_real_room_migration.txt" || {
  echo 'R3C03_C03_EMULATOR_REFUSED: actual migration test missing' >&2
  exit 1
}
SCHEMA16='app/schemas/com.aurora.store.data.room.AuroraDatabase/16.json'
[[ -s "$SCHEMA16" ]] || {
  echo 'R3C03_C03_SCHEMA_NOT_EXPORTED: Room 16.json absent after KSP build' >&2
  exit 1
}
python3 -B scripts/ci/test_r3c03_c03_schema.py
# Fail if hosted Room KSP regenerated a schema different from the tracked export.
git diff --exit-code -- "$SCHEMA16" || {
  echo 'R3C03_C03_SCHEMA_DRIFT: checked-in v16 schema differs from hosted KSP' >&2
  exit 1
}
cp -- "$SCHEMA16" "$OUT/HOST_GENERATED_R3C03_SCHEMA_16.json"
python3 - "$OUT/C03_MIGRATION_RECEIPT.json" "$SCHEMA16" <<'PYR3C03C03'
import hashlib, json, os, sys
from pathlib import Path
schema = Path(sys.argv[2])
Path(sys.argv[1]).write_text(json.dumps({
    'overall': 'PASS', 'source_sha': os.environ.get('GITHUB_SHA', ''),
    'run_id': os.environ.get('GITHUB_RUN_ID', ''), 'android_api': 36,
    'room_v15_to_v16_real_migration_tests': 1,
    'download_account_binding_preserved': True,
    'room_v16_generated_schema_sha256': hashlib.sha256(schema.read_bytes()).hexdigest(),
    'schema_committed_to_master': False,
    'live_play_qualified': False, 'physical_device_qualified': False,
    'release_signed': False
}, indent=2, sort_keys=True) + '\n')
PYR3C03C03
echo 'R3C03_C03_API36_MIGRATION_PASS: 1 on-device migration; generated schema preserved in artifact'
