#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# R3C08 P02-P04 API36: twenty-one real read-only Android tests.
# A single narrowly scoped early AndroidJUnitRunner infrastructure crash can
# trigger one fresh complete attempt. Never accept an incomplete test run.
set -euo pipefail
[[ "$#" == 2 ]] || { echo R3C08_P02_P04_REFUSED_ARGS >&2; exit 2; }
RUNNER="$1"; OUT="$2"
[[ -n "$RUNNER" && -d "$OUT" ]] || { echo R3C08_P02_P04_REFUSED_INPUT >&2; exit 2; }
[[ "$(adb shell getprop ro.build.version.sdk | tr -d '\r')" == 36 ]] || {
  echo R3C08_P02_P04_REFUSED_NOT_API36 >&2; exit 2;
}
CLASS='com.aurora.store.data.artifact.ArtifactR3C08AdversarialDeviceTest'
SELECTORS="$CLASS#p02_cancelledLeaseRejectsNewStreamAndClosesOwnedInput,$CLASS#p02_preCancelledPrivateStagingCleansNewDirectory,$CLASS#p02_providerOpenFailureCleansPrivateStageAndDisablesInstall,$CLASS#p02_remoteProviderDeathRefusesImportAndRestartsInNewProcess,$CLASS#p02_failedProviderRetryResetsAllApprovalsAndCleansCache,$CLASS#p03_traversalZipRejectedBeforeExtraction,$CLASS#p03_archiveMetadataCannotOverrideSignedIdentity,$CLASS#p03_conflictingSignedSplitTargetsNeverAutoSelect,$CLASS#p03_localHeaderCrcTamperingRefusedBeforeStaging,$CLASS#p03_centralDirectoryExtentTamperingRefusedBeforeStaging,$CLASS#p03_featureDependencyCyclesAndMissingSplitsRefused,$CLASS#p03_platformIdentityAndSignerHistoryCannotGrantCompatibility,$CLASS#p03_unsupportedAbiAndOrphanConfigTargetsRefused,$CLASS#p04_forgedPublisherEvidenceCannotMintPlayProof,$CLASS#p04_browserAttributionExpiresAndRejectsChangedHostOrSource,$CLASS#p04_apkpureRequiresCurrentOptInAndAlternativeConsent,$CLASS#p04_unverifiedInstalledIdentityAndIndependentApprovalMatrix,$CLASS#p04_terminalInstallerReceiptReplayRefusedByStatePolicy,$CLASS#p04_consentCannotOverrideSignerMismatch,$CLASS#p04_browserClaimsNeverProducePlayOrPublisherProof,$CLASS#p04_downgradeAndUnknownPublisherRequireIndependentConsent"
log="$OUT/r3c08_p02_p04_adversarial_ui.txt"
first_failure="$OUT/r3c08_p02_p04_unqualified_attempt1.txt"
first_diagnostics="$OUT/r3c08_p02_p04_unqualified_attempt1_process_diagnostics.txt"
report="$OUT/r3c08_p02_p04_android_diagnostics.txt"
# Package inventory is only a no-install side-effect guard, never rollback proof.
adb shell pm list packages -3 --user 0 | tr -d '\r' | LC_ALL=C sort > "$OUT/r3c08_p02_p04_packages_before.txt"
# A prior P01 run may have left both the target and test APK processes resident.
timeout 25 adb shell am force-stop com.aurora.store.debug
timeout 25 adb shell am force-stop com.aurora.store.debug.test
sleep 2

process_diagnostics() {
  # Preserve OS process deaths even if the crash buffer has no Java stack trace.
  {
    echo '--- Android crash buffer ---'
    timeout 25 adb logcat -d -b crash -v threadtime 2>&1 | tail -n 300 || true
    echo '--- Android main/system process lifecycle (bounded) ---'
    timeout 25 adb logcat -d -b main -b system -v threadtime 2>&1 |
      grep -E 'R3C08RemoteProvider|AndroidRuntime|ActivityManager|ActivityTaskManager|am_crash|FATAL EXCEPTION|DeathRecipient|DeadObject|com\.aurora\.store\.debug' |
      tail -n 350 || true
  }
}
crash_report() {
  local rc="$1"
  [[ "$rc" != 0 ]] || return 0
  {
    printf 'R3C08_P02_P04_FAILURE_RC=%s\n' "$rc"
    process_diagnostics
    echo '--- Instrumentation output ---'
    tail -n 110 "$log" 2>/dev/null || true
    if [[ -f "$first_failure" ]]; then
      echo '--- Prior unqualified attempt preserved ---'
      tail -n 50 "$first_failure" || true
    fi
  } > "$report"
  printf 'R3C08_P02_P04_DIAGNOSTIC=%s\n' "$report" >&2
  tail -n 110 "$report" >&2 || true
}
trap 'crash_report "$?"' EXIT

