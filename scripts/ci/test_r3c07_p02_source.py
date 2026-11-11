#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R3C07 P02A source contract; true API36 evidence must come from R1D."""
from pathlib import Path
from xml.etree import ElementTree
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ACTIVITY = (ROOT/'app/src/main/java/com/aurora/store/data/artifact/ArtifactImportActivity.kt').read_text()
DEBUG = (ROOT/'app/src/debug/AndroidManifest.xml').read_text()
PROVIDER = (ROOT/'app/src/debug/java/com/aurora/store/data/artifact/ArtifactP02SignedFileProvider.kt').read_text()
TEST = (ROOT/'app/src/androidTest/java/com/aurora/store/data/artifact/ArtifactReviewP02DeviceTest.kt').read_text()
RUNNER = (ROOT/'scripts/ci/r3c03_c02_emulator_ci.sh').read_text()
AGGREGATE = (ROOT/'scripts/ci/test_r3c04_full_import.py').read_text()
RECEIPT = ROOT/'scripts/ci/r3c07_p02_receipt.py'


def require(condition: bool, what: str) -> None:
    assert condition, 'R3C07_P02A_SOURCE_REFUSED: '+what


for needle in (
    'contentDescription = "Import source or provider"',
    'sources.contentDescription = "Import source or provider: ${choice.title}"',
    'contentDescription = "Provider reference for browser navigation; not APK publisher proof"',
    'accessibilityLiveRegion = View.ACCESSIBILITY_LIVE_REGION_POLITE',
    'ArtifactApkVerifier.verify(this, staged, provenance)',
    'ArtifactReviewPresentation.summary(facts)',
    'technicalReceipt.visibility = View.GONE',
    'installButton.isEnabled = false',
    'requestSerial += 1',
    'cancellation.cancel()',
    'active?.discard()',
):
    require(needle in ACTIVITY, 'missing production UI or lifecycle invariant '+needle)
require('error.message' not in ACTIVITY and 'error.stackTrace' not in ACTIVITY,
        'error text must not leak into UI')
require('onSaveInstanceState' not in ACTIVITY,
        'verified selection/consent must not be restored from Android state')
require('PlayVerifiedEvidenceStore' not in ACTIVITY,
        'local import must not mint Google Play evidence')
# The Android XML namespace is REQUIRED and begins with http://. Do not
# confuse that declaration with an actual browser or network call.
ANDROID_NS = '{http://schemas.android.com/apk/res/android}'

def private_debug_provider(manifest: str) -> bool:
    try:
        root = ElementTree.fromstring(manifest)
    except ElementTree.ParseError:
        return False
    apps = root.findall('application')
    if root.tag != 'manifest' or len(apps) != 1:
        return False
    children = list(apps[0])
    if len(children) != 1 or children[0].tag != 'provider':
        return False
    attrs = children[0].attrib
    return (attrs.get(ANDROID_NS+'name') ==
                '.data.artifact.ArtifactP02SignedFileProvider' and
            attrs.get(ANDROID_NS+'authorities') ==
                '${applicationId}.r3c07p02' and
            attrs.get(ANDROID_NS+'exported') == 'false' and
            attrs.get(ANDROID_NS+'grantUriPermissions', 'false') == 'false' and
            attrs.get(ANDROID_NS+'readPermission') is None and
            attrs.get(ANDROID_NS+'writePermission') is None and
            apps[0].get(ANDROID_NS+'usesCleartextTraffic') != 'true')

require(private_debug_provider(DEBUG),
        'debug-only, non-exported content URI fixture provider missing or unsafe')
# Real adversarial cases, including the XML namespace that caused the HF00
# false-positive. Removing the check must also cause this self-test to fail.
for label, mutant in {
    'exported provider': DEBUG.replace('android:exported="false"',
                                      'android:exported="true"'),
    'grant URI permissions': DEBUG.replace('android:exported="false"',
                                         'android:exported="false" android:grantUriPermissions="true"'),
    'wrong authority': DEBUG.replace('.r3c07p02"', '.other-authority"'),
    'cleartext application': DEBUG.replace('<application ',
                                          '<application android:usesCleartextTraffic="true" ', 1),
    'multiple providers': DEBUG.replace('    </application>',
                   '        <provider android:name=".other" android:exported="false" />\n    </application>'),
    'invalid XML': DEBUG[:len(DEBUG)//2],
}.items():
    require(mutant != DEBUG and not private_debug_provider(mutant),
            'manifest negative was accepted: '+label)
require('class ArtifactP02SignedFileProvider : ContentProvider()' in PROVIDER,
        'test signed-file provider missing')
for needle in ('File(app.applicationInfo.sourceDir)',
               'ParcelFileDescriptor.MODE_READ_ONLY',
               'if (mode != "r")', '/signed.apk', '/invalid.apk',
               'override fun query(', 'OpenableColumns.DISPLAY_NAME'):
    require(needle in PROVIDER, 'provider does not serve actual signed APK safely '+needle)
for forbidden in ('PackageInstaller', 'ACTION_VIEW', 'startActivity(', 'http://', 'https://',
                  'java.net.URL', 'HttpURLConnection', 'android:exported="true"'):
    require(forbidden not in PROVIDER, 'debug file provider is unsafe '+forbidden)
require(TEST.count('@Test') == 4, 'expected four actual instrumented P02A cases')
for needle in (
    'handlePickedFile', 'select(activity, "signed.apk")',
    'select(activity, "invalid.apk")', 'scenario.recreate()',
    'SIGNED APK FILES VERIFIED — NOT INSTALLED',
    'NOT Google Play proof', 'consent.isChecked).isFalse()',
    'install(ui).isEnabled).isFalse()',
    'ViewCompat.isAccessibilityHeading(it)',
    'TypedValue.COMPLEX_UNIT_SP, 26f',
):
    require(needle in TEST, 'real UI acceptance assertion missing '+needle)
for unsafe in ('PackageInstaller', 'install(ui).performClick()', 'adb shell pm install',
               'startActivity(Intent', 'writeSecureSetting'):
    require(unsafe not in TEST, 'P02A must be non-installing/non-browsing '+unsafe)
require(RUNNER.count('R3C07_P02A_CLASS=') == 1,
        'P02A device instrumentation graph ambiguous')
require(RUNNER.count('R3C07_P02A_API36_UX_RECEIPT.json') == 1,
        'P02A as-run receipt path ambiguous')
require('r3c07_p01_review_ux.txt' in RUNNER and
        "'^OK \\(5 tests\\)'" in RUNNER and
        'R3C06_P4_API36_READONLY_RECEIPT.json' in RUNNER,
        'inherited five-test UX and 51-test acceptance must remain')
require('r3c07_p02_receipt.py --log' in RUNNER and
        "'^OK \\(4 tests\\)'" in RUNNER,
        'four actual API36 signed-document tests not required')
require("'test_r3c07_p02_source.py'" in AGGREGATE,
        'P02A source gate must execute in targeted aggregate')
require(RECEIPT.is_file(), 'no P02A independent receipt gate')
result = subprocess.run([sys.executable, '-B', str(RECEIPT), '--selftest'],
                        cwd=ROOT, capture_output=True, text=True, timeout=20)
require(result.returncode == 0 and '1 positive, 9 negatives' in result.stdout,
        'P02A receipt negative tests failed: '+(result.stdout+result.stderr)[-1600:])
print('R3C07_P02A_SOURCE_CONTRACT_PASS: real signed content URI, private debug provider, four non-installing Android UI cases, lifecycle and receipt negatives')
