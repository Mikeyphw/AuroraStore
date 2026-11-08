#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Capture reproducible REAL-device smoke evidence only; manual download/install still required.
set -euo pipefail
if [[ $# -ne 2 || ! "$2" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'R1G_DEVICE_REFUSED: usage r1g_physical_device.sh DEVICE_SERIAL EXPECTED_SOURCE_SHA' >&2
  exit 2
fi
SERIAL="$1"
SOURCE="$2"
for tool in adb python3 sha256sum; do
  command -v "$tool" >/dev/null || { echo "R1G_DEVICE_REFUSED: missing $tool" >&2; exit 2; }
done
adb -s "$SERIAL" get-state | grep -qx device || { echo 'R1G_DEVICE_REFUSED: device offline' >&2; exit 1; }
SDK="$(adb -s "$SERIAL" shell getprop ro.build.version.sdk | tr -d '\r')"
HARDWARE="$(adb -s "$SERIAL" shell getprop ro.hardware | tr -d '\r')"
QEMU="$(adb -s "$SERIAL" shell getprop ro.kernel.qemu | tr -d '\r')"
[[ "$SDK" =~ ^[0-9]+$ ]] && (( SDK >= 26 )) || { echo 'R1G_DEVICE_REFUSED: Android SDK <26' >&2; exit 1; }
[[ "$QEMU" != 1 && ! "$HARDWARE" =~ ^(ranchu|goldfish)$ ]] || {
  echo 'R1G_DEVICE_REFUSED: this is an emulator, not a physical device' >&2
  exit 1
}
PACKAGE=com.aurora.store.debug
adb -s "$SERIAL" shell pm path "$PACKAGE" | grep -q '^package:' || {
  echo 'R1G_DEVICE_REFUSED: debug APK not installed; install an APK from the matching CI commit first' >&2
  exit 1
}
OUT="${R1G_DEVICE_OUT:-${TMPDIR:-/tmp}/aurora-r1g-device-$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$OUT"
ADB_CAPTURE="$(adb -s "$SERIAL" shell monkey -p "$PACKAGE" -c android.intent.category.LAUNCHER 1 2>&1)"
printf '%s\n' "$ADB_CAPTURE" > "$OUT/launch.txt"
grep -q 'Events injected: 1' "$OUT/launch.txt" || {
  echo 'R1G_DEVICE_REFUSED: launcher did not accept launch event' >&2; exit 1
}
adb -s "$SERIAL" exec-out screencap -p > "$OUT/physical_launch.png"
[[ -s "$OUT/physical_launch.png" ]] || { echo 'R1G_DEVICE_REFUSED: screenshot unavailable' >&2; exit 1; }
python3 - "$OUT" "$SOURCE" "$SERIAL" "$SDK" "$HARDWARE" <<'PY'
import hashlib, json, pathlib, sys
out, source, serial, sdk, hardware = sys.argv[1:]
shot = pathlib.Path(out) / 'physical_launch.png'
data = shot.read_bytes()
if len(data) < 100 or not data.startswith(b'\x89PNG\r\n\x1a\n'):
    raise SystemExit('R1G_DEVICE_REFUSED: invalid physical screenshot')
receipt = {
  'overall': 'PENDING_MANUAL',
  'source_sha_user_declared': source,
  'source_sha_verified_on_device': False,
  'device_serial': serial,
  'android_sdk': int(sdk),
  'hardware': hardware,
  'installed_package': 'com.aurora.store.debug',
  'launcher_smoke_passed': True,
  'screenshot_sha256': hashlib.sha256(data).hexdigest(),
  'real_download_tested': False,
  'cancel_resume_tested': False,
  'installer_handoff_tested': False,
  'physical_device_qualified': False,
  'release_qualified': False,
}
(pathlib.Path(out) / 'R1G_PHYSICAL_PENDING.json').write_text(json.dumps(receipt, indent=2, sort_keys=True)+'\n')
PY
printf 'R1G_DEVICE_SMOKE_CAPTURED: %s\n' "$OUT"
echo 'R1G_DEVICE_PENDING: manually test real download/cancel/retry/install and complete the checklist; NOT physical/release-qualified'
