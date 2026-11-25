#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# P02B consolidated: actual hosted API36 font setting, app process restart,
# accessibility semantics and truthful outcome display. Not a TalkBack-service
# test or OS PackageInstaller approval/denial qualification.
set -euo pipefail
[[ $# == 2 ]] || { echo R3C07_P02B_REFUSED_ARGUMENTS >&2; exit 2; }
RUNNER="$1"
OUT="$2"
PACKAGE='com.aurora.store.debug'
CLASS='com.aurora.store.data.artifact.ArtifactReviewP02BDeviceTest'
[[ -d "$OUT" && -n "$RUNNER" ]] || { echo R3C07_P02B_REFUSED_INPUTS >&2; exit 2; }
[[ "$(adb shell getprop ro.build.version.sdk | tr -d '\r')" == '36' ]] || {
  echo R3C07_P02B_REFUSED_WRONG_ANDROID_API >&2; exit 1;
}
PACKAGES="$(adb shell pm list packages --user 0 | tr -d '\r')"
[[ "$PACKAGES" == *"package:$PACKAGE"* ]] || {
  echo R3C07_P02B_REFUSED_APP_NOT_INSTALLED >&2; exit 1;
}
ORIGINAL_FONT="$(adb shell settings get system font_scale | tr -d '\r\n')"
[[ "$ORIGINAL_FONT" =~ ^([0-9]+(\.[0-9]+)?|null)$ ]] || {
  echo R3C07_P02B_REFUSED_UNKNOWN_FONT_BASELINE >&2; exit 1;
}
CHANGED=0
restore_font() {
  # Preserve the original test failure. Print RESTORE_REFUSED only if the
  # independent font cleanup actually failed; never mask the Android cause.
  local upstream_rc=$?
  trap - EXIT
  if [[ "$CHANGED" == 1 ]]; then
    local restore_failed=0
    local after=''
    if [[ "$ORIGINAL_FONT" == null ]]; then
      adb shell settings delete system font_scale >/dev/null || restore_failed=1
    else
      adb shell settings put system font_scale "$ORIGINAL_FONT" >/dev/null || restore_failed=1
    fi
    after="$(adb shell settings get system font_scale | tr -d '\r\n')" || restore_failed=1
    [[ "$after" == "$ORIGINAL_FONT" ]] || restore_failed=1
    if [[ "$restore_failed" != 0 ]]; then
      echo R3C07_P02B_REFUSED_FONT_RESTORE >&2
      exit 1
    fi
    echo R3C07_P02B_FONT_RESTORE_VERIFIED_AFTER_FAILURE >&2
  fi
  exit "$upstream_rc"
}
trap restore_font EXIT
# ADB may have changed the setting even if its command reports an error.
# Arm cleanup before the first mutating system settings command.
CHANGED=1
adb shell settings put system font_scale 2.0
DURING="$(adb shell settings get system font_scale | tr -d '\r\n')"
[[ "$DURING" == '2.0' || "$DURING" == '2' ]] || {
  echo R3C07_P02B_REFUSED_FONT_SETTING_NOT_APPLIED >&2; exit 1;
}

instrument() {
  local selector="$1" count="$2" log="$3" label="$4"
  # AndroidJUnitRunner requires FQCN#method for EACH comma-separated method.
  local -a methods=() selectors=()
  IFS=',' read -r -a methods <<< "$selector"
  local method
  for method in "${methods[@]}"; do
    [[ "$method" =~ ^[a-zA-Z_][a-zA-Z_0-9]*$ ]] || exit 2
    selectors+=("$CLASS#$method")
  done
  local full_selector
  full_selector="$(IFS=','; echo "${selectors[*]}")"
  local adb_rc tee_rc
  local -a exitcodes
  set +e
  timeout 450 adb shell am instrument -w -r -e class "$full_selector" "$RUNNER" |
    tee "$OUT/$log"
  exitcodes=("${PIPESTATUS[@]}")
  adb_rc=${exitcodes[0]}
  tee_rc=${exitcodes[1]}
  set -e
  [[ $adb_rc -eq 0 && $tee_rc -eq 0 ]] || { echo "R3C07_P02B_REFUSED_${label}_ADB" >&2; exit 1; }
  if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|Process crashed|INSTRUMENTATION_CODE: 0' "$OUT/$log"; then
    echo "R3C07_P02B_REFUSED_${label}_ANDROID" >&2; exit 1
  fi
  # AndroidJUnitRunner prints 'OK (1 test)' for one-test runs.
  # Do not accept the synthetic but invalid 'OK (1 tests)' variant.
  local noun='tests'
  if [[ "$count" == 1 ]]; then noun='test'; fi
  grep -Fxq "OK ($count $noun)" "$OUT/$log" || {
    echo "R3C07_P02B_REFUSED_${label}_COUNT" >&2; exit 1;
  }
  grep -Fxq 'INSTRUMENTATION_CODE: -1' "$OUT/$log" || {
    echo "R3C07_P02B_REFUSED_${label}_TERMINAL" >&2; exit 1;
  }
}

adb shell am force-stop "$PACKAGE"
instrument 'realSystemFontScaleChangesActivityConfigurationWithoutConsent,accessibleNodeHierarchyExposesSectionsAndSafeActions,pendingRejectionAndPresentationFailureNeverAppearAsSuccess' 3 \
  'r3c07_p02b_font_a11y_outcome.txt' 'LARGE_FONT_TESTS'
instrument 'verifiedConsentIsTransientBeforeHostForceStop' 1 \
  'r3c07_p02b_seed_consent.txt' 'SIGNED_CONSENT_SEED'
# This is a real hosted Android process force-stop, not scenario.recreate().
adb shell am force-stop "$PACKAGE"
instrument 'newProcessNeverRestoresVerifiedConsentOrSelectedBytes' 1 \
  'r3c07_p02b_reopen_after_force_stop.txt' 'PROCESS_RESTART'

# Explicit restore before sealing the receipt; EXIT trap protects all failures.
if [[ "$ORIGINAL_FONT" == null ]]; then
  adb shell settings delete system font_scale >/dev/null
else
  adb shell settings put system font_scale "$ORIGINAL_FONT"
fi
RESTORED="$(adb shell settings get system font_scale | tr -d '\r\n')"
[[ "$RESTORED" == "$ORIGINAL_FONT" ]] || {
  echo R3C07_P02B_REFUSED_FONT_RESTORE >&2; exit 1;
}
CHANGED=0
python3 -B scripts/ci/r3c07_p02b_receipt.py \
  --font-log "$OUT/r3c07_p02b_font_a11y_outcome.txt" \
  --seed-log "$OUT/r3c07_p02b_seed_consent.txt" \
  --reopen-log "$OUT/r3c07_p02b_reopen_after_force_stop.txt" \
  --font-original "$ORIGINAL_FONT" --font-changed "$DURING" \
  --font-restored "$RESTORED" \
  --output "$OUT/R3C07_P02B_API36_RECEIPT.json"
echo R3C07_P02B_API36_FONT_PROCESS_A11Y_READONLY_PASS
