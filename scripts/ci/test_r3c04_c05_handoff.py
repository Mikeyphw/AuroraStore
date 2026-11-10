#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""C04-05 browser handoffs: source/opt-in/stale-claim and Play-isolation contract."""
from pathlib import Path

root = Path(__file__).resolve().parents[2]
a = root / 'app/src/main/java/com/aurora/store/data/artifact'
t = root / 'app/src/test/java/com/aurora/store/data/artifact'
source = (a / 'ArtifactSourceHandoff.kt').read_text()
claim = (a / 'ArtifactHandoffClaimPolicy.kt').read_text()
ui = (a / 'ArtifactImportActivity.kt').read_text()
provenance = (a / 'ArtifactProvenance.kt').read_text()
tests = (t / 'ArtifactSourceHandoffTest.kt').read_text()
claim_tests = (t / 'ArtifactHandoffClaimPolicyTest.kt').read_text()

def check(predicate, msg):
    if not predicate:
        raise SystemExit('R3C04_C05_REFUSED: ' + msg)

for marker in ('rawUserInfo', 'rawQuery', 'rawFragment', 'encodedControl',
               'source == ArtifactSource.APKPURE_OPT_IN && !apkPureOptIn',
               'host == "github.com"', '"apkmirror.com"', '"f-droid.org"',
               '"apkpure.com"', '"https"', '"releases"', '"tag"'):
    check(marker in source, 'missing provider safety contract: ' + marker)
for marker in ('selected != ArtifactSource.LOCAL_DOCUMENT',
               'launched.source == selected', 'launched.exactInput == enteredUrl',
               'selected != ArtifactSource.APKPURE_OPT_IN || apkPureOptIn',
               'ArtifactProvenance(ArtifactSource.LOCAL_DOCUMENT, untrustedFilename)'):
    check(marker in claim, 'missing stale source/optin protection: ' + marker)
for marker in ('lastBrowserLaunch = null',
               'ArtifactHandoffClaimPolicy.afterSuccessfulLaunch',
               'ArtifactHandoffClaimPolicy.selection(',
               'ArtifactPickerPolicy.safeDisplayLabel(name)',
               'ActivityResultContracts.OpenDocument()',
               'startActivity(Intent(Intent.ACTION_VIEW',
               'apkpure_opt_in", false', 'ArtifactInstallSession.install('):
    check(marker in ui, 'missing UI handoff or picker/installer guard: ' + marker)
check('provenanceHost' not in ui, 'old unbound host survived')
check('PlayVerifiedEvidenceStore' not in (ui + claim + source), 'browser claims can access Play receipts')
check('GOOGLE_PLAY' not in provenance, 'source can masquerade as Google Play')
check('isVerifiedPlayDelivery' in provenance, 'Play proof distinction absent')
check(tests.count('@Test') >= 7 and claim_tests.count('@Test') >= 7,
      'adversarial JVM tests insufficient')
check('apkPureOptInIsRevocableEvenAfterBrowserLaunch' in claim_tests and
      'editingUrlInvalidatesBrowserAttribution' in claim_tests and
      'changingSourceDropsStaleBrowserOrigin' in claim_tests,
      'provider-switch, URL edit and optin revocation not tested')
print('R3C04_C05_SOURCE_PASS: browser-only HTTPS handoffs; no Play proof, opt-in and source-scoped UI claims')
