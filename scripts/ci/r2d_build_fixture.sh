#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
[[ -n "${ANDROID_SDK_ROOT:-}" ]] || { echo R2D_SDK_REQUIRED >&2; exit 1; }
[[ -n "${RUNNER_TEMP:-}" ]] || { echo R2D_RUNNER_TEMP_REQUIRED >&2; exit 1; }
PLATFORM="$ANDROID_SDK_ROOT/platforms/android-37.0/android.jar"
[[ -f "$PLATFORM" ]] || { echo R2D_PLATFORM_REQUIRED >&2; exit 1; }
mapfile -t BUILDTOOLS < <(find "$ANDROID_SDK_ROOT/build-tools" -maxdepth 1 -mindepth 1 -type d | sort -V)
(( ${#BUILDTOOLS[@]} )) || { echo R2D_BUILD_TOOLS_REQUIRED >&2; exit 1; }
TOOLS="${BUILDTOOLS[-1]}"
OUT="$RUNNER_TEMP/aurora-r2d-emulator"
mkdir -p "$OUT"
"$TOOLS/aapt2" link -I "$PLATFORM"   --manifest scripts/ci/fixture_r2d/AndroidManifest.xml   -o "$OUT/r2d-fixture-unsigned.apk"
keytool -genkeypair -noprompt -keystore "$OUT/r2d-fixture.keystore"   -alias r2d -keyalg RSA -keysize 2048 -validity 1   -dname 'CN=Aurora R2D Ephemeral Fixture'   -storepass r2d-fixture-password -keypass r2d-fixture-password >/dev/null 2>&1
"$TOOLS/apksigner" sign   --ks "$OUT/r2d-fixture.keystore" --ks-key-alias r2d   --ks-pass pass:r2d-fixture-password --key-pass pass:r2d-fixture-password   --out "$OUT/r2d-fixture.apk" "$OUT/r2d-fixture-unsigned.apk"
"$TOOLS/apksigner" verify "$OUT/r2d-fixture.apk"
# The CI signing key exists only to sign this throwaway fixture. Do not upload it.
rm -f "$OUT/r2d-fixture.keystore" "$OUT/r2d-fixture-unsigned.apk"
[[ -s "$OUT/r2d-fixture.apk" ]] || { echo R2D_FIXTURE_EMPTY >&2; exit 1; }
sha256sum "$OUT/r2d-fixture.apk" > "$OUT/r2d-fixture.sha256"
echo R2D_FIXTURE_SIGNED_AND_VERIFIED
