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
grep -Eq '^OK \(17 tests\)' "$OUT/c04_private_import.txt" || {
  echo 'R3C04_EMULATOR_REFUSED: expected seventeen real staging device tests' >&2
  exit 1
}
echo 'R3C04_API36_STAGING_PASS: seventeen bounded archive and cancellation tests'

# C04-03 HF01: real APK signer verification on the same periodic API36 gate.
SIGNER_CLASS='com.aurora.store.data.artifact.ArtifactApkVerifierDeviceTest'
timeout 300 adb shell am instrument -w -r -e class "$SIGNER_CLASS" "$RUNNER" |
  tee "$OUT/c04_real_apk_signer.txt"
if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|INSTRUMENTATION_STATUS_CODE: -[12]' \
  "$OUT/c04_real_apk_signer.txt"; then
  echo 'R3C04_HF01_SIGNER_REFUSED: real APK verification tests failed' >&2
  exit 1
fi
grep -Eq '^OK \(7 tests\)' "$OUT/c04_real_apk_signer.txt" || {
  echo 'R3C04_HF01_SIGNER_REFUSED: expected seven signed/identity APK device cases' >&2
  exit 1
}
echo 'R3C04_HF01_API36_SIGNER_PASS: signed APK, tampering and exact identity safeguards'


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

# C04-07 HF08 — read-only UI/consent/insets test; no Android install performed.
UI_CLASS='com.aurora.store.data.artifact.ArtifactImportActivityDeviceTest'
timeout 300 adb shell am instrument -w -r -e class "$UI_CLASS" "$RUNNER" |
  tee "$OUT/c04_07_review_ui.txt"
if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|INSTRUMENTATION_STATUS_CODE: -[12]' \
  "$OUT/c04_07_review_ui.txt"; then
  echo 'R3C04_HF06_REVIEW_UI_REFUSED: API36 UI instrumentation failed' >&2
  exit 1
fi
grep -Eq '^OK \(3 tests\)' "$OUT/c04_07_review_ui.txt" || {
  echo 'R3C04_HF06_REVIEW_UI_REFUSED: three actual Android UI test cases missing' >&2
  exit 1
}
echo 'R3C04_HF06_API36_REVIEW_UI_PASS: three read-only tests'

# R3C-05: three explicit provider-choice and manual-consent UI cases.
# Read-only tests; no browser, APK download or installation is performed.
PROVIDER_CLASS='com.aurora.store.data.artifact.ArtifactProviderDiscoveryDeviceTest'
timeout 300 adb shell am instrument -w -r -e class "$PROVIDER_CLASS" "$RUNNER" |
  tee "$OUT/r3c05_provider_discovery_ui.txt"
if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|INSTRUMENTATION_STATUS_CODE: -[12]' \
  "$OUT/r3c05_provider_discovery_ui.txt"; then
  echo 'R3C05_PROVIDER_UI_REFUSED: API36 tests failed' >&2
  exit 1
fi
grep -Eq '^OK \(3 tests\)' "$OUT/r3c05_provider_discovery_ui.txt" || {
  echo 'R3C05_PROVIDER_UI_REFUSED: three real UI tests missing' >&2
  exit 1
}
echo 'R3C05_API36_PROVIDER_UI_PASS: three manual provider tests'

# R3C06: four read-only split-targeting tests on the periodic API36 gate.
# Complements, never replaces, earlier C04 signing/session/zip tests.
SPLIT_TARGET_CLASS='com.aurora.store.data.artifact.ArtifactSplitCompatibilityDeviceTest'
timeout 300 adb shell am instrument -w -r -e class "$SPLIT_TARGET_CLASS" "$RUNNER" |
  tee "$OUT/r3c06_split_targeting.txt"
if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|INSTRUMENTATION_STATUS_CODE: -[12]' \
  "$OUT/r3c06_split_targeting.txt"; then
  echo 'R3C06_SPLIT_API36_REFUSED: targeted splits failed' >&2
  exit 1
fi
grep -Eq '^OK \(4 tests\)' "$OUT/r3c06_split_targeting.txt" || {
  echo 'R3C06_SPLIT_API36_REFUSED: four actual Android tests missing' >&2
  exit 1
}
echo 'R3C06_API36_SPLIT_TARGETING_PASS: four read-only compatibility tests'

# R3C06 phase 2: six read-only APKM/XAPK metadata and staging tests on API36.
# Additive: no Play evidence, publisher trust, privileged install, or source fallback.
ARCHIVE_DESCRIPTOR_CLASS='com.aurora.store.data.artifact.ArtifactArchiveDescriptorDeviceTest'
timeout 300 adb shell am instrument -w -r -e class "$ARCHIVE_DESCRIPTOR_CLASS" "$RUNNER" |
  tee "$OUT/r3c06_archive_descriptors.txt"
if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|INSTRUMENTATION_STATUS_CODE: -[12]' \
  "$OUT/r3c06_archive_descriptors.txt"; then
  echo 'R3C06_P2_API36_REFUSED: APKM/XAPK tests failed' >&2
  exit 1
