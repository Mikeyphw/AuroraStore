#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Twenty-one real API36 P02-P04 read-only adversarial cases. No PackageInstaller commit,
# app download, browser navigation, privileged provider or Play receipt mutation.
set -euo pipefail
[[ $# == 2 ]] || { echo R3C08_P02_P04_REFUSED_ARGS >&2; exit 2; }
RUNNER="$1"; OUT="$2"
[[ -n "$RUNNER" && -d "$OUT" ]] || { echo R3C08_P02_P04_REFUSED_INPUT >&2; exit 2; }
[[ "$(adb shell getprop ro.build.version.sdk | tr -d '\r')" == 36 ]] || {
  echo R3C08_P02_P04_REFUSED_NOT_API36 >&2; exit 2;
}
CLASS='com.aurora.store.data.artifact.ArtifactR3C08AdversarialDeviceTest'
SELECTORS="$CLASS#p02_cancelledLeaseRejectsNewStreamAndClosesOwnedInput,$CLASS#p02_preCancelledPrivateStagingCleansNewDirectory,$CLASS#p02_providerOpenFailureCleansPrivateStageAndDisablesInstall,$CLASS#p02_remoteProviderDeathRefusesImportAndRestartsInNewProcess,$CLASS#p02_failedProviderRetryResetsAllApprovalsAndCleansCache,$CLASS#p03_traversalZipRejectedBeforeExtraction,$CLASS#p03_archiveMetadataCannotOverrideSignedIdentity,$CLASS#p03_conflictingSignedSplitTargetsNeverAutoSelect,$CLASS#p03_localHeaderCrcTamperingRefusedBeforeStaging,$CLASS#p03_centralDirectoryExtentTamperingRefusedBeforeStaging,$CLASS#p03_featureDependencyCyclesAndMissingSplitsRefused,$CLASS#p03_platformIdentityAndSignerHistoryCannotGrantCompatibility,$CLASS#p03_unsupportedAbiAndOrphanConfigTargetsRefused,$CLASS#p04_forgedPublisherEvidenceCannotMintPlayProof,$CLASS#p04_browserAttributionExpiresAndRejectsChangedHostOrSource,$CLASS#p04_apkpureRequiresCurrentOptInAndAlternativeConsent,$CLASS#p04_unverifiedInstalledIdentityAndIndependentApprovalMatrix,$CLASS#p04_terminalInstallerReceiptReplayRefusedByStatePolicy,$CLASS#p04_consentCannotOverrideSignerMismatch,$CLASS#p04_browserClaimsNeverProducePlayOrPublisherProof,$CLASS#p04_downgradeAndUnknownPublisherRequireIndependentConsent"
log="$OUT/r3c08_p02_p04_adversarial_ui.txt"
# A package inventory is not an installer-rollback proof. It is only a
# fail-closed guard against unexpected install/uninstall side effects here.
adb shell pm list packages -3 --user 0 | tr -d '\r' | LC_ALL=C sort > "$OUT/r3c08_p02_p04_packages_before.txt"
# Do not let preceding ActivityScenario runs lend state to this Android suite.
timeout 25 adb shell am force-stop com.aurora.store.debug
# P01 may have left the test APK's remote document provider already alive.
# Stop that *test-only* package before clearing logcat, or its original PID
# cannot be independently paired with the subsequent death event.
timeout 25 adb shell am force-stop com.aurora.store.debug.test
# Fresh log buffer: require an actual isolated test-provider process death and
# a DIFFERENT freshly started provider PID after recovery.
timeout 25 adb logcat -c || { echo R3C08_P02_REFUSED_LOGCAT_RESET >&2; exit 1; }
report="$OUT/r3c08_p02_p04_android_diagnostics.txt"
crash_report() {
  rc="$1"
  [[ "$rc" != 0 ]] || return 0
  {
    printf 'R3C08_P02_P04_FAILURE_RC=%s\n' "$rc"
    timeout 25 adb logcat -d -b crash -v threadtime 2>&1 | tail -n 450 || true
    echo '--- Instrumentation output ---'
    tail -n 110 "$log" 2>/dev/null || true
  } > "$report"
  printf 'R3C08_P02_P04_DIAGNOSTIC=%s\n' "$report" >&2
  tail -n 90 "$report" >&2 || true
}
trap 'crash_report "$?"' EXIT
set +e
timeout 520 adb shell am instrument -w -r -e class "$SELECTORS" "$RUNNER" | tee "$log"
status=("${PIPESTATUS[@]}")
set -e
[[ "${status[0]}" == 0 && "${status[1]}" == 0 ]] || {
  echo R3C08_P02_P04_REFUSED_INSTRUMENTATION >&2; exit 1;
}
if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|Process crashed|INSTRUMENTATION_CODE: 0|INSTRUMENTATION_STATUS_CODE: -[12]' "$log"; then
  echo R3C08_P02_P04_REFUSED_REAL_TESTS >&2; exit 1
fi
grep -Fxq 'OK (21 tests)' "$log" || { echo R3C08_P02_P04_REFUSED_TWENTY_ONE_TESTS >&2; exit 1; }
grep -Fxq 'INSTRUMENTATION_CODE: -1' "$log" || { echo R3C08_P02_P04_REFUSED_ANDROID_TERMINAL >&2; exit 1; }
adb shell pm list packages -3 --user 0 | tr -d '\r' | LC_ALL=C sort > "$OUT/r3c08_p02_p04_packages_after.txt"
cmp -s "$OUT/r3c08_p02_p04_packages_before.txt" "$OUT/r3c08_p02_p04_packages_after.txt" || {
  echo R3C08_P02_P04_REFUSED_PACKAGE_INVENTORY_CHANGED >&2; exit 1;
}
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
echo 'R3C08_P02_P04_TWENTY_ONE_REAL_API36_READONLY_TESTS_PASS (no OS install/rollback claim)'
