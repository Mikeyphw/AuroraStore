#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Source-only R4 qualification. Only a fresh GitHub-hosted API36 x86_64 emulator.
set -euo pipefail

: "${RUNNER_TEMP:?}"
: "${GITHUB_SHA:?}"
: "${GITHUB_RUN_ID:?}"
OUT="$RUNNER_TEMP/aurora-r4-p05"
TARGET='com.aurora.store.debug'
mkdir -p "$OUT/screenshots/light" "$OUT/screenshots/dark" "$OUT/logs" "$OUT/metadata"

printf '%s\n' '{"result":"NOT_RUN","emulator_qualified":false,"release_qualified":false,"physical_arm64_qualified":false,"visual_manual_approved":false}' > "$OUT/receipt.json"

[[ "$(git rev-parse HEAD)" == "$GITHUB_SHA" ]] || { echo R4_P05_REFUSED_WRONG_SOURCE >&2; exit 1; }
[[ "$GITHUB_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo R4_P05_REFUSED_BAD_SHA >&2; exit 1; }
adb wait-for-device
[[ "$(adb shell getprop ro.build.version.sdk | tr -d '\r')" == '36' ]] || { echo R4_P05_REFUSED_NOT_API36 >&2; exit 1; }
[[ "$(adb shell getprop ro.product.cpu.abi | tr -d '\r')" == 'x86_64' ]] || { echo R4_P05_REFUSED_NOT_X86_64 >&2; exit 1; }
[[ "$(adb shell getprop sys.boot_completed | tr -d '\r')" == '1' ]] || { echo R4_P05_REFUSED_NOT_BOOTED >&2; exit 1; }

# The emulator must be a fresh, disposable device, with neither APK preinstalled.
if adb shell pm list packages | tr -d '\r' | grep -F "package:${TARGET}"; then
    echo R4_P05_REFUSED_PREEXISTING_AURORA >&2
    exit 1
fi

mapfile -d '' APP < <(find app/build/outputs/apk/vanilla/debug -maxdepth 1 -type f -name '*.apk' -print0)
mapfile -d '' TEST < <(find app/build/outputs/apk/androidTest -type f -name '*.apk' -print0)
[[ "${#APP[@]}" -eq 1 && "${#TEST[@]}" -eq 1 ]] || { echo R4_P05_REFUSED_APK_COUNT >&2; exit 1; }
sha256sum "${APP[0]}" "${TEST[0]}" > "$OUT/metadata/apk-sha256.txt"
printf '%s\n' "$GITHUB_SHA" > "$OUT/metadata/source-sha.txt"
printf '%s\n' "$GITHUB_RUN_ID" > "$OUT/metadata/run-id.txt"
adb install -r "${APP[0]}" | tee "$OUT/logs/install-app.txt"
adb install -r "${TEST[0]}" | tee "$OUT/logs/install-test.txt"

RUNNER="$(adb shell pm list instrumentation | tr -d '\r' | sed -nE '/target=com\.aurora\.store\.debug\)/s/^instrumentation:([^ ]+).*/\1/p' | grep 'HiltInstrumentationTestRunner' | head -n1)"
[[ -n "$RUNNER" ]] || { echo R4_P05_REFUSED_MISSING_INSTRUMENTATION_RUNNER >&2; exit 1; }

run_suite() {
    local label="$1" klass="$2" source="$3" expected="$4"
    local log="$OUT/logs/$label.txt"
    [[ -s "$source" ]] || { echo "R4_P05_REFUSED_SOURCE_MISSING $source" >&2; exit 1; }
    local count
    count="$(grep -c '^[[:space:]]*@Test[[:space:]]*$' "$source")"
    [[ "$count" == "$expected" && "$count" -gt 0 ]] || {
        echo "R4_P05_REFUSED_TEST_INVENTORY $label expected=$expected actual=$count" >&2
        exit 1
    }
    echo "R4_P05_REAL_ANDROID_START $label count=$count"
    timeout 840 adb shell am instrument -w -r -e class "$klass" "$RUNNER" | tee "$log"
    if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|shortMsg=|Process crashed|INSTRUMENTATION_STATUS_CODE: -2' "$log"; then
        echo "R4_P05_REAL_ANDROID_FAIL $label" >&2
        exit 1
    fi
    local suffix="tests"
    [[ "$expected" == '1' ]] && suffix="test"
    grep -Fxq "OK ($expected $suffix)" "$log" || {
        echo "R4_P05_REFUSED_TEST_COUNT $label: $(grep '^OK (' "$log" | tail -n 1)" >&2
        exit 1
    }
    echo "R4_P05_REAL_ANDROID_PASS $label count=$count"
}

# Real Room DAO generation/attempt guards, real loopback worker, and real UI state/cancel sheet.
run_suite 'download-dao-cancellation' \
  'com.aurora.store.data.room.download.DownloadLifecycleDeviceTest' \
  'app/src/androidTest/java/com/aurora/store/data/room/download/DownloadLifecycleDeviceTest.kt' 9
run_suite 'real-offline-worker' \
  'com.aurora.store.data.work.DownloadWorkerOfflineDeviceTest' \
  'app/src/androidTest/java/com/aurora/store/data/work/DownloadWorkerOfflineDeviceTest.kt' 8
run_suite 'download-ui-cancellation' \
  'com.aurora.store.compose.ui.downloads.DownloadFinalUiDeviceTest' \
  'app/src/androidTest/java/com/aurora/store/compose/ui/downloads/DownloadFinalUiDeviceTest.kt' 4
# Real isolated Android preference tests with synthetic credentials only.
# Original auth preferences are restored after every test; no Play login.
run_suite 'r4-offline-account-session' \
  'com.aurora.store.data.providers.R4OfflineAccountSessionDeviceTest' \
  'app/src/androidTest/java/com/aurora/store/data/providers/R4OfflineAccountSessionDeviceTest.kt' 9

# UI snapshots run on the actual emulator in both system light and dark modes.
# No external app downloads or authentication are attempted.
UI_CLASS='com.aurora.store.compose.ui.r4.R4ExpressiveDeviceTest'
UI_SOURCE='app/src/androidTest/java/com/aurora/store/compose/ui/r4/R4ExpressiveDeviceTest.kt'
for mode in light dark; do
    if [[ "$mode" == 'light' ]]; then adb shell cmd uimode night no; else adb shell cmd uimode night yes; fi
    adb shell am force-stop "$TARGET" || true
    run_suite "r4-expressive-$mode" "$UI_CLASS" "$UI_SOURCE" 5
    ACTIVITY_CLASS='com.aurora.store.compose.ui.r4.R4ActivityNavigationDeviceTest'
    ACTIVITY_SOURCE='app/src/androidTest/java/com/aurora/store/compose/ui/r4/R4ActivityNavigationDeviceTest.kt'
    run_suite "r4-activity-$mode" "$ACTIVITY_CLASS" "$ACTIVITY_SOURCE" 6
    for screenshot in \
        r4_update_downloading.png r4_update_idle.png r4_update_verifying.png \
        r4_update_installing.png r4_expressive_menu.png \
        r4_activity_settings.png r4_activity_ui_preferences.png \
        r4_activity_more_sheet.png r4_activity_main.png r4_activity_search.png \
        r4_activity_downloads.png r4_activity_updates.png; do
        # A debug-only run-as copy keeps evidence private, not written to shared storage.
        adb exec-out run-as "$TARGET" cat "files/$screenshot" > "$OUT/screenshots/$mode/$screenshot" || {
            echo "R4_P05_REFUSED_SCREENSHOT_MISSING $mode/$screenshot" >&2
            exit 1
        }
    done
    echo "R4_P05_SCREENSHOTS_CAPTURED mode=$mode"
done

# Keep an independent cold-launch onboarding reference. Actual production Nav3
# Main/Search/Downloads/Settings/Updates capture happens in the Hilt test suite above.
adb shell am force-stop "$TARGET" || true
adb shell cmd uimode night no
adb shell am start -W -n "$TARGET/com.aurora.store.ComposeActivity" | tee "$OUT/logs/real-launch.txt"
adb exec-out screencap -p > "$OUT/screenshots/light/r4_real_app_launch.png"
adb shell am force-stop "$TARGET" || true

python3 -B scripts/ci/r4_p05_screenshot_audit.py \
    --root "$OUT" --source "$GITHUB_SHA" --run "$GITHUB_RUN_ID" \
    --out "$OUT/receipt.json"

echo "R4_P05_API36_REAL_EMULATOR_ACCEPTANCE_PASS $GITHUB_SHA run=$GITHUB_RUN_ID"
