#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# HF07: emulator-runner invokes its `script` via /bin/sh -c per command.
# Keep the entire bootstrap as ONE shell action, with all guards in this file.
# No install, instrumentation, privileged changes, or app data writes here.
set -euo pipefail

api="$(adb shell getprop ro.build.version.sdk | tr -d '\r')"
if [[ "$api" != '36' ]]; then
  echo 'R3C07_HF07_AVD_REFUSED_NOT_API36' >&2
  exit 1
fi

# A populated user-0 inventory is required; an empty or failed query is never
# evidence of a clean emulator, and package checks must match the entire name.
inventory="$(adb shell pm list packages --user 0 | tr -d '\r')"
if [[ -z "$inventory" || "$inventory" != *'package:'* ]]; then
  echo 'R3C07_HF07_AVD_REFUSED_INVENTORY_UNAVAILABLE' >&2
  exit 1
fi
if printf '%s\n' "$inventory" | grep -Eq '^package:com\.aurora\.store\.debug(\.test)?$'; then
  echo 'R3C07_HF03_AVD_REFUSED_NOT_CLEAN' >&2
  exit 1
fi
printf '%s\n' 'R3C07_HF03_PREINSTALL_AVD_SNAPSHOT_INITIALIZED'
