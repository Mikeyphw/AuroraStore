#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""P5 contract: opt-in-only existing R1D workflow; no green from missing OS or matrix evidence."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / '.github/workflows/aurora-r1d-emulator.yml'
R1D = WORKFLOW.read_text(encoding='utf-8')
RUNNER = (ROOT/'scripts/ci/r3c03_c02_emulator_ci.sh').read_text(encoding='utf-8')
CI = (ROOT/'scripts/ci/test_r3c04_full_import.py').read_text(encoding='utf-8')
SCRIPT = ROOT/'scripts/ci/r3c06_p5_manual_receipt.py'
NEGATIVE = ROOT/'scripts/ci/test_r3c06_p5_manual_receipt.py'

for token in ('workflow_dispatch:', 'r3c06_live_install:', 'r3c06_bundletool_matrix:',
              'type: boolean', 'default: false',
              'bundletool-all-1.18.3.jar',
              'a099cfa1543f55593bc2ed16a70a7c67fe54b1747bb7301f37fdfd6d91028e29',
              "R3C06_ALLOW_LIVE_INSTALL:", 'r3c06_p5_manual_receipt.py',
              'R3C06_P5_MANUAL_RECEIPT.json', 'git rev-parse HEAD',
              ':app:bundleVanillaDebug', 'platforms;android-36'):
    assert token in R1D, 'R3C06_P5_SOURCE_REFUSED missing exact workflow guard '+token
for token in ('R3C06_ALLOW_LIVE_INSTALL:-no', 'r3c06_api36_live_install.py',
              'r3c06_bundletool_matrix.py'):
    assert token in RUNNER, 'R3C06_P5_SOURCE_REFUSED inherited real tests lost '+token
assert 'test_r3c06_p5_source_contract.py' in CI, 'P5 missing from targeted source contract'
assert 'import android' not in SCRIPT.read_text(), 'P5 host receipt must remain pure Python'
assert 'aurora-r1d-emulator.yml' in WORKFLOW.as_posix(), 'workflow path mismatch'
assert R1D.count("name: Execute 40 R1D through R1G Android device tests and screenshots") == 1
assert R1D.count('name: Upload source-bound emulator receipt and offline test logs') == 1
assert R1D.count('uses: ReactiveCircus/android-emulator-runner@') == 1, 'duplicate emulator graph'
assert 'R3C06_ALLOW_LIVE_INSTALL' not in R1D.split('name: Build vanillaDebug application and instrumentation APKs')[0], 'non-opted default must be non-destructive'
assert SCRIPT.is_file() and NEGATIVE.is_file()
result=subprocess.run([sys.executable,'-B',str(NEGATIVE)],cwd=ROOT,
                      capture_output=True,text=True,timeout=30)
assert result.returncode==0, 'R3C06_P5_SOURCE_REFUSED negative regression failed: '+(result.stdout+result.stderr)[-2500:]
assert 'Ran 12 tests' in result.stderr, 'P5 acceptance negative test count stale'
print('R3C06_P5_SOURCE_CONTRACT_PASS: manual R1D opt-in, pinned bundletool, exact receipt, 12 negatives')
