#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
ROOT="${RUNNER_TEMP:?}/aurora-r2d-emulator/r3b"
mkdir -p "$ROOT"
# Upload-artifact runs even when CI fails; never leave temporary signing keys behind.
cleanup() {
  rm -f "$ROOT"/*.keystore "$ROOT"/*-unsigned.apk "$ROOT"/*-manifest.xml
}
trap cleanup EXIT
SDK="${ANDROID_SDK_ROOT:?}"
PLATFORM="$SDK/platforms/android-37.0/android.jar"
mapfile -t BINS < <(find "$SDK/build-tools" -maxdepth 1 -mindepth 1 -type d | sort -V)
TOOLS="${BINS[-1]:?}"
test -f "$PLATFORM"
for key in main other; do
  keytool -genkeypair -noprompt -keystore "$ROOT/$key.keystore" \
    -alias "$key" -keyalg RSA -keysize 2048 -validity 1 \
    -dname "CN=Aurora R3B Offline $key" \
    -storepass r3b-fixture-password -keypass r3b-fixture-password >/dev/null 2>&1
done
fixture() {
  local name="$1" pkg="$2" version="$3" signer="$4" split="${5:-}"
  local split_attr=""
  [[ -z "$split" ]] || split_attr=" split=\"$split\""
  cat > "$ROOT/$name-manifest.xml" <<XML
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="$pkg" android:versionCode="$version" android:versionName="$version"$split_attr>
    <uses-sdk android:minSdkVersion="23" android:targetSdkVersion="35" />
    <application android:label="R3B Offline Fixture" android:hasCode="false" />
</manifest>
XML
  "$TOOLS/aapt2" link -I "$PLATFORM" --manifest "$ROOT/$name-manifest.xml" \
    -o "$ROOT/$name-unsigned.apk"
  "$TOOLS/apksigner" sign --ks "$ROOT/$signer.keystore" --ks-key-alias "$signer" \
    --ks-pass pass:r3b-fixture-password --key-pass pass:r3b-fixture-password \
    --out "$ROOT/$name.apk" "$ROOT/$name-unsigned.apk"
  "$TOOLS/apksigner" verify --verbose "$ROOT/$name.apk"
  rm "$ROOT/$name-unsigned.apk" "$ROOT/$name-manifest.xml"
}
fixture base com.aurora.r3b.fixture 73 main
fixture older com.aurora.r3b.fixture 72 main
fixture newer com.aurora.r3b.fixture 74 main
fixture other-package com.aurora.r3b.other 73 main
fixture other-signer com.aurora.r3b.fixture 73 other
fixture matching-split com.aurora.r3b.fixture 73 main config.en
fixture other-signer-split com.aurora.r3b.fixture 73 other config.en
# Do not preserve private signing material or unsigned intermediates as artifacts.
rm -f "$ROOT"/*.keystore
sha256sum "$ROOT"/*.apk > "$ROOT/sha256sums.txt"
echo R3B_OFFLINE_SIGNED_FIXTURES_PASS
