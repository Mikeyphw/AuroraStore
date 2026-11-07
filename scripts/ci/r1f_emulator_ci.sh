#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
OUT="${RUNNER_TEMP:?}/aurora-r1f-emulator"
mkdir -p "$OUT"
# Invoked only by r1d2_emulator_ci.sh, after the 32 previous tests pass.
# Do not invoke that parent script here: it would recurse indefinitely.
[[ "$(adb shell getprop ro.build.version.sdk | tr -d '\r')" == '36' ]] || {
  echo 'R1F_REFUSED: emulator must be API36' >&2
  exit 1
}
TARGET='com.aurora.store.debug'
RUNNER="$(adb shell pm list instrumentation | tr -d '\r' | \
  sed -nE '/target=com\.aurora\.store\.debug\)/s/^instrumentation:([^ ]+).*/\1/p' | \
  grep 'HiltInstrumentationTestRunner' | head -n 1)"
[[ -n "$RUNNER" ]] || { echo 'R1F_REFUSED: runner absent' >&2; exit 1; }
run_suite() {
  local label="$1" selector="$2" expected="$3"
  timeout 300 adb shell am instrument -w -r -e class "$selector" "$RUNNER" \
    | tee "$OUT/${label}.txt"
  if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|INSTRUMENTATION_STATUS_CODE: -[12]' \
    "$OUT/${label}.txt"; then
    echo "R1F_TEST_FAIL: $label" >&2
    exit 1
  fi
  grep -Eq "^OK \(${expected} tests?\)" "$OUT/${label}.txt" || {
    echo "R1F_REFUSED: wrong test count in $label" >&2
    exit 1
  }
}
R1F_SUITE='com.aurora.store.compose.ui.downloads.DownloadUiDeviceTest'
run_suite ux-r1f "$R1F_SUITE" 4
for image in r1f_queued.png r1f_downloading.png r1f_failed.png; do
  adb exec-out run-as "$TARGET" cat "files/$image" > "$OUT/$image"
  if [[ ! -s "$OUT/$image" ]]; then
    echo "R1F_REFUSED: missing screenshot $image" >&2
    exit 1
  fi
done
python3 - "$OUT" <<'PYR1F'
import json, os, pathlib, sys
root = pathlib.Path(sys.argv[1])
for name in ['r1f_queued.png', 'r1f_downloading.png', 'r1f_failed.png']:
    if not (root / name).read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):
        raise SystemExit('R1F_REFUSED: invalid screenshot ' + name)
receipt = {
    'overall': 'PASS',
    'source_sha': os.getenv('GITHUB_SHA', ''),
    'run_id': os.getenv('GITHUB_RUN_ID', ''),
    'prior_device_tests': 32,
    'new_compose_device_tests': 4,
    'total_device_tests': 36,
    'real_compose_semantics': True,
    'real_emulator_screenshots': 3,
    'account_or_play_delivery_required': False,
    'physical_device_qualified': False,
    'release_qualified': False,
}
(root / 'R1F_EMULATOR_RECEIPT.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
PYR1F
echo 'R1F_API36_UX_ACCEPTANCE_PASS: 36 device tests and 3 real Compose screenshots'
