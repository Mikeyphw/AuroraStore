#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R3C07 HF02 regression: parse and EXECUTE the real CI receipt heredoc.

May be run alone with an explicit runner path, or exec-compiled by the existing
R3C04 aggregate. Uses synthetic identities exclusively. No device install.
"""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

R3C07_HF02_START = "<<'R3C07_RECEIPT_PY'"
R3C07_HF02_END = 'R3C07_RECEIPT_PY'
R3C07_HF02_SYNTHETIC_SHA = '0123456789abcdef0123456789abcdef01234567'
R3C07_HF02_SYNTHETIC_RUN = '123456789'


def r3c07_hf02_extract(path: Path) -> str:
    text = path.read_text(encoding='utf-8')
    if text.count(R3C07_HF02_START) != 1:
        raise AssertionError('must find exactly one quoted R3C07 receipt heredoc')
    after = text.split(R3C07_HF02_START, 1)[1]
    if after.count('\n'+R3C07_HF02_END+'\n') != 1:
        raise AssertionError('receipt terminator must occupy one exact line')
    src = after.split('\n'+R3C07_HF02_END+'\n', 1)[0]
    if not src.startswith('\n'):
        raise AssertionError('heredoc must start on the next line')
    return src[1:]


def r3c07_hf02_check_code(code: str) -> None:
    ast.parse(code, filename='R3C07_RECEIPT_PY', mode='exec')
    with tempfile.TemporaryDirectory(prefix='r3c07-hf02-receipt-') as td:
        out = Path(td) / 'actual-receipt.json'
        env = {**os.environ, 'GITHUB_SHA': R3C07_HF02_SYNTHETIC_SHA,
               'GITHUB_RUN_ID': R3C07_HF02_SYNTHETIC_RUN}
        cp = subprocess.run([sys.executable, '-B', '-', str(out)], input=code,
                            text=True, capture_output=True, env=env, timeout=12,
                            check=False)
        if cp.returncode != 0:
            raise AssertionError('real inline code execution failed: '+(cp.stderr+cp.stdout)[-1200:])
        if not out.is_file():
            raise AssertionError('real inline code wrote no receipt')
        raw = out.read_bytes()
        if not raw.endswith(b'\n') or raw.endswith(b'\n\n'):
            raise AssertionError('receipt must end in one LF')
        actual = json.loads(raw.decode('utf-8'))
        expected = {
            'overall': 'PASS', 'source_sha': R3C07_HF02_SYNTHETIC_SHA,
            'run_id': R3C07_HF02_SYNTHETIC_RUN, 'android_api': 36,
            'actual_instrumentation_tests': 5, 'read_only_ui': True,
            'installation_qualified': False, 'publisher_authenticated': False,
            'physical_device_qualified': False, 'release_qualified': False,
        }
        if actual != expected:
            raise AssertionError('receipt identity/count/scope mismatch: '+repr(actual))


def r3c07_hf02_run(path: Path) -> None:
    good = r3c07_hf02_extract(path)
    r3c07_hf02_check_code(good)
    # An executable negative: exactly the old two-line literal must fail syntax.
    literal = "+'\\n',encoding='utf-8'"
    if good.count(literal) != 1:
        raise AssertionError('escaped LF line not found exactly once')
    bad = good.replace(literal, "+'\n',encoding='utf-8'", 1)
    try:
        ast.parse(bad, filename='R3C07_RECEIPT_PY_BROKEN', mode='exec')
    except SyntaxError:
        pass
    else:
        raise AssertionError('broken literal negative was not rejected')
    print('R3C07_P01_HF02_INLINE_PYTHON_REGRESSION_PASS: executed real heredoc, 5/5 JSON contract, malformed negative rejected')


# The existing aggregate calls this by exec(compile(...)); its __file__ is the
# aggregate script. Explicit argv is only accepted for direct invocation.
if __name__ == '__main__' and len(sys.argv) > 1:
    if len(sys.argv) != 2:
        raise SystemExit('R3C07_HF02_REFUSED: expected one runner path')
    r3c07_hf02_run(Path(sys.argv[1]))
else:
    r3c07_hf02_run(Path(__file__).resolve().parents[2] / 'scripts/ci/r3c03_c02_emulator_ci.sh')
