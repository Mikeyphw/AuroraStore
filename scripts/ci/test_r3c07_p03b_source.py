#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""P03B source, host and receipt negatives; actual Android acceptance is R1D."""
from __future__ import annotations
from pathlib import Path
import ast
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'app/src/main/java/com/aurora/store/data/artifact'
ACT=(BASE/'ArtifactImportActivity.kt').read_text()
POL=(BASE/'ArtifactImportJourney.kt').read_text()
TEST=(ROOT/'app/src/androidTest/java/com/aurora/store/data/artifact/ArtifactImportJourneyP03BDeviceTest.kt').read_text()
JVM=(ROOT/'app/src/test/java/com/aurora/store/data/artifact/ArtifactImportJourneyTest.kt').read_text()
HOST=(ROOT/'scripts/ci/r3c07_p03b_api36.sh').read_text()
RECEIPT=(ROOT/'scripts/ci/r3c07_p03b_receipt.py').read_text()
FLOW=(ROOT/'.github/workflows/aurora-r1d-emulator.yml').read_text()
RUNNER=(ROOT/'scripts/ci/r3c03_c02_emulator_ci.sh').read_text()
AGG=(ROOT/'scripts/ci/test_r3c04_full_import.py').read_text()
CI=(ROOT/'.github/workflows/aurora-targeted.yml').read_text()
CLASS_NAME='com.aurora.store.data.artifact.ArtifactImportJourneyP03BDeviceTest'
REQUIRED_METHODS=(
    'explicitProviderChoiceAndRefusalNeverAutoNavigatesOrInstalls',
    'invalidDocumentGetsSafeManualRetryAndFreshSignedReview',
    'requestedVersionMismatchBlocksRealSignedFileConsent',
    'userSourceChangeAndActivityRecreateDiscardAllOldConsent',
    'realLandscapeConfigurationAndLargeTextRetainSafeActions',
)

def require(ok,label):
    if not ok:raise AssertionError('R3C07_P03B_SOURCE_REFUSED: '+label)

def valid(a,p,t,j,h,r,runner,flow,ci,agg):
    return all((
      'Retry file selection' in a,
      a.count('offerManualRetry()')==5,
      'ArtifactImportJourney.failureMessage(error)' in a,
      'requestedVersion.text.toString(), verified.attempt.versionCode' in a,
      'blockers.isEmpty() && versionMatches' in a,
      'if (!ArtifactImportJourney.versionMatches(' in a,
      'requestedVersion.text.toString(), receipt.attempt.versionCode' in a,
      'active != null || (::selectButton.isInitialized && !selectButton.isEnabled)' in a,
      'invalidateCurrentImport(ArtifactImportJourney.retryMessage())' in a,
      'active?.discard()' in a,
      'if (serial != requestSerial || ticket.isCancelled()' in a,
      'invalidateCurrentImport(ArtifactImportJourney.retryMessage())' in a,
      'versionMatches(reference: String, verifiedVersion: Long)' in p,
      'reference.any { it !in' in p,
      'fun failureMessage(error: Throwable)' in p,
      'Nothing installed. Choose a file again manually' in p,
      'no automatic provider fallback' in p,
      j.count('@Test fun ')==7,
      t.count('@Test fun ')==5,
      all(t.count('@Test fun '+name+'(')==1 and
          h.count('$CLASS#'+name)==1 and
          r.count("'"+name+"'")==1
          for name in REQUIRED_METHODS),
      'ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE' in t,
      'scenario.recreate()' in t,
      'content://com.aurora.store.debug.r3c07p02/' in t,
      'uiAutomation.takeScreenshot()' in t,
      t.count('screenshot("r3c07_p03b_')==3,
      'button(ui, "Request Android installation").isEnabled).isFalse()' in t,
      'install(ui).performClick()' not in t,
      'ArtifactInstallSession.install(' not in t,
      h.count('adb shell am instrument ')==1,
      h.count('adb exec-out run-as "$PACKAGE" cat')==1,
      'INSTRUMENTATION_CODE: -1' in h,
      'OK (5 tests)' in h,
      'R3C07_P03B_REFUSED_PRIVATE_SCREENSHOT' in h,
      'R3C07_P03B_REFUSED_STALE_SCREENSHOT_CLEANUP' in h,
      h.index('adb shell run-as "$PACKAGE" rm -f') < h.index('timeout 520 adb shell am instrument'),
      '${GITHUB_SHA:?}' in h and '${GITHUB_RUN_ID:?}' in h,
      'phase\':\'R3C07_P03B_REAL_PROVIDER_RETRY_ROTATION\'' in r,
      'not a PNG image with valid IHDR' in r,
      'PNG chunk CRC mismatch' in r,
      'PNG pixel stream truncated, oversized or invalid' in r,
      "'provider_listing_availability_proven':False" in r,
      "'installation_qualified':False" in r,
      r.count("'real_talkback_service_qualified':False")==1,
      runner.count('bash scripts/ci/r3c07_p03b_api36.sh "$RUNNER" "$OUT"')==1,
      runner.find('bash scripts/ci/r3c07_p02b_api36.sh') <
        runner.find('bash scripts/ci/r3c07_p03b_api36.sh') <
        runner.find('scripts/ci/r3c07_p03_talkback.py --run'),
      flow.count('scripts/ci/test_r3c07_p03b_source.py')==1,
      flow.count('uses: ReactiveCircus/android-emulator-runner@')==2,
      ci.count('python3 -B scripts/ci/test_r3c07_p03b_source.py')==1,
      ci.count('app:testVanillaDebugUnitTest')==1,
      ci.count('--tests \'com.aurora.store.data.artifact.ArtifactImportJourneyTest\'')==1,
      agg.count("'test_r3c07_p03b_source.py'")==1,
      'r3c06_live_install: ' not in h,
    ))

