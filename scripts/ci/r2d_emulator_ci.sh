#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
OUT="${RUNNER_TEMP:?}/aurora-r2d-emulator"
mkdir -p "$OUT"
[[ "$(adb shell getprop ro.build.version.sdk | tr -d '\r')" == '36' ]] || {
  echo R2D_REFUSED_NOT_API36 >&2
  exit 1
}
mapfile -t APP_APKS < <(find app/build/outputs/apk/vanilla/debug -type f -name '*.apk' | sort)
mapfile -t TEST_APKS < <(find app/build/outputs/apk/androidTest -type f -name '*.apk' | sort)
(( ${#APP_APKS[@]} == 1 && ${#TEST_APKS[@]} == 1 )) || {
  echo R2D_REFUSED_UNIQUE_APK_REQUIRED >&2
  exit 1
}
FIXTURE="$OUT/r2d-fixture.apk"
[[ -s "$FIXTURE" ]] || { echo R2D_REFUSED_FIXTURE_MISSING >&2; exit 1; }
sha256sum -c "$OUT/r2d-fixture.sha256"
adb install -r "${APP_APKS[0]}"
adb install -r "${TEST_APKS[0]}"
TARGET='com.aurora.store.debug'
RUNNER="$(adb shell pm list instrumentation | tr -d '\r' |     sed -nE '/target=com\.aurora\.store\.debug\)/s/^instrumentation:([^ ]+).*/\1/p' |     grep 'HiltInstrumentationTestRunner' | head -n 1)"
[[ -n "$RUNNER" ]] || { echo R2D_INSTRUMENTATION_MISSING >&2; exit 1; }
SUITE='com.aurora.store.data.room.download.InstallLifecycleRestartDeviceTest'
run_case() {
  local label="$1" selector="$2" log="$OUT/$1.txt"
  timeout 300 adb shell am instrument -w -r -e class "$selector" "$RUNNER" | tee "$log"
  if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|INSTRUMENTATION_STATUS_CODE: -[12]' "$log"; then
    echo "R2D_INSTRUMENTATION_FAILED: $label" >&2
    exit 1
  fi
  grep -Eq '^OK \(1 test\)' "$log" || {
    echo "R2D_REFUSED_INSTRUMENTATION_COUNT: $label" >&2
    exit 1
  }
}
# R3B uses signed fixture APKs in Aurora's private cache. This exercises the real
# Android package archive reader and signature verifier, not a mocked result.
R3B="$OUT/r3b"
sha256sum -c "$R3B/sha256sums.txt"
adb shell run-as "$TARGET" mkdir -p cache/r3b-fixtures
for fixture in "$R3B"/*.apk; do
  filename="$(basename "$fixture")"
  adb push "$fixture" "/data/local/tmp/$filename" >/dev/null
  adb shell run-as "$TARGET" cp "/data/local/tmp/$filename" "cache/r3b-fixtures/$filename"
  adb shell rm -f "/data/local/tmp/$filename"
done
# OS state is real: installed package signer must match a subsequent verified APK set.
adb install -r "$R3B/base.apk"
R3B_SUITE='com.aurora.store.data.installer.verification.ApkSetVerifierDeviceTest'
for case in \
  correctOfflineSignedApkAndVersionAreAccepted \
  wrongRequestedPackageIsRejected \
  wrongRequestedVersionIsRejected \
  validHistoricalVersionIsAcceptedAsExactArtifact \
  truncatedApkIsRejectedEvenWhenMetadataMatchesItsBytes \
  invalidPlayHashIsRejected \
  missingSplitIsRejected \
  mismatchedSplitSignerIsRejected \
  installedPackageWithDifferentSignerIsRejected \
  alteredSigningBlockIsRejectedEvenWithUpdatedDownloadHash \
  undeclaredCachedApkIsRejected \
  stalePartialDownloadIsRejected \
  cancelledAndReplacedAttemptsAreNotInstallable \
  verificationInterruptedBeforeInstallIsRejected \
  privateVerifiedSnapshotCannotBeSwappedWithCacheReplacement \
  validSignedSplitsRequireMatchingManifestAndSigner; do
  run_case "r3b-$case" "$R3B_SUITE#$case"
done
python3 - "$R3B/receipt.json" <<'PYR3B'
import json,os,sys
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps({
  'result':'PASS', 'source_sha':os.environ['GITHUB_SHA'],
  'run_id':os.environ['GITHUB_RUN_ID'],
  'device':'hosted-api36-x86_64','signed_fixture_archive_tests':14,
  'google_play_provenance_verified':False, 'physical_arm64_verified':False,
  'live_privileged_backend_verified':False,
  'release_qualified':False
},sort_keys=True,indent=2)+'\n')
PYR3B
run_case seed "$SUITE#seedInterruptedInstallAndOwnedSession"
adb shell am force-stop "$TARGET"
# Exercise the real Android PackageInstaller lifecycle using an offline signed APK.
BYTES="$(wc -c < "$FIXTURE" | tr -d ' ')"
CREATE="$(adb shell pm install-create -r -S "$BYTES" | tr -d '\r')"
printf '%s\n' "$CREATE" | tee "$OUT/install-create.txt"
SESSION="$(printf '%s\n' "$CREATE" | sed -nE 's/^Success: created install session \[([0-9]+)\].*/\1/p')"
[[ -n "$SESSION" ]] || { echo R2D_SESSION_CREATE_FAILED >&2; exit 1; }
trap 'adb shell pm install-abandon "$SESSION" >/dev/null 2>&1 || true' EXIT
adb shell -T pm install-write -S "$BYTES" "$SESSION" base.apk - < "$FIXTURE"   | tr -d '\r' | tee "$OUT/install-write.txt"
grep -q '^Success' "$OUT/install-write.txt" || { echo R2D_WRITE_FAILED >&2; exit 1; }
adb shell pm install-commit "$SESSION" | tr -d '\r' | tee "$OUT/install-commit.txt"
grep -q '^Success' "$OUT/install-commit.txt" || { echo R2D_COMMIT_FAILED >&2; exit 1; }
trap - EXIT
adb shell dumpsys package com.aurora.r2d.fixture > "$OUT/dumpsys.txt"
grep -m 1 -E 'versionCode=73([[:space:]]|$)' "$OUT/dumpsys.txt" \
  > "$OUT/installed-version.txt"
[[ -s "$OUT/installed-version.txt" ]] || { echo R2D_REAL_PACKAGE_MISSING >&2; exit 1; }
# Launch the normal production application outside instrumentation so AuroraApp.onCreate
# invokes the real DownloadHelper recovery on the same production Room database.
adb shell am force-stop "$TARGET"
adb shell am start -W -n "$TARGET/com.aurora.store.ComposeActivity" \
  | tr -d '\r' | tee "$OUT/production-app-restart.txt"
grep -q 'Status: ok' "$OUT/production-app-restart.txt" || {
  echo R2D_PRODUCTION_APP_START_REFUSED >&2
  exit 1
}
# Startup reconciliation is asynchronous; allow it to finish before replacing the process
# with the separate Hilt instrumentation application.
sleep 10
adb logcat -d -v time > "$OUT/production-restart-logcat.txt"
adb shell am force-stop "$TARGET"
run_case reconcile "$SUITE#reconcileRealInstallAfterForceStop"
python3 - "$OUT/R2D_INSTALL_LIFECYCLE_RECEIPT.json" "$FIXTURE" <<'PYR2D'
import hashlib, json, os, sys
from pathlib import Path
fixture = Path(sys.argv[2]); receipt = {
    'overall': 'PASS', 'source_sha': os.environ['GITHUB_SHA'],
    'run_id': os.environ['GITHUB_RUN_ID'], 'run_attempt': os.environ['GITHUB_RUN_ATTEMPT'],
    'device': 'hosted-api36-google_apis-x86_64',
    'fixture_sha256': hashlib.sha256(fixture.read_bytes()).hexdigest(),
    'fixture_version_code': 73,
    'real_package_installer_create_write_commit': True,
    'real_android_apk_installed': True,
    'persistent_production_room_dao': True,
    'owned_session_survived_process_death': True,
    'explicit_force_stop_before_recovery': True,
    'stale_callback_cas_rejected': True,
    'google_play_delivery_qualified': False,
    'microg_live_provider_qualified': False,
    'privileged_live_provider_qualified': False,
    'physical_device_qualified': False,
    'release_qualified': False,
}
Path(sys.argv[1]).write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
print('R2D_HOSTED_REAL_APK_AND_RESTART_PASS')
PYR2D
