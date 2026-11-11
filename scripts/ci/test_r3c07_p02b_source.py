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
        'PackageInstaller.Session' not in host
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
require(r.returncode==0 and '1 positive, 13 negatives' in r.stdout,
        'actual receipt negative test failed: '+(r.stdout+r.stderr)[-1300:])
print('R3C07_P02B_CONSOLIDATED_SOURCE_PASS: five real API36 instrumented scenarios, actual font/process host, as-run receipt 13 negatives')