require(valid(ACT,POL,TEST,JVM,HOST,RECEIPT,RUNNER,FLOW,CI,AGG),
        'real signed UI, safe retry, screenshot evidence and inherited CI contracts')
for label,which,old,new in (
    ('version bypass','activity','blockers.isEmpty() && versionMatches','blockers.isEmpty()'),
    ('install method bypass','activity','if (!ArtifactImportJourney.versionMatches(', 'if (false && !ArtifactImportJourney.versionMatches('),
    ('unsanitized error','activity','ArtifactImportJourney.failureMessage(error)','error.message'),
    ('retry removed','activity','offerManualRetry()','/* no retry */'),
    ('unguarded consent','activity','if (serial != requestSerial || ticket.isCancelled()', 'if (false'),
    ('version overflow','policy','reference.any { it !in','reference.all { it !in'),
    ('false success','receipt',"'installation_qualified':False","'installation_qualified':True"),
    ('fake image permitted','receipt','PNG chunk CRC mismatch','accept damaged CRC'),
    ('removed screenshot','device','uiAutomation.takeScreenshot()','null'),
    ('no activity restart','device','scenario.recreate()','/* skip */'),
    ('actual Android gate bypass','runner','bash scripts/ci/r3c07_p03b_api36.sh "$RUNNER" "$OUT"','echo NOT_RUN'),
    ('unbound SHA','host','${GITHUB_SHA:?}','b'*40),
    ('host no screenshot','host','adb exec-out run-as "$PACKAGE" cat','echo skipped'),
    ('missing screenshot replay cleanup','host',
        'R3C07_P03B_REFUSED_STALE_SCREENSHOT_CLEANUP', 'silently ignore cleanup'),
    ('missing real retry test selector','host',
        '#invalidDocumentGetsSafeManualRetryAndFreshSignedReview',
        '#totallyDifferentTest'),
    ('missing targeted JVM','ci','--tests \'com.aurora.store.data.artifact.ArtifactImportJourneyTest\'','--tests \'DifferentTest\''),
):
    values=[ACT,POL,TEST,JVM,HOST,RECEIPT,RUNNER,FLOW,CI,AGG]
    index={'activity':0,'policy':1,'device':2,'jvm':3,'host':4,'receipt':5,
           'runner':6,'flow':7,'ci':8,'agg':9}[which]
    require(old in values[index],'mutant preimage missing: '+label)
    values[index]=values[index].replace(old,new,1)
    require(not valid(*values),'unsafe source mutation accepted: '+label)

ast.parse(RECEIPT)
result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/ci/r3c07_p03b_receipt.py'),'--selftest'],
                      cwd=ROOT,capture_output=True,text=True,timeout=25)
require(result.returncode==0 and '13 negatives' in result.stdout,
        'as-run receipt executable negatives missing: '+(result.stdout+result.stderr)[-1000:])
result=subprocess.run(['bash','-n',str(ROOT/'scripts/ci/r3c07_p03b_api36.sh')],
                      cwd=ROOT,capture_output=True,text=True,timeout=10)
require(result.returncode==0,'invalid host Bash syntax')
print('R3C07_P03B_SOURCE_AND_16_NEGATIVES_PASS: 7 JVM method definitions, 5 wired API36 scenarios, 3 required PNG captures, source-bound receipt contract (NOT DEVICE QUALIFIED)')
