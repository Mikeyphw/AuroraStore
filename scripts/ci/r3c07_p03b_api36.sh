#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# R3C07 P03B real API36 read-only UI and screenshots. Never installs/browses.
set -euo pipefail
[[ $# == 2 ]] || { echo R3C07_P03B_REFUSED_ARGS >&2; exit 2; }
RUNNER="$1"
OUT="$2"
CLASS='com.aurora.store.data.artifact.ArtifactImportJourneyP03BDeviceTest'
PACKAGE='com.aurora.store.debug'
[[ -d "$OUT" && -n "$RUNNER" ]] || exit 2
[[ "$(adb shell getprop ro.build.version.sdk | tr -d '\r')" == '36' ]] || {
  echo R3C07_P03B_REFUSED_NOT_API36 >&2; exit 2;
}
[[ "$(adb shell pm list packages --user 0 | tr -d '\r')" == *"package:$PACKAGE"* ]] || {
  echo R3C07_P03B_REFUSED_APP_MISSING >&2; exit 2;
}
# Remove dedicated old test captures before instrumentation. This guarantees
# uploaded PNGs were freshly written by the current five-test hosted run.
# No user documents, APKs or independent evidence are touched.
for name in r3c07_p03b_provider_choice.png r3c07_p03b_failed_retry.png r3c07_p03b_signed_review.png; do
  adb shell run-as "$PACKAGE" rm -f "files/$name" || {
    echo R3C07_P03B_REFUSED_STALE_SCREENSHOT_CLEANUP >&2; exit 1;
  }
done
# List every FQCN#method; AndroidJUnitRunner rejects bare names after commas.
SELECTORS="$CLASS#explicitProviderChoiceAndRefusalNeverAutoNavigatesOrInstalls,$CLASS#invalidDocumentGetsSafeManualRetryAndFreshSignedReview,$CLASS#requestedVersionMismatchBlocksRealSignedFileConsent,$CLASS#userSourceChangeAndActivityRecreateDiscardAllOldConsent,$CLASS#realLandscapeConfigurationAndLargeTextRetainSafeActions"
set +e
timeout 520 adb shell am instrument -w -r -e class "$SELECTORS" "$RUNNER" | tee "$OUT/r3c07_p03b_real_ui.txt"
codes=("${PIPESTATUS[@]}")
set -e
[[ "${codes[0]}" == 0 && "${codes[1]}" == 0 ]] || {
  echo R3C07_P03B_REFUSED_INSTRUMENTATION >&2; exit 1;
}
log="$OUT/r3c07_p03b_real_ui.txt"
if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|Process crashed|INSTRUMENTATION_CODE: 0' "$log"; then
  echo R3C07_P03B_REFUSED_REAL_TESTS >&2; exit 1
fi
grep -Fxq 'OK (5 tests)' "$log" || { echo R3C07_P03B_REFUSED_TEST_COUNT >&2; exit 1; }
grep -Fxq 'INSTRUMENTATION_CODE: -1' "$log" || { echo R3C07_P03B_REFUSED_OS_TERMINAL >&2; exit 1; }
# Read screenshots from the actual debuggable target's private file directory.
# No screen capture is synthesized or accepted from checked-in fixture data.
for name in r3c07_p03b_provider_choice.png r3c07_p03b_failed_retry.png r3c07_p03b_signed_review.png; do
  adb exec-out run-as "$PACKAGE" cat "files/$name" > "$OUT/$name" || {
    echo R3C07_P03B_REFUSED_PRIVATE_SCREENSHOT >&2; exit 1;
  }
done
python3 -B scripts/ci/r3c07_p03b_receipt.py \
  --log "$log" \
  --choice "$OUT/r3c07_p03b_provider_choice.png" \
  --retry "$OUT/r3c07_p03b_failed_retry.png" \
  --review "$OUT/r3c07_p03b_signed_review.png" \
  --sha "${GITHUB_SHA:?}" --run-id "${GITHUB_RUN_ID:?}" \
  --output "$OUT/R3C07_P03B_API36_REAL_UI_RECEIPT.json"
echo R3C07_P03B_REAL_API36_FIVE_UI_TESTS_THREE_SCREENSHOTS_PASS
