#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# P14 P01: disposable GitHub API36 only. Never run on a physical Android device.
set -euo pipefail
: "${RUNNER_TEMP:?}" "${GITHUB_SHA:?}" "${GITHUB_RUN_ID:?}"
OUT="$RUNNER_TEMP/aurora-r4-p14-p01"
TARGET='com.aurora.store.debug'
CLASS='com.aurora.store.compose.ui.r4.R4P14OfflineNav3JourneyDeviceTest'
SOURCE='app/src/androidTest/java/com/aurora/store/compose/ui/r4/R4P14OfflineNav3JourneyDeviceTest.kt'
mkdir -p "$OUT/metadata" "$OUT/logs" "$OUT/screenshots"
printf '%s\n' '{"result":"NOT_RUN","release_qualified":false,"full_upstream_visual_signoff":false}' > "$OUT/receipt.json"
[[ "$(git rev-parse HEAD)" == "$GITHUB_SHA" && "$GITHUB_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo P14_REFUSED_SOURCE_SHA >&2;exit 1;
}
adb wait-for-device
[[ "$(adb shell getprop ro.build.version.sdk | tr -d '\r')" == 36 ]] || { echo P14_REFUSED_API >&2;exit 1; }
[[ "$(adb shell getprop ro.product.cpu.abi | tr -d '\r')" == x86_64 ]] || { echo P14_REFUSED_ABI >&2;exit 1; }
[[ "$(adb shell getprop sys.boot_completed | tr -d '\r')" == 1 ]] || { echo P14_REFUSED_BOOT >&2;exit 1; }
if adb shell pm list packages | tr -d '\r' | grep -Fxq "package:${TARGET}";then
 echo P14_REFUSED_PREINSTALLED_APP >&2;exit 1
fi
mapfile -d '' APP < <(find app/build/outputs/apk/vanilla/debug -maxdepth 1 -type f -name '*.apk' -print0)
mapfile -d '' TEST < <(find app/build/outputs/apk/androidTest -type f -name '*.apk' -print0)
[[ ${#APP[@]} == 1 && ${#TEST[@]} == 1 ]] || { echo P14_REFUSED_APK_INVENTORY >&2;exit 1; }
sha256sum "${APP[0]}" "${TEST[0]}" > "$OUT/metadata/apks-sha256.txt"
printf '%s\n' "$GITHUB_SHA" > "$OUT/metadata/source-sha.txt"
printf '%s\n' "$GITHUB_RUN_ID" > "$OUT/metadata/run-id.txt"
adb install -r "${APP[0]}" > "$OUT/logs/install-app.txt"
adb install -r "${TEST[0]}" > "$OUT/logs/install-test.txt"
RUNNER="$(adb shell pm list instrumentation | tr -d '\r' | sed -nE '/target=com\.aurora\.store\.debug\)/s/^instrumentation:([^ ]+).*/\1/p' | grep HiltInstrumentationTestRunner | head -n1)"
[[ -n "$RUNNER" ]] || { echo P14_REFUSED_RUNNER >&2;exit 1; }
[[ "$(grep -c '^[[:space:]]*@Test[[:space:]]*$' "$SOURCE")" == 4 ]] || { echo P14_REFUSED_TEST_INVENTORY >&2;exit 1; }
restore_display() { adb shell wm size reset >/dev/null 2>&1 || true;adb shell wm density reset >/dev/null 2>&1 || true; }
trap restore_display EXIT
# We reuse the P13-B proven effective readback algorithm, not "Override" text.
effective_wm() {
 local kind="$1"
 awk -v kind="$kind" '{gsub(/\r/,"")} $0 ~ "^Physical "kind":" {physical=$0;sub(/^[^:]*:[[:space:]]*/,"",physical)} $0 ~ "^Override "kind":" {override=$0;sub(/^[^:]*:[[:space:]]*/,"",override)} END {if(override!="")print override;else if(physical!="")print physical}'
}
for profile in full compact;do
 case "$profile" in full) size=1080x2400;density=420;; compact) size=720x1600;density=320;; esac
 adb shell wm size "$size";adb shell wm density "$density"
 : > "$OUT/metadata/$profile-readback.log"
 ok=false
 for attempt in 1 2 3 4 5 6;do
  raw_size="$(adb shell wm size 2>&1)" || raw_size=ADB_SIZE_FAILED
  raw_density="$(adb shell wm density 2>&1)" || raw_density=ADB_DENSITY_FAILED
  actual_size="$(printf '%s\n' "$raw_size" | effective_wm size)"
  actual_density="$(printf '%s\n' "$raw_density" | effective_wm density)"
  printf 'attempt=%s requested=%s/%s effective=%s/%s\nwm_size=%s\nwm_density=%s\n' "$attempt" "$size" "$density" "$actual_size" "$actual_density" "$raw_size" "$raw_density" >> "$OUT/metadata/$profile-readback.log"
  if [[ "$actual_size" == "$size" && "$actual_density" == "$density" ]];then ok=true;break;fi
  sleep 1
 done
 [[ "$ok" == true ]] || { echo "P14_REFUSED_DISPLAY profile=$profile" >&2;exit 1; }
 printf '%s density=%s\n' "$size" "$density" > "$OUT/metadata/$profile.txt"
 for mode in light dark;do
  mkdir -p "$OUT/logs/$profile" "$OUT/screenshots/$profile/$mode"
  if [[ "$mode" == light ]];then adb shell cmd uimode night no;else adb shell cmd uimode night yes;fi
  adb shell am force-stop "$TARGET" || true
  log="$OUT/logs/$profile/p14-$mode.txt"
  echo "P14_BEGIN profile=$profile mode=$mode tests=4"
  timeout 840 adb shell am instrument -w -r -e class "$CLASS" "$RUNNER" | tee "$log"
  if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|shortMsg=|Process crashed|INSTRUMENTATION_STATUS_CODE: -2' "$log";then
   # On a refusal, preserve the screenshots already captured by instrumentation.
   # This is a disposable GH emulator only; never a physical-device action.
   debug="$OUT/debug/$profile/$mode"
   mkdir -p "$debug"
   adb logcat -d -v time -t 2500 > "$debug/logcat.txt" 2>&1 || true
   for shot in r4_p14_search_route.png r4_p14_downloads_route.png r4_p14_settings_route.png r4_p14_preferences_route.png r4_p14_games_tab.png r4_p14_updates_tab.png \
     r4_p14_populated_search.png r4_p14_details_identity.png r4_p14_details_carousel.png r4_p14_details_reviews.png;do
    partial="$debug/$shot"
    adb exec-out run-as "$TARGET" cat "files/$shot" > "$partial" 2>/dev/null || true
    [[ -s "$partial" ]] || rm -f -- "$partial"
   done
   echo "P14_FAILURE_EVIDENCE_DIR $debug" >&2
   echo "P14_REFUSED_ANDROID_TEST_FAILURE profile=$profile mode=$mode" >&2;exit 1
  fi
  grep -Fxq 'OK (4 tests)' "$log" || { echo "P14_REFUSED_TEST_COUNT profile=$profile mode=$mode" >&2;exit 1; }
  for shot in r4_p14_search_route.png r4_p14_downloads_route.png r4_p14_settings_route.png r4_p14_preferences_route.png r4_p14_games_tab.png r4_p14_updates_tab.png \
    r4_p14_populated_search.png r4_p14_details_identity.png r4_p14_details_carousel.png r4_p14_details_reviews.png;do
   destination="$OUT/screenshots/$profile/$mode/$shot"
   adb exec-out run-as "$TARGET" cat "files/$shot" > "$destination" || { echo "P14_REFUSED_MISSING_PNG $shot" >&2;exit 1; }
   [[ -s "$destination" ]] || { echo "P14_REFUSED_ZERO_PNG $shot" >&2;exit 1; }
  done
  echo "P14_PASS profile=$profile mode=$mode tests=4 screenshots=10"
 done
done
python3 -B scripts/ci/r4_p14_p01_screenshot_audit.py --root "$OUT" --source "$GITHUB_SHA" --run "$GITHUB_RUN_ID" --out "$OUT/receipt.json"
echo "P14_P01_P02_HOSTED_16_REAL_TESTS_40_PNGS_PASS source=$GITHUB_SHA run=$GITHUB_RUN_ID"