fi
grep -Eq '^OK \(6 tests\)' "$OUT/r3c06_archive_descriptors.txt" || {
  echo 'R3C06_P2_API36_REFUSED: six actual archive-format tests missing' >&2
  exit 1
}
echo 'R3C06_P2_API36_ARCHIVE_DESCRIPTOR_PASS: six bounded archive-format tests'


# R3C06 phase 3: actual signed debug APK bytes in APKM/XAPK wrappers.
# These cases are READ-ONLY; no installer session is submitted by this suite.
REAL_SIGNED_CLASS='com.aurora.store.data.artifact.ArtifactRealSignedArchiveDeviceTest'
timeout 360 adb shell am instrument -w -r -e class "$REAL_SIGNED_CLASS" "$RUNNER" |
  tee "$OUT/r3c06_real_signed_archives.txt"
if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|INSTRUMENTATION_STATUS_CODE: -[12]' \
  "$OUT/r3c06_real_signed_archives.txt"; then
  echo 'R3C06_P3_SIGNED_ARCHIVES_REFUSED: actual signed APKM/XAPK tests failed' >&2
  exit 1
fi
grep -Eq '^OK \(6 tests\)' "$OUT/r3c06_real_signed_archives.txt" || {
  echo 'R3C06_P3_SIGNED_ARCHIVES_REFUSED: six actual signed-APK tests missing' >&2
  exit 1
}
echo 'R3C06_P3_SIGNED_ARCHIVES_PASS: six API36 signed APKM/XAPK import tests'

# R3C06 P4: exact-SHA, measured, READ-ONLY API36 instrumentation receipt.
# Never claim a live install or bundletool qualification from these logs.
python3 -B scripts/ci/r3c06_readonly_receipt.py \
  --logs "$OUT" --receipt "$OUT/R3C06_P4_API36_READONLY_RECEIPT.json"
echo 'R3C06_P4_API36_READONLY_EVIDENCE_PASS: 51 actually executed tests'

# REAL OS installation is explicitly opt-in: this never runs on ordinary PR CI.
# It creates and deletes ONLY an isolated synthetic fixture package on API36 emulator.
if [[ "${R3C06_ALLOW_LIVE_INSTALL:-no}" == yes ]]; then
  python3 -B scripts/ci/r3c06_api36_live_install.py \
    --receipt "$OUT/R3C06_P3_LIVE_OS_INSTALL_RECEIPT.json"
else
  echo 'R3C06_P3_LIVE_OS_INSTALL_NOT_QUALIFIED: explicit opt-in required'
fi

# A SHA256-pinned official bundletool binary AND a real fixture AAB are required.
# Never silently certify a dimension or use untrusted toc.pb as publisher proof.
if [[ -n "${R3C06_BUNDLETOOL_JAR:-}" && -n "${R3C06_BUNDLETOOL_SHA256:-}" && -n "${R3C06_AAB_FIXTURE:-}" ]]; then
  python3 -B scripts/ci/r3c06_bundletool_matrix.py \
    --bundle "$R3C06_AAB_FIXTURE" \
    --bundletool-jar "$R3C06_BUNDLETOOL_JAR" \
    --bundletool-sha256 "$R3C06_BUNDLETOOL_SHA256" \
    --receipt "$OUT/R3C06_P3_BUNDLETOOL_MATRIX_RECEIPT.json"
else
  echo 'R3C06_P3_BUNDLETOOL_NOT_QUALIFIED: signed AAB and pinned bundletool required'
fi

# P6: second *independent* real AAB, never relabel Aurora's production AAB.
# This block is reachable only after the existing 51-case read-only gate and
# the production matrix have completed on this same emulator/source/run.
if [[ -n "${R3C06_P6_FEATURE_AAB:-}" ]]; then
  [[ -s "$R3C06_P6_FEATURE_AAB" && -s "${R3C06_AAB_FIXTURE:-}" &&
     -s "${R3C06_BUNDLETOOL_JAR:-}" && -n "${R3C06_BUNDLETOOL_SHA256:-}" ]] || {
    echo R3C06_P6_FEATURE_INPUTS_MISSING >&2
    exit 1
  }
  python3 -B scripts/ci/r3c06_p6_feature_aab.py \
    --bundle "$R3C06_P6_FEATURE_AAB" \
    --bundletool-jar "$R3C06_BUNDLETOOL_JAR" \
    --receipt "$OUT/R3C06_P6_FIXTURE_MANIFEST_RECEIPT.json"
  python3 -B scripts/ci/r3c06_bundletool_matrix.py \
    --bundle "$R3C06_P6_FEATURE_AAB" \
    --bundletool-jar "$R3C06_BUNDLETOOL_JAR" \
    --bundletool-sha256 "$R3C06_BUNDLETOOL_SHA256" \
    --feature featureproof \
    --receipt "$OUT/R3C06_P6_FEATURE_MATRIX_RECEIPT.json"
fi
