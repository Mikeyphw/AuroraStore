#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R3C07 P02B consolidated source contract with real negative mutations.

Only exact hosted API36 test execution can produce a device qualification.
"""
from __future__ import annotations
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
HOST=(ROOT/'scripts/ci/r3c07_p02b_api36.sh').read_text()
TEST=(ROOT/'app/src/androidTest/java/com/aurora/store/data/artifact/ArtifactReviewP02BDeviceTest.kt').read_text()
RECEIPT=(ROOT/'scripts/ci/r3c07_p02b_receipt.py').read_text()
RUNNER=(ROOT/'scripts/ci/r3c03_c02_emulator_ci.sh').read_text()
AGGREGATE=(ROOT/'scripts/ci/test_r3c04_full_import.py').read_text()

class Refused(AssertionError):pass

def require(ok:bool,why:str)->None:
    if not ok:raise Refused('R3C07_P02B_SOURCE_REFUSED: '+why)

def host_ok(host:str)->bool:
    code=host.splitlines()
    return (
        host.count('trap restore_font EXIT')==1 and
        host.count('adb shell am force-stop "$PACKAGE"')==2 and
        host.count('adb shell settings put system font_scale 2.0')==1 and
        'adb shell getprop ro.build.version.sdk' in host and
        'adb shell settings get system font_scale' in host and
        'adb shell settings delete system font_scale' in host and
        'R3C07_P02B_REFUSED_FONT_RESTORE' in host and
        '[[ "$RESTORED" == "$ORIGINAL_FONT" ]]' in host and
        host.count('instrument ')==4 and
        'realSystemFontScaleChangesActivityConfigurationWithoutConsent' in host and
        'verifiedConsentIsTransientBeforeHostForceStop' in host and
        'newProcessNeverRestoresVerifiedConsentOrSelectedBytes' in host and
        'accessibleNodeHierarchyExposesSectionsAndSafeActions' in host and
        'pendingRejectionAndPresentationFailureNeverAppearAsSuccess' in host and
        host.count('scripts/ci/r3c07_p02b_receipt.py')==1 and
        'INSTRUMENTATION_CODE: -1' in host and
        'FAILURES!!!' in host and
        'GITHUB_SHA=' not in host and
        'PackageInstaller.Session' not in host and
        'local upstream_rc=$?' in host and
        'local restore_failed=0' in host and
        'R3C07_P02B_FONT_RESTORE_VERIFIED_AFTER_FAILURE' in host and
        host.index('CHANGED=1\nadb shell settings put system font_scale 2.0') <
            host.index('DURING=')
    )

require(host_ok(HOST),'real font/process verification or restore path missing')
for name,old,new in (
    ('removed font setting','adb shell settings put system font_scale 2.0','echo skip'),
    ('removed restore trap','trap restore_font EXIT','true'),
    ('removed restored equality','[[ "$RESTORED" == "$ORIGINAL_FONT" ]]','true'),
    ('removed first force stop','adb shell am force-stop "$PACKAGE"','echo nothing'),
    ('removed receipt','scripts/ci/r3c07_p02b_receipt.py','scripts/ci/disabled.py'),
    ('swapped API level','ro.build.version.sdk','ro.build.version.codename'),
):
    changed=HOST.replace(old,new,1)
    require(changed!=HOST and not host_ok(changed),
            'unsafe host mutation escaped source gate: '+name)
require(TEST.count('@Test fun ')==5, 'must have five independent P02B device tests')
for required in (
    'configuration.fontScale).isAtLeast(1.4f)',
    'heading.createAccessibilityNodeInfo()',
    'node.isHeading',
    'node.isEnabled).isFalse()',
    'val accessibleLabel = node.text.toString()',
    'assertThat(accessibleLabel.equals(action.text.toString(), ignoreCase = true)).isTrue()',
    'ViewCompat.isAccessibilityHeading(it)',
    'accessibilityLiveRegion == View.ACCESSIBILITY_LIVE_REGION_POLITE',
    'ArtifactReviewPresentation.androidResult(state)',
    'label).doesNotContain("SUCCESS")',
    'getDeclaredMethod("handlePickedFile", Uri::class.java)',
    'content://com.aurora.store.debug.r3c07p02/signed.apk',
    'SIGNED APK FILES VERIFIED — NOT INSTALLED',
    'consent.isChecked = true',
    'install(ui).isEnabled).isTrue()',
    'install(ui).isEnabled).isFalse()',
    'reportPid("r3c07_p02b_seed_pid")',
    'reportPid("r3c07_p02b_reopen_pid")',
    'No verified files',
):
    require(required in TEST,'device test invariant absent: '+required)
for forbidden in ('install(ui).performClick()', 'ArtifactInstallSession.install(',
                  'startActivity(Intent.ACTION_VIEW', 'Settings.Secure.putString(',
                  'PackageInstaller.SessionParams('):
    require(forbidden not in TEST,'P02B automated test must not install/browse '+forbidden)
# HF01: a real API36 failure proved AppCompat uppercase accessibility
# node text is not an identity or missing-label failure. Case sensitivity
# must not be reintroduced, nor may the restore trap mask a prior failure.
require('assertThat(node.text.toString()).contains("Request Android installation")' not in TEST,
        'HF01: case-sensitive A11y node assertion reintroduced')
require('local restore_failed=0' in HOST and
        'echo R3C07_P02B_FONT_RESTORE_VERIFIED_AFTER_FAILURE' in HOST,
        'HF01: font cleanup must distinguish restored setting from original test failure')
for case, old, new in (
    ('case-only text comparison removed',
     'assertThat(accessibleLabel.equals(action.text.toString(), ignoreCase = true)).isTrue()',
     'assertThat(node.text.toString()).contains("Request Android installation")'),
    ('restore success marker removed',
     'echo R3C07_P02B_FONT_RESTORE_VERIFIED_AFTER_FAILURE',
     'echo R3C07_P02B_REFUSED_FONT_RESTORE'),
):
    selected = TEST if case.startswith('case') else HOST
    mutated = selected.replace(old, new, 1)
    require(old in selected and mutated != selected,
            'HF01 mutation anchor changed: '+case)
    if case.startswith('case'):
        require('assertThat(accessibleLabel.equals(action.text.toString(), ignoreCase = true)).isTrue()' not in mutated,
                'HF01 unsafe case-sensitive accessibility mutation accepted')
    else:
        require(not host_ok(mutated), 'HF01 unsafe restore-result mutation accepted')

require('actual_talkback_service_qualified' in RECEIPT and
        "'actual_talkback_service_qualified': False" in RECEIPT,
        'do not falsely qualify TalkBack')
require("'actual_os_approval_denial_qualified': False" in RECEIPT and
        "'installation_qualified': False" in RECEIPT,
        'do not falsely qualify Android OS approval')
require("'R3C07_P02B_API36_RECEIPT.json'" in HOST or
        'R3C07_P02B_API36_RECEIPT.json' in HOST,
        'missing P02B independent hosted receipt path')
require(RUNNER.count('bash scripts/ci/r3c07_p02b_api36.sh "$RUNNER" "$OUT"')==1,
        'P02B must run exactly once in inherited R1D graph')
require(RUNNER.index('R3C06_P4_API36_READONLY_RECEIPT.json') <
        RUNNER.index('R3C07_P01_API36_UX_RECEIPT.json') <
        RUNNER.index('R3C07_P02A_API36_UX_RECEIPT.json') <
        RUNNER.index('bash scripts/ci/r3c07_p02b_api36.sh'),
        'inherited R3C06/P01/P02A real device evidence reordered')
require(AGGREGATE.count("'test_r3c07_p02b_source.py'")==1 and
        AGGREGATE.index("'test_r3c07_p02_source.py'")<
        AGGREGATE.index("'test_r3c07_p02b_source.py'"),
        'P02B source gate is not in the aggregated historical test suite')
r=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/ci/r3c07_p02b_receipt.py'),'--selftest'],
                 cwd=ROOT,text=True,capture_output=True,timeout=25)
require(r.returncode==0 and '1 positive, 14 negatives' in r.stdout,
        'actual receipt negative test failed: '+(r.stdout+r.stderr)[-1300:])
# HF02: preserve JUnit's *actual* singular banner, which the previous
# fake-ADB harness had incorrectly spelled 'OK (1 tests)'. No weaker
# count checks are allowed for the seed and process-reopen acceptance.
require('local noun=\'tests\'' in HOST and
        'if [[ "$count" == 1 ]]; then noun=\'test\'; fi' in HOST and
        'grep -Fxq "OK ($count $noun)"' in HOST and
        'grep -Fxq "OK ($count tests)"' not in HOST,
        'HF02: host must validate singular/plural JUnit counts exactly')
require("suffix = 'test' if count == 1 else 'tests'" in RECEIPT and
        "('test' if n == 1 else 'tests')" in RECEIPT and
        "'incorrect plural one-test banner'" in RECEIPT,
        'HF02: as-run receipt and selftest must reject synthetic plural 1 tests')
for label,candidate in (
    ('host reverted', HOST.replace('grep -Fxq "OK ($count $noun)"',
                                   'grep -Fxq "OK ($count tests)"')),
    ('host accepts arbitrary count', HOST.replace('grep -Fxq "OK ($count $noun)"',
                                   'true # unsafe skip')),
    ('host singular branch removed', HOST.replace('if [[ "$count" == 1 ]]; then noun=\'test\'; fi',
                                                'true')),
):
    require(candidate!=HOST and not (
        'local noun=\'tests\'' in candidate and
        'if [[ "$count" == 1 ]]; then noun=\'test\'; fi' in candidate and
        'grep -Fxq "OK ($count $noun)"' in candidate and
        'grep -Fxq "OK ($count tests)"' not in candidate),
        'HF02 unsafe host count mutation accepted: '+label)
print('R3C07_P02B_CONSOLIDATED_SOURCE_PASS: five real API36 instrumented scenarios, actual font/process host, as-run receipt 14 negatives')
