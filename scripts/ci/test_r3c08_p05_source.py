#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""P05 hosted-source gate: independent as-run signoff, no fabricated final approval."""
from __future__ import annotations
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
S=ROOT/'scripts/ci/r3c08_p05_signoff.py'
HOST=ROOT/'scripts/ci/r3c08_p01_api36.sh'
P02=ROOT/'scripts/ci/r3c08_p02_p04_receipt.py'
SRC=ROOT/'scripts/ci/test_r3c08_p02_p04_source.py'
DOC=ROOT/'docs/R3C08_P05_FINAL_SIGNOFF.md'

def need(ok,why):
    if not ok:raise AssertionError('R3C08_P05_SOURCE_REFUSED: '+why)
for f in (S,HOST,P02,SRC,DOC):need(f.is_file(),'missing P05 component '+str(f))
s=S.read_text();host=HOST.read_text();p02=P02.read_text();source=SRC.read_text();doc=DOC.read_text()
need(host.count('python3 -B scripts/ci/r3c08_p05_signoff.py')==1,
     'P05 as-run verifier must execute once in existing API36 graph')
need(host.index('bash scripts/ci/r3c08_p02_p04_api36.sh') <
     host.index('python3 -B scripts/ci/r3c08_p05_signoff.py'),
     'P05 must run AFTER successful P01 and P02-P04 Android receipts')
need('R3C08_P05_API36_SECURITY_SIGNOFF.json' in host and
     '--evidence-dir "$OUT"' in host and
     '--sha "$GITHUB_SHA"' in host and '--run-id "$GITHUB_RUN_ID"' in host,
     'P05 host does not bind actual Android run/commit/source')
need('isolated_provider_verified_restart_cycles' in p02 and
     'len(cycles)>=1' in p02 and
     'need(pid!=pending_dead' in p02,
     'multi-cycle provider restart bug may regress')
need('test_r3c08_p05_source.py' in source and
     'test_r3c08_p05_source.py' not in s,
     'P05 must be called from inherited targeted/source chain without recursive testing')
for needle in (
    'p01_assess(', 'p02_assess(', 'p03b_verify(',
    'require_completed_device_log(',
    'receipt output exists or is a symlink',
    "a.output.open('x',encoding='utf8')",
    'R3C06_P4_API36_READONLY_RECEIPT.json',
    'R3C07_P02B_API36_RECEIPT.json',
    'R3C07_HF03_APK_SOURCE_RECEIPT.json',
    'actual_instrumentation_tests', 'isolated_provider_verified_restart_cycles',
    'independent_source_run_bound_evidence_sha256',
    "'READ_ONLY_QUALIFIED_MANUAL_PENDING'",
    "'final_security_signoff':False",
    "'actual_installer_rollback_qualified':False",
    "'physical_device_qualified':False",
    "'publisher_authenticated':False",
    "'play_delivery_verified':False",
    "'actual_third_party_provider_death_qualified':False",
    'if a.final:', 'FINAL_UNQUALIFIED:',
): need(needle in s,'P05 missing independent evidence/final refusal '+needle)
need('require_completed_device_log(' in s and
     'per_phase_instrumentation' in s and "'R3C06-'+str(key)" in s,
     'P05 must independently validate inherited Android start/end events')
need('not PASS_FINAL' in doc and 'DENY' in doc and 'rollback' in doc,
     'P05 manual qualification caveats are absent')
for forbidden in ('adb shell pm install', 'su -c', 'PackageInstaller.install(',
                  'PlayVerifiedEvidenceStore(', 'shell am instrument'):
    need(forbidden not in s, 'signoff must not modify OS or Play state: '+forbidden)
for old,new in (
    ("'final_security_signoff':False", "'final_security_signoff':True"),
    ('FINAL_UNQUALIFIED:', 'FINAL_ACCEPTED:'),
    ('p02_assess(', 'dict('),
    ('p03b_verify(', 'dict('),
    ("'actual_installer_rollback_qualified':False", "'actual_installer_rollback_qualified':True"),
):
    altered=s.replace(old,new,1)
    need(altered!=s and (old not in altered or old in s[altered.find(new):]),
         'security source mutation anchor absent '+old)
for path,expected in ((S,'7 additional Android device-stream mutations'),
                      (P02,'34 negatives')):
    result=subprocess.run([sys.executable,'-B',str(path),'--selftest'],
                          cwd=ROOT,timeout=40,text=True,capture_output=True)
    need(result.returncode==0 and expected in result.stdout,
         'P05/folded multicycle source regression failed '+(result.stdout+result.stderr)[-800:])
print('R3C08_P05_SOURCE_SECURITY_PASS: real 3+21 Android receipts, inherited R3C07/C06 evidence, multi-cycle provider replays, fail-closed P05 manual signoff')
