#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R3C06 P4 source gate: acceptance receipts and host-driver negatives.

Designed for targeted CI (no Android runtime). Do not count this PASS as API36.
"""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / 'scripts/ci'
RUNNER = CI / 'r3c03_c02_emulator_ci.sh'

class Refused(Exception): pass

def require(ok, message):
    if not ok: raise Refused(message)

def read(p):
    require(p.is_file(), 'missing ' + str(p))
    return p.read_text(encoding='utf-8')

runner = read(RUNNER)
receipt = read(CI / 'r3c06_readonly_receipt.py')
live = read(CI / 'r3c06_api36_live_install.py')
bundle = read(CI / 'r3c06_bundletool_matrix.py')
tests = read(CI / 'test_r3c06_p4_python.py')
full = read(CI / 'test_r3c04_full_import.py')
for token in ('r3c06_readonly_receipt.py', 'R3C06_P4_API36_READONLY',
              'R3C06_ALLOW_LIVE_INSTALL', 'ArtifactRealSignedArchiveDeviceTest'):
    require(token in runner, 'missing previous gate/P4 append: ' + token)
require(runner.index('r3c06_readonly_receipt.py') < runner.index('# REAL OS installation is explicitly opt-in'),
        'read-only measured receipt must precede optionally destructive test')
for token in ('read-only', 'real_android_installation_qualified',
              'bundletool_device_matrix_qualified', 'source_sha', 'run_id',
              'log_sha256', 'EXPECTED_COUNT', 'android_api == 36'):
    require(token in receipt.lower() if token == 'read-only' else token in receipt,
            'read-only measured receipt missing: ' + token)
require('fixture_present(adb)' in live and
        "'pm', 'list', 'packages', '--user', '0'" in live and
        "'package:' + AURORA in records" in live and
        "return 'package:' + TARGET in records" in live and
        "'pm','path',TARGET" not in live and
        "n.get('package') in INSTALLER_PACKAGES" in live and
        'R3C06_ALLOW_LIVE_INSTALL' in live and
        "run(['git','rev-parse','HEAD'])==source_sha" in live,
        'live install inventory/OS consent checks were weakened')
require('stage_fixture(adb, runner, fixture, evidence)' in live and
        'cleanup_fixture(adb,runner,fixture_digest,evidence)' in live and
        "TEST_CLASS + '#seedSignedFixtureIntoPrivateCache'" in live and
        "TEST_CLASS + '#removeSignedFixtureFromPrivateCache'" in live and
        "'run-as'" not in live and
        'private_app_uid_staging_verified' in live,
        'R3C06 HF04 private app-owned fixture handoff/cleanup missing')
require('run_fixture_instrumentation(' in live and
        'check_single_instrumentation_result(' in live and
        'INSTRUMENTATION_STATUS: ' in live and
        'INSTRUMENTATION_CODE: -1' in live and
        'r3c06-live-install' in live and
        'original acceptance failure:' in live and
        'instrumentation_status_proof_verified' in live,
        'R3C06 HF05 structured evidence or failed-run diagnostics missing')
require('def qualifies_variant(' in bundle and
        'qualifies_variant(results' in bundle and
        "candidate.get('status') == 'SIGNED'" in bundle and
        "'REFUSED' or" not in bundle,
        'bundletool false acceptance is still present')
require('test_r3c06_p4_qualification.py' in full and
        tests.count('def test_') >= 24,
        'targeted CI does not reach the new P4 tests')
require((ROOT/'docs/R3C06_P4_QUALIFICATION.md').is_file(), 'qualification documentation missing')
check = subprocess.run([sys.executable, '-B', str(CI/'test_r3c06_p4_python.py')],
                       cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       text=True, timeout=30)
require(check.returncode == 0,
        'offline regression tests failed: ' + (check.stdout+check.stderr)[-5000:])
print('R3C06_P4_SOURCE_AND_PYTHON_PASS: twenty-four measured host-driver regressions; device qualification still pending')
