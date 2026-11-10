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

# R3C-04: bounded local SAF and archive staging on the same API36 hosted emulator.
# Source and JVM contracts run in targeted CI; this device lane runs only at full gates.
python3 -B scripts/ci/test_r3c04_full_import.py
IMPORT_CLASS='com.aurora.store.data.artifact.ArtifactPrivateStagerDeviceTest'
timeout 300 adb shell am instrument -w -r -e class "$IMPORT_CLASS" "$RUNNER" |
  tee "$OUT/c04_private_import.txt"
if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|INSTRUMENTATION_STATUS_CODE: -[12]'   "$OUT/c04_private_import.txt"; then
  echo 'R3C04_EMULATOR_REFUSED: private import tests failed' >&2
  exit 1
fi
grep -Eq '^OK \(6 tests\)' "$OUT/c04_private_import.txt" || {
  echo 'R3C04_EMULATOR_REFUSED: expected six real staging device tests' >&2
  exit 1
}
echo 'R3C04_API36_STAGING_PASS: six bounded archive and cancellation tests'

# C04-03 HF01: real APK signer verification on the same periodic API36 gate.
SIGNER_CLASS='com.aurora.store.data.artifact.ArtifactApkVerifierDeviceTest'
timeout 300 adb shell am instrument -w -r -e class "$SIGNER_CLASS" "$RUNNER" |
  tee "$OUT/c04_real_apk_signer.txt"
if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|INSTRUMENTATION_STATUS_CODE: -[12]' \
  "$OUT/c04_real_apk_signer.txt"; then
  echo 'R3C04_HF01_SIGNER_REFUSED: real APK verification tests failed' >&2
  exit 1
fi
grep -Eq '^OK \(3 tests\)' "$OUT/c04_real_apk_signer.txt" || {
  echo 'R3C04_HF01_SIGNER_REFUSED: expected three real signed/corrupt APK device cases' >&2
  exit 1
}
echo 'R3C04_HF01_API36_SIGNER_PASS: signed APK, corruption and mutation cases'


# C04-04 HF02: verify *real* signed APK session revalidation and consent refusal.
# Additive API36 tests; never run full gate on each PR.
SESSION_CLASS='com.aurora.store.data.artifact.ArtifactInstallSessionDeviceTest'
timeout 300 adb shell am instrument -w -r -e class "$SESSION_CLASS" "$RUNNER" |
  tee "$OUT/c04_real_session_consent.txt"
if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|INSTRUMENTATION_STATUS_CODE: -[12]' \
  "$OUT/c04_real_session_consent.txt"; then
  echo 'R3C04_HF02_SESSION_REFUSED: real API36 consent/recheck tests failed' >&2
  exit 1
fi
grep -Eq '^OK \(5 tests\)' "$OUT/c04_real_session_consent.txt" || {
  echo 'R3C04_HF02_SESSION_REFUSED: five real non-installing API36 tests missing' >&2
  exit 1
}
echo 'R3C04_HF02_SESSION_PASS: fresh signer, consent and staged-byte mutation'
