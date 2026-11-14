#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Consolidated P13-B: actual Navigation3, isolated populated views, two viewport profiles.
# Only GitHub-hosted disposable API36 x86_64; never a personal Android device.
set -euo pipefail
: "${RUNNER_TEMP:?}" "${GITHUB_SHA:?}" "${GITHUB_RUN_ID:?}"
OUT="$RUNNER_TEMP/aurora-r4-p13b"
TARGET='com.aurora.store.debug'
INTEGRATED='com.aurora.store.compose.ui.r4.R4P13BIntegratedVisualDeviceTest'
NAVIGATION='com.aurora.store.compose.ui.r4.R4P13BProductionNav3DeviceTest'
INTEGRATED_SOURCE='app/src/androidTest/java/com/aurora/store/compose/ui/r4/R4P13BIntegratedVisualDeviceTest.kt'
NAVIGATION_SOURCE='app/src/androidTest/java/com/aurora/store/compose/ui/r4/R4P13BProductionNav3DeviceTest.kt'
mkdir -p "$OUT/logs" "$OUT/metadata"
printf '%s\n' '{"result":"NOT_RUN","p12_evidence_preserved":true,"manual_visual_approved":false,"full_upstream_visual_signoff":false,"release_qualified":false}' > "$OUT/receipt.json"
[[ "$(git rev-parse HEAD)" == "$GITHUB_SHA" && "$GITHUB_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo P13B_REFUSED_SOURCE_IDENTITY >&2; exit 1;
}
adb wait-for-device
[[ "$(adb shell getprop ro.build.version.sdk | tr -d '\r')" == 36 ]] || {
  echo P13B_REFUSED_API36 >&2; exit 1;
}
[[ "$(adb shell getprop ro.product.cpu.abi | tr -d '\r')" == x86_64 ]] || {
  echo P13B_REFUSED_X86_64 >&2; exit 1;
}
[[ "$(adb shell getprop sys.boot_completed | tr -d '\r')" == 1 ]] || {
  echo P13B_REFUSED_BOOT >&2; exit 1;
}
if adb shell pm list packages | tr -d '\r' | grep -Fxq "package:${TARGET}"; then
  echo P13B_REFUSED_PREINSTALLED_APP >&2; exit 1
fi
mapfile -d '' APP < <(find app/build/outputs/apk/vanilla/debug -maxdepth 1 -type f -name '*.apk' -print0)
mapfile -d '' TEST < <(find app/build/outputs/apk/androidTest -type f -name '*.apk' -print0)
[[ "${#APP[@]}" == 1 && "${#TEST[@]}" == 1 ]] || {
  echo P13B_REFUSED_APK_INVENTORY >&2; exit 1;
}
sha256sum "${APP[0]}" "${TEST[0]}" > "$OUT/metadata/apk-sha256.txt"
printf '%s\n' "$GITHUB_SHA" > "$OUT/metadata/source-sha.txt"
printf '%s\n' "$GITHUB_RUN_ID" > "$OUT/metadata/run-id.txt"
adb install -r "${APP[0]}" > "$OUT/logs/install-app.txt"
adb install -r "${TEST[0]}" > "$OUT/logs/install-test.txt"
RUNNER="$(adb shell pm list instrumentation | tr -d '\r' | sed -nE '/target=com\.aurora\.store\.debug\)/s/^instrumentation:([^ ]+).*/\1/p' | grep HiltInstrumentationTestRunner | head -n1)"
[[ -n "$RUNNER" ]] || { echo P13B_REFUSED_HILT_RUNNER >&2; exit 1; }
[[ "$(grep -c '^[[:space:]]*@Test[[:space:]]*$' "$INTEGRATED_SOURCE")" == 3 ]] || {
  echo P13B_REFUSED_INTEGRATED_INVENTORY >&2; exit 1;
}
[[ "$(grep -c '^[[:space:]]*@Test[[:space:]]*$' "$NAVIGATION_SOURCE")" == 2 ]] || {
  echo P13B_REFUSED_NAVIGATION_INVENTORY >&2; exit 1;
}

# Restore display modifications even on partial failure. These are disposable
# emulator-only wm overrides, not physical device actions.
restore_display() {
  adb shell wm size reset >/dev/null 2>&1 || true
  adb shell wm density reset >/dev/null 2>&1 || true
}
trap restore_display EXIT

# Verify EFFECTIVE geometry, not an "Override" label: wm may report only
# Physical size/density when the requested full profile is already native.
# The 48 PNG auditor independently checks the captured image dimensions.
effective_wm_value() {
  local kind="$1" response="$2"
  printf '%s\n' "$response" | awk -v kind="$kind" '
    { gsub(/\r/, "") }
    $0 ~ "^Physical " kind ":" {
      physical=$0; sub(/^[^:]*:[[:space:]]*/, "", physical)
    }
    $0 ~ "^Override " kind ":" {
      override=$0; sub(/^[^:]*:[[:space:]]*/, "", override)
    }
    END {
      if (override != "") print override
      else if (physical != "") print physical
    }
  '
}

verify_display() {
  local profile="$1" requested_size="$2" requested_density="$3"
  local attempts="${P13B_DISPLAY_PROBE_ATTEMPTS:-6}"
  [[ "$attempts" =~ ^[1-9][0-9]?$ ]] || {
    echo "P13B_REFUSED_PROBE_ATTEMPTS" >&2; return 1;
  }
  local readback="$OUT/metadata/${profile}-display-readback.log"
  local attempt size_raw density_raw size density
  mkdir -p "$OUT/metadata"
  : > "$readback"
  for ((attempt=1;attempt<=attempts;attempt++)); do
    # Persist raw stdout AND stderr. This distinguishes emulator startup,
    # no override (valid on native size), and actual wrong geometry.
    size_raw="$(adb shell wm size 2>&1)" || size_raw="ADB_WM_SIZE_FAILED: $size_raw"
    density_raw="$(adb shell wm density 2>&1)" || density_raw="ADB_WM_DENSITY_FAILED: $density_raw"
    size="$(effective_wm_value size "$size_raw")"
    density="$(effective_wm_value density "$density_raw")"
    printf 'attempt=%s\nrequested=%s density=%s\nwm_size=%s\nwm_density=%s\neffective=%s density=%s\n' \
      "$attempt" "$requested_size" "$requested_density" "$size_raw" "$density_raw" \
      "${size:-unknown}" "${density:-unknown}" >> "$readback"
    if [[ "$size" == "$requested_size" && "$density" == "$requested_density" ]]; then
      echo "P13B_DISPLAY_PROBE_PASS profile=$profile size=$size density=$density attempt=$attempt"
      return 0
    fi
    if ((attempt < attempts)); then sleep 1; fi
  done
  echo "P13B_REFUSED_DISPLAY_READBACK profile=$profile expected=$requested_size/$requested_density observed=${size:-unknown}/${density:-unknown} evidence=$readback" >&2
  return 1
}

run_class() {
  local profile="$1" mode="$2" label="$3" klass="$4" count="$5"
  local log="$OUT/logs/$profile/$label-$mode.txt"
  echo "P13B_RUN_BEGIN profile=$profile mode=$mode class=$klass tests=$count"
  timeout 840 adb shell am instrument -w -r -e class "$klass" "$RUNNER" | tee "$log"
  if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|shortMsg=|Process crashed|INSTRUMENTATION_STATUS_CODE: -2' "$log"; then
    echo "P13B_REFUSED_TEST_FAILURE profile=$profile mode=$mode class=$klass" >&2; exit 1
  fi
  grep -Fxq "OK ($count tests)" "$log" || {
    echo "P13B_REFUSED_TEST_COUNT profile=$profile mode=$mode actual=$(grep '^OK (' "$log" | tail -n1)" >&2; exit 1;
  }
  echo "P13B_RUN_PASS profile=$profile mode=$mode tests=$count"
}

copy_screenshot() {
  local profile="$1" mode="$2" name="$3"
  local destination="$OUT/screenshots/$profile/$mode/$name"
  adb exec-out run-as "$TARGET" cat "files/$name" > "$destination" || {
    echo "P13B_REFUSED_MISSING_SCREENSHOT $profile/$mode/$name" >&2; exit 1;
  }
  [[ -s "$destination" ]] || { echo "P13B_REFUSED_ZERO_PNG $name" >&2; exit 1; }
}

# Same emulator/ABI, two deliberately distinct display sizes/densities.
# Full reruns in both modes prove screens not merely recycled from P12.
for profile in full compact; do
  case "$profile" in
    full) width=1080; height=2400; density=420 ;;
    compact) width=720; height=1600; density=320 ;;
    *) echo P13B_REFUSED_PROFILE >&2; exit 1 ;;
  esac
  adb shell wm size "${width}x${height}"
  adb shell wm density "$density"
  verify_display "$profile" "${width}x${height}" "$density" || exit 1
  mkdir -p "$OUT/logs/$profile"
  printf '%s\n' "${width}x${height} density=$density" > "$OUT/metadata/$profile.txt"
  for mode in light dark; do
    mkdir -p "$OUT/screenshots/$profile/$mode"
    if [[ "$mode" == light ]]; then adb shell cmd uimode night no; else adb shell cmd uimode night yes; fi
    adb shell am force-stop "$TARGET" || true
    run_class "$profile" "$mode" p13b-integrated "$INTEGRATED" 3
    run_class "$profile" "$mode" p13b-nav3 "$NAVIGATION" 2
    for shot in \
      r4_p13b_home.png r4_p13b_charts.png r4_p13b_categories.png \
      r4_p13b_search.png r4_p13b_details_top.png r4_p13b_details_reviews.png \
      r4_p13b_category_selection.png r4_p13b_category_collection.png \
      r4_p13b_nav_search.png r4_p13b_nav_return.png \
      r4_p13b_nav_settings.png r4_p13b_nav_preferences.png; do
      copy_screenshot "$profile" "$mode" "$shot"
    done
    echo "P13B_SCREENSHOTS_CAPTURED profile=$profile mode=$mode count=12"
  done
done
python3 -B scripts/ci/r4_p13b_screenshot_audit.py \
  --root "$OUT" --source "$GITHUB_SHA" --run "$GITHUB_RUN_ID" --out "$OUT/receipt.json"
echo "P13B_API36_NAV3_20_TESTS_48_SCREENSHOTS_PASS source=$GITHUB_SHA run=$GITHUB_RUN_ID"
