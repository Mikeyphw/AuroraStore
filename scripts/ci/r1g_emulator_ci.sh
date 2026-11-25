#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Called by r1d2_emulator_ci.sh after all 36 R1D-R1F cases and their receipts.
set -euo pipefail
OUT="${RUNNER_TEMP:?}/aurora-r1g-emulator"
mkdir -p "$OUT"
printf '%s\n' '{"overall":"NOT_RUN","physical_device_qualified":false,"release_qualified":false}' > "$OUT/R1G_QUALIFICATION_RECEIPT.json"
[[ "$(adb shell getprop ro.build.version.sdk | tr -d '\r')" == '36' ]] || {
  echo 'R1G_REFUSED: emulator must be API36' >&2
  exit 1
}
RUNNER="$(adb shell pm list instrumentation | tr -d '\r' | \
  sed -nE '/target=com\.aurora\.store\.debug\)/s/^instrumentation:([^ ]+).*/\1/p' | \
  grep 'HiltInstrumentationTestRunner' | head -n 1)"
[[ -n "$RUNNER" ]] || { echo 'R1G_REFUSED: Hilt runner missing' >&2; exit 1; }
SUITE='com.aurora.store.compose.ui.downloads.DownloadFinalUiDeviceTest'
timeout 300 adb shell am instrument -w -r -e class "$SUITE" "$RUNNER" | tee "$OUT/r1g-ui.txt"
if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|INSTRUMENTATION_STATUS_CODE: -[12]' "$OUT/r1g-ui.txt"; then
  echo 'R1G_TEST_FAIL: final Compose tests' >&2
  exit 1
fi
grep -Eq '^OK \(4 tests\)' "$OUT/r1g-ui.txt" || {
  echo 'R1G_REFUSED: expected four successful Compose tests' >&2
  exit 1
}
for name in r1g_awaiting_retry.png r1g_cancelled.png; do
  adb exec-out run-as com.aurora.store.debug cat "files/$name" > "$OUT/$name"
  [[ -s "$OUT/$name" ]] || { echo "R1G_REFUSED: screenshot $name absent" >&2; exit 1; }
done
python3 -B scripts/ci/r1g_evidence_gate.py "$RUNNER_TEMP"
echo 'R1G_EMULATOR_QUALIFICATION_PASS: 40 device tests and 5 evidence screenshots; no physical/release claim'
