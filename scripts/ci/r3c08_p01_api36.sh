#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# API36 READ ONLY: actual platform URI-grant revocation, then importer rejection.
set -euo pipefail
[[ "$#" == 2 ]] || { echo R3C08_P01_REFUSED_ARGS >&2; exit 2; }
RUNNER="$1"
OUT="$2"
CLASS='com.aurora.store.data.artifact.ArtifactR3C08P01DeviceTest'
[[ -d "$OUT" && -n "$RUNNER" ]] || { echo R3C08_P01_REFUSED_INPUT >&2; exit 2; }
[[ "$(adb shell getprop ro.build.version.sdk | tr -d '\r')" == 36 ]] || {
  echo R3C08_P01_REFUSED_NOT_API36 >&2; exit 2;
}
SELECTORS="$CLASS#realAndroidUriGrantAndRevocationRejectFreshOpens,$CLASS#revokedDocumentIsRefusedByProductionImportWithoutConsent,$CLASS#cancellingVerifiedSignedFileDiscardsSelectionAndAllConsent"
set +e
timeout 480 adb shell am instrument -w -r -e class "$SELECTORS" "$RUNNER" | tee "$OUT/r3c08_p01_revoked_saf.txt"
status=("${PIPESTATUS[@]}")
set -e
[[ "${status[0]}" == 0 && "${status[1]}" == 0 ]] || {
  echo R3C08_P01_REFUSED_INSTRUMENTATION >&2; exit 1;
}
log="$OUT/r3c08_p01_revoked_saf.txt"
if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|Process crashed|INSTRUMENTATION_CODE: 0' "$log"; then
  echo R3C08_P01_REFUSED_REAL_TESTS >&2; exit 1
fi
grep -Fxq 'OK (3 tests)' "$log" || { echo R3C08_P01_REFUSED_TEST_COUNT >&2; exit 1; }
grep -Fxq 'INSTRUMENTATION_CODE: -1' "$log" || { echo R3C08_P01_REFUSED_ANDROID_TERMINAL >&2; exit 1; }
python3 -B scripts/ci/r3c08_p01_receipt.py --log "$log" --sha "$GITHUB_SHA" \
  --run-id "$GITHUB_RUN_ID" --output "$OUT/R3C08_P01_API36_REVOCATION_RECEIPT.json"
echo R3C08_P01_API36_REAL_URI_GRANT_REVOKE_READ_ONLY_PASS
