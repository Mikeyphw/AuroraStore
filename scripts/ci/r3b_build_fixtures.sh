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
# Corrupt BOTH the v2 and v3 authenticated signing-data digests. Altering only
# v2 is not a valid negative test on API 36: a still-valid v3 signer may be
# accepted by Android. Each deliberately corrupted signer is independently
# rejected by apksigner even if the Play-provided SHA-256 is recalculated.
python3 - "$ROOT/base.apk" "$ROOT/tampered-v2-v3.apk" <<'PYR3BTAMPER'
from pathlib import Path
import struct
import sys

source, destination = map(Path, sys.argv[1:])
data = bytearray(source.read_bytes())
magic = b"APK Sig Block 42"
magic_at = data.rfind(magic)
if magic_at < 32 or magic_at + len(magic) >= len(data):
    raise SystemExit("R3B_TAMPER_REFUSED: missing APK signing block")
size = struct.unpack_from("<Q", data, magic_at - 8)[0]
start = magic_at + len(magic) - size - 8
if start < 0 or struct.unpack_from("<Q", data, start)[0] != size:
    raise SystemExit("R3B_TAMPER_REFUSED: inconsistent signing-block size")
position = start + 8
end = magic_at - 8
# Official APK Signature Scheme block IDs: v2, v3, v3.1. v3.1 is optional.
schemes = {0x7109871a: "v2", 0xf05368c0: "v3", 0x1b93ad61: "v3.1"}
mutated = set()
while position + 12 <= end:
    length = struct.unpack_from("<Q", data, position)[0]
    next_position = position + 8 + length
    if length < 4 or next_position > end:
        raise SystemExit("R3B_TAMPER_REFUSED: malformed signer ID/value pair")
    scheme_id = struct.unpack_from("<I", data, position + 8)[0]
    if scheme_id in schemes:
        # Each scheme's value begins with a length-prefixed signer sequence.
        # The first signer begins with a length-prefixed signed-data record;
        # its signed-data begins with a length-prefixed list of digests.
        value_start = position + 12
        if value_start + 20 > next_position:
            raise SystemExit("R3B_TAMPER_REFUSED: shortened signer data")
        signer_list_size = struct.unpack_from("<I", data, value_start)[0]
        signer_size = struct.unpack_from("<I", data, value_start + 4)[0]
        signed_data_size = struct.unpack_from("<I", data, value_start + 8)[0]
        signed_data_start = value_start + 12
        digest_list_size = struct.unpack_from("<I", data, signed_data_start)[0]
        record_size = struct.unpack_from("<I", data, signed_data_start + 4)[0]
        digest_size = struct.unpack_from("<I", data, signed_data_start + 12)[0]
        byte_at = signed_data_start + 16
        if (signer_list_size < 16 or signer_size < signed_data_size + 4 or
                signed_data_size < 16 or digest_list_size < 12 or
                record_size < 8 or digest_size < 16 or
                byte_at + digest_size > signed_data_start + signed_data_size or
                byte_at + digest_size > next_position):
            raise SystemExit("R3B_TAMPER_REFUSED: unexpected signer digest encoding")
        data[byte_at] ^= 1
        mutated.add(schemes[scheme_id])
    position = next_position
if not {"v2", "v3"}.issubset(mutated):
    raise SystemExit("R3B_TAMPER_REFUSED: need v2 and v3 signers for this fixture")
destination.write_bytes(data)
print("R3B_TAMPERED_V2_V3_DIGEST_FIXTURE_CREATED")
PYR3BTAMPER
if "$TOOLS/apksigner" verify --verbose "$ROOT/tampered-v2-v3.apk" \
    > "$ROOT/tampered-v2-v3-rejection.txt" 2>&1; then
  echo 'R3B_REFUSED: corrupt v2+v3 fixture incorrectly passed apksigner' >&2
  exit 1
fi
grep -Eq 'DOES NOT VERIFY|Failed to verify|does not verify' \
  "$ROOT/tampered-v2-v3-rejection.txt" || {
  echo 'R3B_REFUSED: tampered fixture rejected for an unexpected reason' >&2
  cat "$ROOT/tampered-v2-v3-rejection.txt" >&2
  exit 1
}
echo R3B_SIGNING_BLOCK_MUTATION_NEGATIVE_PASS
# Do not preserve private signing material or unsigned intermediates as artifacts.
rm -f "$ROOT"/*.keystore
sha256sum "$ROOT"/*.apk > "$ROOT/sha256sums.txt"
echo R3B_OFFLINE_SIGNED_FIXTURES_PASS
