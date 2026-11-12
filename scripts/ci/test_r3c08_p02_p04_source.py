#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real R3C08 P02-P04 source gate, host graph and adversarial receipt contract.

This does not label synthetic fixtures as device evidence. The CI emulator must
run every selected method and independently seal its as-run log and inventories.
"""
from __future__ import annotations
import pathlib
import re
import subprocess
import sys

ROOT=pathlib.Path(__file__).resolve().parents[2]
TEST=ROOT/'app/src/androidTest/java/com/aurora/store/data/artifact/ArtifactR3C08AdversarialDeviceTest.kt'
HOST=ROOT/'scripts/ci/r3c08_p02_p04_api36.sh'
RECEIPT=ROOT/'scripts/ci/r3c08_p02_p04_receipt.py'
P01_HOST=ROOT/'scripts/ci/r3c08_p01_api36.sh'
P01_RECEIPT=ROOT/'scripts/ci/r3c08_p01_receipt.py'

class Refused(AssertionError):pass

def check(ok,why):
    if not ok:raise Refused('R3C08_P02_P04_SOURCE_REFUSED: '+why)
for path in (TEST,HOST,RECEIPT,P01_HOST,P01_RECEIPT):
    check(path.is_file(),'missing '+str(path))
test=TEST.read_text(encoding='utf8')
host=HOST.read_text(encoding='utf8')
receipt=RECEIPT.read_text(encoding='utf8')
p01_host=P01_HOST.read_text(encoding='utf8')
p01_receipt=P01_RECEIPT.read_text(encoding='utf8')

METHODS=(
 'p02_cancelledLeaseRejectsNewStreamAndClosesOwnedInput',
 'p02_preCancelledPrivateStagingCleansNewDirectory',
 'p02_providerOpenFailureCleansPrivateStageAndDisablesInstall',
 'p02_remoteProviderDeathRefusesImportAndRestartsInNewProcess',
 'p02_failedProviderRetryResetsAllApprovalsAndCleansCache',
 'p03_traversalZipRejectedBeforeExtraction',
 'p03_archiveMetadataCannotOverrideSignedIdentity',
 'p03_conflictingSignedSplitTargetsNeverAutoSelect',
 'p03_localHeaderCrcTamperingRefusedBeforeStaging',
 'p03_centralDirectoryExtentTamperingRefusedBeforeStaging',
 'p03_featureDependencyCyclesAndMissingSplitsRefused',
 'p03_platformIdentityAndSignerHistoryCannotGrantCompatibility',
 'p03_unsupportedAbiAndOrphanConfigTargetsRefused',
 'p04_forgedPublisherEvidenceCannotMintPlayProof',
 'p04_browserAttributionExpiresAndRejectsChangedHostOrSource',
 'p04_apkpureRequiresCurrentOptInAndAlternativeConsent',
 'p04_unverifiedInstalledIdentityAndIndependentApprovalMatrix',
 'p04_terminalInstallerReceiptReplayRefusedByStatePolicy',
 'p04_consentCannotOverrideSignerMismatch',
 'p04_browserClaimsNeverProducePlayOrPublisherProof',
 'p04_downgradeAndUnknownPublisherRequireIndependentConsent',
)

def test_guard(s):
    return (s.count('@Test fun ')==21 and
            all(re.search(r'@Test\s+fun\s+'+re.escape(m)+r'\s*\(',s) is not None for m in METHODS) and
            all(x in s for x in (
                'lease.attach(input)','lease.cancel()', 'lease.isCancelled()',
                'if (checks >= 5) midflight.cancel()',
                'assertThat(midflight.isCancelled()).isTrue()',
                'ArtifactPrivateStager.stage(', 'assertThat(stages()).containsExactlyElementsIn(before)',
                'ArtifactZipPreflight.inspect(source)',
                'ArtifactArchiveDescriptorPolicy.checkAgainstSignedApks(',
                'ArtifactSplitCompatibilityPolicy.check(',
                'ArtifactFeatureDependencyPolicy.check(',
                'ArtifactApkIdentityPolicy.installedSignerStatus(',
                'ArtifactApkIdentityPolicy.requirePlatformAgreement(',
                'ZipEntry.STORED', 'corrupt[14] =', 'corrupt[eocd + 12] =',
                'ArtifactImportDecision.blockers(', 'ArtifactOriginBoundary.claimOnly(',
                'ArtifactHandoffClaimPolicy.selection(',
                'ArtifactHandoffClaimPolicy.afterSuccessfulLaunch(',
                'ArtifactSourceHandoff.parse(',
                'ArtifactIndependentEvidence.fromVerifiedImport(',
                'ArtifactSessionReceiptPolicy.next(',
                'SIGNER_MISMATCH','UNVERIFIED_SIGNATURE',
                'EXPLICIT_INSTALL_CONSENT_REQUIRED','DOWNGRADE_CONSENT_REQUIRED',
                'UNANCHORED_PUBLISHER_CONSENT_REQUIRED',
                'not proof', 'rollback',
                'method.invoke(a, Uri.parse(',
                'p02_remoteProviderDeathRefusesImportAndRestartsInNewProcess',
                'p02_failedProviderRetryResetsAllApprovalsAndCleansCache',
                'noInstallConsent(activity)', 'getDeclaredField("active")')) and
            s.count('ArtifactSplitCompatibilityPolicy.check(')>=2 and
            s.count('ArtifactOriginBoundary.claimOnly(')>=2 and
            s.count('assertThat(stages()).containsExactlyElementsIn(before)')>=4 and
            all(x not in s for x in (
                'ArtifactInstallSession.install(',
                'PackageInstaller.SessionParams',
                'PlayVerifiedEvidenceStore(', 'startActivity(Intent.ACTION_VIEW',
                'shell pm install', 'su -c')))

def host_guard(s):
    return (s.count('adb shell am instrument')==1 and
            'OK (21 tests)' in s and 'INSTRUMENTATION_CODE: -1' in s and
            'PIPESTATUS[@]' in s and 'timeout 520 adb shell am instrument' in s and
            'adb logcat -c' in s and 'R3C08RemoteProvider:I' in s and
            'adb shell am force-stop com.aurora.store.debug.test' in s and
            'r3c08_p02_remote_provider_lifecycle.log' in s and
            'R3C08_P02_P04_RECEIPT' not in s and
            'scripts/ci/r3c08_p02_p04_receipt.py' in s and
            'GITHUB_SHA' in s and 'GITHUB_RUN_ID' in s and
            'cmp -s ' in s and
            'r3c08_p02_p04_packages_before.txt' in s and
            'r3c08_p02_p04_packages_after.txt' in s and
            'adb logcat -d -b crash' in s and
            'trap ' in s and
            all('$CLASS#'+m in s for m in METHODS) and
            'pm install ' not in s and 'ksud module install' not in s and
            'r3c08_p02_p04_android_diagnostics.txt' in s)

# P02 audit must be truthful: only a real separately running Android test provider
# process (not a routine FileNotFoundException) can satisfy the process-death claim.
DOC=ROOT/'app/src/androidTest/java/com/aurora/store/data/artifact/R3C08GrantDataProvider.java'
CTL=ROOT/'app/src/androidTest/java/com/aurora/store/data/artifact/R3C08GrantControlProvider.java'
MANIFEST=ROOT/'app/src/androidTest/AndroidManifest.xml'
for file in (DOC,CTL,MANIFEST):check(file.is_file(),'missing isolated test fixture '+str(file))
data=DOC.read_text();control=CTL.read_text();manifest=MANIFEST.read_text()
check('android:process=":r3c08_saf_document"' in manifest and
      manifest.count('android:process=":r3c08_saf_document"')==1,
      'provider death could terminate the instrumentation runner')
check('R3C08_PROVIDER_START pid=' in data and
      'R3C08_PROVIDER_KILL pid=' in data and
      'Process.killProcess(Process.myPid())' in data and
      '"/crash.apk".equals(uri.getPath())' in data and
      'ParcelFileDescriptor.MODE_READ_ONLY' in data,
      'separate-process provider death or surviving read-only data path missing')
check('"grant_crash".equals(method)' in control and
      '"revoke_crash".equals(method)' in control and
      'Arrays.asList(packages).contains(TARGET)' in control and
      'ctx.revokeUriPermission(' in control,
      'crash grant must be exact-UID authenticated and revoked after testing')
check('if (crashGranted) request("revoke_crash")' in test and
      'if (signedGranted) request("revoke")' in test and
      'target.contentResolver.openInputStream(signed)' in test and
      'waitFor' not in test, # use awaitLabel and bounded retries; avoid blocking activity thread
      'real provider death/recovery and cleanup not exercised')
check('method.invoke(activity, Uri.parse(' not in test and
      'method.invoke(a, Uri.parse(' in test,
      'P02 test has a stale/undefined ActivityScenario callback receiver')
check('R3C08_PROVIDER_(START|KILL)' in receipt and
      'isolated_provider_verified_restart_cycles' in receipt and 'len(cycles)>=1' in receipt,
      'host receipt did not prove distinct provider restart PID')

check(test_guard(test),'twenty-one genuinely authored read-only Android test methods or security gates missing')
check(host_guard(host),'host omits actual twenty-one device selectors, evidence or failure safeguards')
check(p01_host.count('bash scripts/ci/r3c08_p02_p04_api36.sh "$RUNNER" "$OUT"')==1,
      'P02-P04 must be chained exactly once from successful existing P01 API36 graph')
check(p01_host.index('r3c08_p01_receipt.py') < p01_host.index('bash scripts/ci/r3c08_p02_p04_api36.sh'),
      'P02-P04 cannot run before the proven P01 receipt')
check('three test starts and three test finishes' in p01_receipt and
      "matching[0][0]<matching[1][0]" in p01_receipt,
      'P01 HF04 must bind ordered actual AndroidJUnitRunner start/finish events')
check('R3C08_P02_P04_RECEIPT_SELFTEST_PASS' in receipt and
      'isolated_provider_lifecycle_log_sha256' in receipt and
      'p02_isolated_test_provider_actual_process_death_and_restart_tested' in receipt and
      'package_inventory_unchanged' in receipt and
      "'actual_install_rollback_qualified':False" in receipt and
      "'actual_provider_process_death_qualified':False" in receipt,
      'receipt could claim unmeasured provider death or installation rollback')

for label,source,old,new,guard in (
 ('remove-test',test,'@Test fun p02_cancelledLeaseRejectsNewStreamAndClosesOwnedInput','fun p02_cancelledLeaseRejectsNewStreamAndClosesOwnedInput',test_guard),
 ('remove-stage-cleanup',test,'assertThat(stages()).containsExactlyElementsIn(before)','assertThat(stages()).isNotNull()',test_guard),
 ('remove-signed-split-check',test,'ArtifactSplitCompatibilityPolicy.check(','println(',test_guard),
 ('remove-Play-isolation',test,'ArtifactOriginBoundary.claimOnly(','println(',test_guard),
 ('add-install',test,'/* SPDX-License-Identifier: GPL-3.0-or-later */','ArtifactInstallSession.install(',test_guard),
 ('remove-instrument',host,'adb shell am instrument','echo skipped',host_guard),
 ('remove-PID',host,'adb logcat -d -b crash','echo ignored',host_guard),
 ('remove-inventory-guard',host,'cmp -s ','echo ignored ',host_guard),
 ('remove-P03-test',test,'@Test fun p03_localHeaderCrcTamperingRefusedBeforeStaging','fun p03_localHeaderCrcTamperingRefusedBeforeStaging',test_guard),
 ('remove-CRC-guard',test,'corrupt[14] =','corrupted[14] =',test_guard),
 ('remove-feature-veto',test,'ArtifactFeatureDependencyPolicy.check(', 'println(',test_guard),
 ('remove-identity-veto',test,'ArtifactApkIdentityPolicy.installedSignerStatus(', 'println(',test_guard),
 ('remove-P04-forged-tier',test,'ArtifactIndependentEvidence.fromVerifiedImport(', 'println(',test_guard),
 ('remove-P04-browser-lease',test,'ArtifactHandoffClaimPolicy.afterSuccessfulLaunch(', 'println(',test_guard),
 ('remove-P04-apkpure-gate',test,'p04_apkpureRequiresCurrentOptInAndAlternativeConsent', 'missingP04ApkpureMethod',test_guard),
 ('remove-P04-consent-matrix',test,'p04_unverifiedInstalledIdentityAndIndependentApprovalMatrix', 'missingP04ApprovalMethod',test_guard),
 ('remove-P04-OS-replay',test,'ArtifactSessionReceiptPolicy.next(', 'println(',test_guard),
 ('remove-test-selector',host,'$CLASS#p04_consentCannotOverrideSignerMismatch','$CLASS#missingMethod',host_guard),
):
    mutated=source.replace(old,new) if label in ('remove-stage-cleanup','remove-signed-split-check','remove-feature-veto','remove-identity-veto','remove-Play-isolation','remove-P04-forged-tier','remove-P04-browser-lease','remove-P04-OS-replay') else source.replace(old,new,1)
    check(mutated!=source and not guard(mutated), 'negative test did not reject '+label)
for script,count in ((RECEIPT,'34 negatives'),(P01_RECEIPT,'18 negatives')):
    result=subprocess.run([sys.executable,'-B',str(script),'--selftest'],
        cwd=ROOT,capture_output=True,text=True,timeout=30)
    check(result.returncode==0 and count in result.stdout,
          'receipt negative tests failed: '+str(script)+' '+(result.stdout+result.stderr)[-1600:])
check(subprocess.run(['bash','-n',str(HOST)],capture_output=True).returncode==0,
      'adversarial host bash source invalid')
# P05 is a mandatory additional source gate, not an optional marker-only document.
p05=ROOT/'scripts/ci/test_r3c08_p05_source.py'
check(p05.is_file(), 'P05 signoff security source gate missing')
p05_result=subprocess.run([sys.executable,'-B',str(p05)],cwd=ROOT,
    capture_output=True,text=True,timeout=70)
check(p05_result.returncode==0 and 'R3C08_P05_SOURCE_SECURITY_PASS' in p05_result.stdout,
      'P05 final signoff source/security regression failed: '+
      (p05_result.stdout+p05_result.stderr)[-1500:])
print('R3C08_P02_P04_SOURCE_PASS: twenty-one independently selected API36 tests, '
      'eighteen guard mutations, 34 P02-P04 receipt negatives, real package-state invariant, '
      'ordered P01 source-bound receipt and no install/rollback overclaim')
