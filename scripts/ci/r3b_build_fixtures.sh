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
# Create a NEGATIVE fixture by changing a digest byte *inside* the authenticated
# APK Signature Scheme v2 signed-data region, not an unrelated ID/value pair.
# A checksum over these tampered bytes is still well-formed; cryptographic
# verification must reject it even when the checksum is updated to match.
python3 - "$ROOT/base.apk" "$ROOT/tampered-v2.apk" <<'PYR3BTAMPER'
from pathlib import Path
import struct
import sys

source, destination = map(Path, sys.argv[1:])
data = bytearray(source.read_bytes())
magic = b"APK Sig Block 42"
magic_at = data.rfind(magic)
if magic_at < 32 or magic_at + len(magic) >= len(data):
    raise SystemExit("R3B_TAMPER_REFUSED: missing v2 signing block")
size = struct.unpack_from("<Q", data, magic_at - 8)[0]
start = magic_at + len(magic) - size - 8
if start < 0 or struct.unpack_from("<Q", data, start)[0] != size:
    raise SystemExit("R3B_TAMPER_REFUSED: inconsistent signing-block size")
position = start + 8
end = magic_at - 8
changed = False
while position + 12 <= end:
    length = struct.unpack_from("<Q", data, position)[0]
    next_position = position + 8 + length
    if length < 4 or next_position > end:
        raise SystemExit("R3B_TAMPER_REFUSED: malformed signer ID/value pair")
    scheme_id = struct.unpack_from("<I", data, position + 8)[0]
    if scheme_id == 0x7109871a:
        value_start = position + 12
        signer_list_size = struct.unpack_from("<I", data, value_start)[0]
        signer_size = struct.unpack_from("<I", data, value_start + 4)[0]
        signed_data_start = value_start + 12
        signed_data_size = struct.unpack_from("<I", data, value_start + 8)[0]
        # The first signer has a length-prefixed digest list. Its first digest
        # contains [record_size, algorithm_id, digest_size, actual_digest].
        digest_list_size = struct.unpack_from("<I", data, signed_data_start)[0]
        record_size = struct.unpack_from("<I", data, signed_data_start + 4)[0]
        digest_size = struct.unpack_from("<I", data, signed_data_start + 12)[0]
        byte_at = signed_data_start + 16
        if (signer_list_size < 16 or signer_size < signed_data_size + 4 or
                digest_list_size < 12 or record_size < 8 or digest_size < 16 or
                byte_at + digest_size > signed_data_start + signed_data_size or
                byte_at + digest_size > next_position):
            raise SystemExit("R3B_TAMPER_REFUSED: unexpected v2 signer encoding")
        data[byte_at] ^= 1
        changed = True
        break
    position = next_position
if not changed:
    raise SystemExit("R3B_TAMPER_REFUSED: no v2 signature scheme record")
destination.write_bytes(data)
print("R3B_TAMPERED_V2_DIGEST_FIXTURE_CREATED")
PYR3BTAMPER
if "$TOOLS/apksigner" verify --verbose "$ROOT/tampered-v2.apk"     > "$ROOT/tampered-v2-rejection.txt" 2>&1; then
  echo 'R3B_REFUSED: corrupt v2 fixture incorrectly passed apksigner' >&2
  exit 1
fi
grep -Eq 'DOES NOT VERIFY|Failed to verify|does not verify'   "$ROOT/tampered-v2-rejection.txt" || {
  echo 'R3B_REFUSED: tampered fixture rejected for an unexpected reason' >&2
  cat "$ROOT/tampered-v2-rejection.txt" >&2
  exit 1
}
echo R3B_SIGNING_BLOCK_MUTATION_NEGATIVE_PASS
# Do not preserve private signing material or unsigned intermediates as artifacts.
rm -f "$ROOT"/*.keystore
sha256sum "$ROOT"/*.apk > "$ROOT/sha256sums.txt"
echo R3B_OFFLINE_SIGNED_FIXTURES_PASS
