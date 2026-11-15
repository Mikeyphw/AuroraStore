#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# P14-P03 executes ONLY in a GitHub-hosted disposable API36 x86_64 emulator.
set -euo pipefail
: "${RUNNER_TEMP:?}" "${GITHUB_SHA:?}" "${GITHUB_RUN_ID:?}"
OUT="$RUNNER_TEMP/aurora-r4-p14-p03"
TARGET='com.aurora.store.debug'
LIFECYCLE='com.aurora.store.data.installer.R4P14P03LifecycleDeviceTest'
DOWNLOAD_UI='com.aurora.store.compose.ui.r4.R4P14P03DownloadUiDeviceTest'
FINAL_UI='com.aurora.store.compose.ui.downloads.DownloadFinalUiDeviceTest'
DAO='com.aurora.store.data.room.download.DownloadLifecycleDeviceTest'
WORKER='com.aurora.store.data.work.DownloadWorkerOfflineDeviceTest'
mkdir -p "$OUT/metadata" "$OUT/logs" "$OUT/screenshots"
printf '%s\n' '{"result":"NOT_RUN","real_installer_qualified":false,"physical_arm64_qualified":false,"release_qualified":false}' > "$OUT/receipt.json"
[[ "$(git rev-parse HEAD)" == "$GITHUB_SHA" && "$GITHUB_SHA" =~ ^[a-f0-9]{40}$ ]] || { echo P14P03_REFUSED_SOURCE_ID >&2;exit 1; }
adb wait-for-device
[[ "$(adb shell getprop ro.build.version.sdk | tr -d '\r')" == 36 ]] || { echo P14P03_REFUSED_API >&2;exit 1; }
[[ "$(adb shell getprop ro.product.cpu.abi | tr -d '\r')" == x86_64 ]] || { echo P14P03_REFUSED_ABI >&2;exit 1; }
[[ "$(adb shell getprop sys.boot_completed | tr -d '\r')" == 1 ]] || { echo P14P03_REFUSED_BOOT >&2;exit 1; }
if adb shell pm list packages | tr -d '\r' | grep -Fxq "package:${TARGET}";then echo P14P03_REFUSED_PREINSTALLED_APP >&2;exit 1;fi
mapfile -d '' APP < <(find app/build/outputs/apk/vanilla/debug -maxdepth 1 -type f -name '*.apk' -print0)
mapfile -d '' TEST < <(find app/build/outputs/apk/androidTest -type f -name '*.apk' -print0)
[[ ${#APP[@]} == 1 && ${#TEST[@]} == 1 ]] || { echo P14P03_REFUSED_APK_PAIR >&2;exit 1; }
sha256sum "${APP[0]}" "${TEST[0]}" > "$OUT/metadata/apk-sha256.txt"
printf '%s\n' "$GITHUB_SHA" > "$OUT/metadata/source-sha.txt"
printf '%s\n' "$GITHUB_RUN_ID" > "$OUT/metadata/run-id.txt"
adb install -r "${APP[0]}" > "$OUT/logs/install-app.txt"
adb install -r "${TEST[0]}" > "$OUT/logs/install-test.txt"
RUNNER="$(adb shell pm list instrumentation | tr -d '\r' | sed -nE '/target=com\.aurora\.store\.debug\)/s/^instrumentation:([^ ]+).*/\1/p' | grep HiltInstrumentationTestRunner | head -n1)"
[[ -n "$RUNNER" ]] || { echo P14P03_REFUSED_INSTRUMENTATION_RUNNER >&2;exit 1; }
restore_display() { adb shell wm size reset >/dev/null 2>&1 || true; adb shell wm density reset >/dev/null 2>&1 || true; }
trap restore_display EXIT
# Retain collected evidence even after an Android instrumentation failure.
collect_failed() {
 local profile="$1" mode="$2"
 mkdir -p "$OUT/logs/$profile" "$OUT/screenshots/$profile/$mode"
 adb logcat -d -t 1500 > "$OUT/logs/$profile/p14p03-logcat-$mode.txt" 2>&1 || true
 for shot in r4_p14p03_queued.png r4_p14p03_downloading.png r4_p14p03_failed.png r1g_awaiting_retry.png r1g_cancelled.png;do
  adb exec-out run-as "$TARGET" cat "files/$shot" > "$OUT/screenshots/$profile/$mode/$shot" 2>/dev/null || rm -f "$OUT/screenshots/$profile/$mode/$shot"
 done
}
run_class() {
 local profile="$1" mode="$2" label="$3" klass="$4" count="$5"
 local log="$OUT/logs/$profile/$label-$mode.txt"
 local expected="OK ($count tests)"
 if (( count == 1 )); then expected='OK (1 test)'; fi
 echo "P14P03_TEST_BEGIN profile=$profile mode=$mode label=$label tests=$count"
 timeout 840 adb shell am instrument -w -r -e class "$klass" "$RUNNER" | tee "$log"
 if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|shortMsg=|Process crashed|INSTRUMENTATION_STATUS_CODE: -2' "$log" || ! grep -Fxq "$expected" "$log" || ! grep -Fxq 'INSTRUMENTATION_CODE: -1' "$log";then
  collect_failed "$profile" "$mode"
  echo "P14P03_REFUSED_ANDROID_FAILURE profile=$profile mode=$mode suite=$label expected=\"$expected\" observed=\"$(grep -E '^OK \(' "$log" | tail -n 1 || true)\"" >&2
  exit 1
 fi
 echo "P14P03_TEST_PASS profile=$profile mode=$mode label=$label count=$count"
}
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
  printf 'attempt=%s requested=%s/%s effective=%s/%s\n' "$attempt" "$size" "$density" "$actual_size" "$actual_density" >> "$OUT/metadata/$profile-readback.log"
  if [[ "$actual_size" == "$size" && "$actual_density" == "$density" ]];then ok=true;break;fi
  sleep 1
 done
 [[ "$ok" == true ]] || { echo "P14P03_REFUSED_DISPLAY profile=$profile" >&2;exit 1; }
 printf '%s density=%s\n' "$size" "$density" > "$OUT/metadata/$profile.txt"
 for mode in light dark;do
  mkdir -p "$OUT/logs/$profile" "$OUT/screenshots/$profile/$mode"
 if [[ "$mode" == light ]];then adb shell cmd uimode night no;else adb shell cmd uimode night yes;fi
 adb shell am force-stop "$TARGET" || true
 run_class "$profile" "$mode" lifecycle "$LIFECYCLE" 8
 run_class "$profile" "$mode" download-ui "$DOWNLOAD_UI" 4
 run_class "$profile" "$mode" final-ui "$FINAL_UI" 4
 for shot in r4_p14p03_queued.png r4_p14p03_downloading.png r4_p14p03_failed.png r1g_awaiting_retry.png r1g_cancelled.png;do
  file="$OUT/screenshots/$profile/$mode/$shot"
  adb exec-out run-as "$TARGET" cat "files/$shot" > "$file" || { echo "P14P03_REFUSED_MISSING_SCREENSHOT $shot" >&2;exit 1; }
  [[ -s "$file" ]] || { echo "P14P03_REFUSED_ZERO_SCREENSHOT $shot" >&2;exit 1; }
 done
 echo "P14P03_PROFILE_PASS profile=$profile mode=$mode tests=16 screenshots=5"
 # Additional production DAO and worker regressions only once, without duplicating app state.
 if [[ "$profile" == full && "$mode" == light ]];then
  run_class "$profile" "$mode" baseline-dao "$DAO" 9
  for method in truncatedResponseRetriesThenResumesSameAttemptExactly \
                shaMismatchRejectsPayloadWithoutInstallHandoff \
                cancelledAttemptIsNotResurrectedOrDownloaded;do
   run_class "$profile" "$mode" "worker-$method" "$WORKER#$method" 1
  done
 fi
 done
done
python3 -B scripts/ci/r4_p14_p03_evidence_audit.py --root "$OUT" --source "$GITHUB_SHA" --run "$GITHUB_RUN_ID" --out "$OUT/receipt.json"
echo "P14P03_HOSTED_76_TESTS_20_PNGS_PASS source=$GITHUB_SHA run=$GITHUB_RUN_ID"
