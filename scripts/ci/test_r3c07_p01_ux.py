#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R3C07 P01 independent source/security gate. Runtime acceptance is API36-only."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
A=(ROOT/'app/src/main/java/com/aurora/store/data/artifact/ArtifactImportActivity.kt').read_text()
R=(ROOT/'app/src/main/java/com/aurora/store/data/artifact/ArtifactReviewPresentation.kt').read_text()
D=(ROOT/'app/src/main/java/com/aurora/store/data/artifact/ArtifactImportDecision.kt').read_text()
E=(ROOT/'scripts/ci/r3c03_c02_emulator_ci.sh').read_text()
T=(ROOT/'app/src/androidTest/java/com/aurora/store/data/artifact/ArtifactReviewUxDeviceTest.kt').read_text()

def require(predicate, label):
    assert predicate, 'R3C07_P01_REFUSED: '+label

for token in (
        'heading("Verification receipt")', 'heading("Android installation outcome")',
        'heading("Installation permissions for this verified file")',
        'ViewCompat.setAccessibilityHeading(this, true)',
        'View.ACCESSIBILITY_LIVE_REGION_POLITE',
        'ArtifactReviewPresentation.summary(facts)',
        'technicalReceipt.text = ArtifactReviewPresentation.verification(facts)',
        'receiptToggle.visibility = View.VISIBLE',
        'technicalReceipt.visibility = View.GONE',
        'receiptToggle.visibility = View.GONE',
        'text = "Show technical verification details"',
        '"Hide technical verification details"',
        'isEnabled = false',
        'cancellation.cancel()', 'requestSerial += 1',
        'installConsent.isChecked = false',
        'unknownPublisherConsent.isChecked = false',
        'downgradeConsent.isChecked = false',
        'ArtifactImportDecision.blockers(',
        'ArtifactInstallSession.lastResult('):
    require(token in A, 'missing activity invariant '+token)
require('error.message' not in A, 'raw exception message exposed in import/install UI')
require('error.stackTrace' not in A, 'raw stacktrace exposed in UI')
require('PlayVerifiedEvidenceStore' not in A+R, 'non-Play importer touched Play evidence')
require('onSaveInstanceState' not in A, 'verified/import consent persisted across rotation')
for token in (
        'fun summary(f: VerifiedFacts)',
        'SIGNED APK FILES VERIFIED — NOT INSTALLED',
        'Exact-version availability from provider: UNKNOWN',
        'Publisher identity: NOT independently authenticated',
        'NOT Google Play proof',
        'Final Android compatibility and installation result: NOT CONFIRMED',
        'true -> "Matches installed identity (not publisher authentication)"',
        'false -> "Mismatch — installation blocked"',
        '"Unknown — installation blocked"',
        'append("Downgrade requested: separate approval required; Android may refuse',
        'fun verification(f: VerifiedFacts)',
        'APK signing certificate SHA-256:'):
    require(token in R, 'missing truthful review '+token)
for token in ('installedSignerMatches != true', 'UNANCHORED_PUBLISHER_CONSENT_REQUIRED',
              'DOWNGRADE_CONSENT_REQUIRED', 'EXPLICIT_INSTALL_CONSENT_REQUIRED'):
    require(token in D, 'install consent/security gate weakened '+token)
require('R3C07_UX_CLASS' in E and 'R3C07_P01_API36_UX_PASS' in E,
        'API36 independent UX gate not wired')
require("'^OK \\(5 tests\\)'" in E, 'missing measured 5-test instrument result')
require(T.count('@Test')==5, 'exactly five instrumentation tests required')
for token in ('scenario.recreate()',
              'assertThat(toggle.visibility).isEqualTo(View.GONE)',
              'View.ACCESSIBILITY_LIVE_REGION_POLITE',
              'ViewCompat.isAccessibilityHeading', 'setSelection(6)'):
    require(token in T, 'missing device UX negative '+token)
# Three distinct assertions, including startup, rotation and provider switch.
# The device suite intentionally uses a helper method `install(views)` rather
# than a variable named `install`. Verify the actual Kotlin expressions, not
# an invented source spelling. Do not substitute assertions on a different view.
require(T.count('assertThat(install(views).isEnabled).isFalse()') == 2,
        'startup and rotation must independently keep install disabled')
require(T.count('assertThat(install(root(activity)).isEnabled).isFalse()') == 1,
        'provider switch must keep install disabled')
require('private fun install(views: List<View>): Button' in T and
        'it.text.toString() == "Request Android installation"' in T,
        'install helper must resolve the real install button')
require('PackageInstaller' not in T and 'startActivity(Intent' not in T,
        'read-only UX tests must not install or browse')
print('R3C07_P01_SOURCE_SECURITY_PASS: truthful review + disclosure + accessible states + 5 separately measured UI tests')