# A crashed first *test* is not a failed JUnit assertion. Only the narrow
# zero-completion process-crash pattern permits a SINGLE fresh complete retry.
# The second attempt must pass ALL 21 real tests; a partial run NEVER qualifies.
first_unqualified=0
success=0
for attempt in 1 2; do
  timeout 25 adb logcat -c || { echo R3C08_P02_REFUSED_LOGCAT_RESET >&2; exit 1; }
  set +e
  timeout 520 adb shell am instrument -w -r -e class "$SELECTORS" "$RUNNER" | tee "$log"
  status=("${PIPESTATUS[@]}")
  set -e
  if [[ "${status[0]}" == 0 && "${status[1]}" == 0 ]] &&
     ! grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|Process crashed|INSTRUMENTATION_CODE: 0|INSTRUMENTATION_STATUS_CODE: -[12]' "$log" &&
     grep -Fxq 'OK (21 tests)' "$log" &&
     grep -Fxq 'INSTRUMENTATION_CODE: -1' "$log"; then
    success=1
    break
  fi
  if [[ "$attempt" == 1 && "${status[0]}" == 0 && "${status[1]}" == 0 ]] &&
     grep -Fxq 'INSTRUMENTATION_RESULT: shortMsg=Process crashed.' "$log" &&
     grep -Fxq 'INSTRUMENTATION_CODE: 0' "$log" &&
     grep -Fxq 'INSTRUMENTATION_STATUS: test=p02_remoteProviderDeathRefusesImportAndRestartsInNewProcess' "$log" &&
     ! grep -Eq '^INSTRUMENTATION_STATUS_CODE: (0|-[12])$|FAILURES!!!|INSTRUMENTATION_FAILED|^OK \(' "$log"; then
    cp "$log" "$first_failure"
    process_diagnostics > "$first_diagnostics"
    echo 'R3C08_P02_EARLY_PROCESS_CRASH_UNQUALIFIED: preserved; one fresh full-suite attempt permitted' >&2
    first_unqualified=1
    # These stops and the log reset bound the next run to a fresh attempt.
    timeout 25 adb shell am force-stop com.aurora.store.debug
    timeout 25 adb shell am force-stop com.aurora.store.debug.test
    sleep 2
    continue
  fi
  echo "R3C08_P02_P04_REFUSED_INSTRUMENTATION_ATTEMPT=$attempt (no bypass for assertion, partial test or repeated crash)" >&2
  exit 1
done
[[ "$success" == 1 ]] || { echo R3C08_P02_P04_REFUSED_NO_COMPLETE_PASS >&2; exit 1; }
# This file is the complete, successful *actual* instrument run. A previously
# failed attempt is never concatenated with it or counted as a passed test.
grep -Fxq 'OK (21 tests)' "$log" || { echo R3C08_P02_P04_REFUSED_TWENTY_ONE_TESTS >&2; exit 1; }
grep -Fxq 'INSTRUMENTATION_CODE: -1' "$log" || { echo R3C08_P02_P04_REFUSED_ANDROID_TERMINAL >&2; exit 1; }
adb shell pm list packages -3 --user 0 | tr -d '\r' | LC_ALL=C sort > "$OUT/r3c08_p02_p04_packages_after.txt"
cmp -s "$OUT/r3c08_p02_p04_packages_before.txt" "$OUT/r3c08_p02_p04_packages_after.txt" || {
  echo R3C08_P02_P04_REFUSED_PACKAGE_INVENTORY_CHANGED >&2; exit 1;
}
# Only the final, complete attempt's bounded provider-process PID trace counts.
timeout 25 adb logcat -d -v brief -s 'R3C08RemoteProvider:I' '*:S' \
  > "$OUT/r3c08_p02_remote_provider_lifecycle.log" || {
  echo R3C08_P02_REFUSED_REMOTE_PROVIDER_LOG >&2; exit 1;
}
python3 -B scripts/ci/r3c08_p02_p04_receipt.py \
  --provider-log "$OUT/r3c08_p02_remote_provider_lifecycle.log" \
  --log "$log" --before "$OUT/r3c08_p02_p04_packages_before.txt" \
  --after "$OUT/r3c08_p02_p04_packages_after.txt" \
  --sha "$GITHUB_SHA" --run-id "$GITHUB_RUN_ID" \
  --output "$OUT/R3C08_P02_P04_API36_ADVERSARIAL_RECEIPT.json"
if [[ "$first_unqualified" == 1 ]]; then
  echo 'R3C08_P02_P04_COMPLETE_RETRY_PASS: original attempt retained as UNQUALIFIED'
fi
echo 'R3C08_P02_P04_TWENTY_ONE_REAL_API36_READONLY_TESTS_PASS (no OS install/rollback claim)'
