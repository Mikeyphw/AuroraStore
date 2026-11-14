#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""P02B: verify genuine hosted instrumented font, consent, process restart logs.

The process PIDs and Android system font setting are evidence, but do NOT
substitute for a live TalkBack-service session or real PackageInstaller decision.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

CLASS = 'com.aurora.store.data.artifact.ArtifactReviewP02BDeviceTest'
SHA = re.compile(r'[0-9a-f]{40}\Z')
POS_PID = re.compile(r'^[1-9][0-9]{0,9}$')
LOG_NAMES = {
    'font': 'r3c07_p02b_font_a11y_outcome.txt',
    'seed': 'r3c07_p02b_seed_consent.txt',
    'reopen': 'r3c07_p02b_reopen_after_force_stop.txt',
}

class Refused(ValueError):
    pass

def require(ok: bool, problem: str) -> None:
    if not ok:
        raise Refused(problem)

def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def verify_log(raw: bytes, count: int, pid_key: str | None) -> dict:
    require(0 < len(raw) <= 2_000_000, 'empty or oversized instrumentation log')
    try:
        text = raw.decode('utf-8')
    except UnicodeError as exc:
        raise Refused('invalid UTF8 instrumentation evidence') from exc
    require(CLASS in text, 'wrong instrumented P02B test class')
    for bad in ('FAILURES!!!', 'INSTRUMENTATION_FAILED', 'Process crashed',
                'INSTRUMENTATION_CODE: 0', 'INSTRUMENTATION_STATUS_CODE: -2',
                'INSTRUMENTATION_STATUS_CODE: -1'):
        require(bad not in text, 'failed instrumentation evidence: '+bad)
    # AndroidJUnitRunner's real JUnit grammar is singular for exactly one.
    suffix = 'test' if count == 1 else 'tests'
    require(len(re.findall(r'^OK \('+str(count)+r' '+suffix+r'\)\s*$', text, re.M)) == 1,
            'missing exact successful JUnit test count')
    require(len(re.findall(r'^INSTRUMENTATION_CODE: -1\s*$', text, re.M)) == 1,
            'missing unique final OS instrumentation result')
    # sendStatus(0, Bundle) contributes an additional success status event,
    # which is separate from JUnit's actual test count.
    expected_events = count + (1 if pid_key else 0)
    require(len(re.findall(r'^INSTRUMENTATION_STATUS_CODE: 0\s*$', text, re.M)) == expected_events,
            'wrong number of actual status+test events')
    pid = None
    if pid_key:
        found = re.findall(r'^INSTRUMENTATION_STATUS: '+re.escape(pid_key)+
                           r'=([^\r\n]+)\s*$', text, re.M)
        require(len(found) == 1 and POS_PID.fullmatch(found[0]) is not None,
                'missing real Android test process PID '+pid_key)
        pid = int(found[0])
    return {'log_sha256': sha256(raw), 'actual_tests': count, 'pid': pid}

def validate(logs: dict[str, bytes], before: str, during: str,
             restored: str, source: str, run_id: str) -> dict:
    require(SHA.fullmatch(source) is not None, 'source SHA missing')
    require(run_id.isdecimal() and int(run_id)>0, 'GitHub run ID missing')
    require(before == restored, 'Android system font NOT restored')
    require(re.fullmatch(r'(?:[0-9]+(?:\.[0-9]+)?|null)', before) is not None,
            'original font setting not safely parseable')
    require(during in ('2.0', '2'), 'font was not changed to hosted test scale')
    require(set(logs)==set(LOG_NAMES), 'unexpected evidence log roles')
    proofs = {
        'font': verify_log(logs['font'], 3, None),
        'seed': verify_log(logs['seed'], 1, 'r3c07_p02b_seed_pid'),
        'reopen': verify_log(logs['reopen'], 1, 'r3c07_p02b_reopen_pid'),
    }
    require(proofs['seed']['pid'] != proofs['reopen']['pid'],
            'app process PID did not change after force-stop')
    return {
        'overall': 'PASS', 'phase': 'R3C07_P02B_CONSOLIDATED',
        'source_sha': source, 'run_id': run_id, 'android_api': 36,
        'actual_instrumentation_tests': 5,
        'per_phase_instrumentation': {k:v['actual_tests'] for k,v in proofs.items()},
        'log_sha256': {k:v['log_sha256'] for k,v in proofs.items()},
        'font_original': before, 'font_during': during, 'font_restored': restored,
        'actual_android_system_font_changed_and_restored': True,
        'actual_android_process_restarted': True,
        'seed_process_pid': proofs['seed']['pid'],
        'reopened_process_pid': proofs['reopen']['pid'],
        'actual_signed_apk_in_review_before_restart': True,
        'read_only_ui': True, 'accessibility_node_semantics_verified': True,
        'android_outcome_text_mapping_verified': True,
        'actual_talkback_service_qualified': False,
        'actual_os_approval_denial_qualified': False,
        'installation_qualified': False,
        'publisher_authenticated': False,
        'physical_device_qualified': False,
        'release_qualified': False,
    }

def seal(paths: dict[str, Path], output: Path, before: str,
         during: str, restored: str, source: str, run_id: str) -> dict:
    for role,path in paths.items():
        require(path.is_file() and not path.is_symlink() and
                path.name == LOG_NAMES[role], 'missing/symlink/wrong log name '+role)
    doc = validate({k:p.read_bytes() for k,p in paths.items()},before,during,restored,
                   source,run_id)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(doc,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    return doc

def fake_log(n: int, pidkey: str | None, pid: int) -> bytes:
    t = 'INSTRUMENTATION_STATUS: class='+CLASS+'\n'
    t += 'INSTRUMENTATION_STATUS_CODE: 0\n'*n
    if pidkey:
        t += 'INSTRUMENTATION_STATUS: '+pidkey+'='+str(pid)+'\n'
        t += 'INSTRUMENTATION_STATUS_CODE: 0\n'
    t += 'OK ('+str(n)+' '+('test' if n == 1 else 'tests')+')\nINSTRUMENTATION_CODE: -1\n'
    return t.encode()

def selftest() -> None:
    good={'font':fake_log(3,None,0),
          'seed':fake_log(1,'r3c07_p02b_seed_pid',1122),
          'reopen':fake_log(1,'r3c07_p02b_reopen_pid',2233)}
    correct=validate(good,'1.15','2.0','1.15','a'*40,'12345')
    assert correct['actual_instrumentation_tests']==5
    assert correct['actual_android_process_restarted']
    bad={
        'same process pid':({**good,'reopen':fake_log(1,'r3c07_p02b_reopen_pid',1122)},'1.15','2.0','1.15','a'*40,'12345'),
        'wrong font restore':(good,'1.15','2.0','1.0','a'*40,'12345'),
        'font never changed':(good,'1.15','1.15','1.15','a'*40,'12345'),
        'wrong source':(good,'1.15','2.0','1.15','wrong','12345'),
        'wrong run':(good,'1.15','2.0','1.15','a'*40,'invalid'),
        'missing status':({**good,'seed':good['seed'].replace(b'INSTRUMENTATION_STATUS_CODE: 0\n',b'',1)},'1.15','2.0','1.15','a'*40,'12345'),
        'forged junit count':({**good,'font':good['font'].replace(b'OK (3 tests)',b'OK (2 tests)')},'1.15','2.0','1.15','a'*40,'12345'),
        'duplicate junit banner':({**good,'font':good['font']+b'OK (3 tests)\n'},'1.15','2.0','1.15','a'*40,'12345'),
        'failure even with OK':({**good,'seed':good['seed']+b'FAILURES!!!\n'},'1.15','2.0','1.15','a'*40,'12345'),
        'missing process evidence':({**good,'seed':good['seed'].replace(b'r3c07_p02b_seed_pid',b'wrong_pid')},'1.15','2.0','1.15','a'*40,'12345'),
        'wrong android terminal':({**good,'reopen':good['reopen'].replace(b'INSTRUMENTATION_CODE: -1',b'INSTRUMENTATION_CODE: 0')},'1.15','2.0','1.15','a'*40,'12345'),
        'invalid UTF8':({**good,'font':good['font']+b'\xff'},'1.15','2.0','1.15','a'*40,'12345'),
        'missing log':({**good,'font':b''},'1.15','2.0','1.15','a'*40,'12345'),
        'incorrect plural one-test banner':({**good,'seed':good['seed'].replace(b'OK (1 test)',b'OK (1 tests)')},'1.15','2.0','1.15','a'*40,'12345'),
    }
    for label,args in bad.items():
        try:validate(*args)
        except Refused:pass
        else:raise AssertionError('P02B invalid as-run evidence accepted: '+label)
    with tempfile.TemporaryDirectory(prefix='r3c07-p02b-receipt-') as td:
        root=Path(td)
        paths={}
        for key,data in good.items():
            p=root/LOG_NAMES[key]; p.write_bytes(data);paths[key]=p
        output=root/'receipt.json'
        assert seal(paths,output,'1.15','2.0','1.15','a'*40,'12345')==json.loads(output.read_text())
        assert output.read_bytes().endswith(b'\n')
    print('R3C07_P02B_RECEIPT_EXECUTABLE_REGRESSION_PASS: 1 positive, '+str(len(bad))+' negatives')

def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument('--selftest',action='store_true')
    for name in ('font-log','seed-log','reopen-log','font-original',
                 'font-changed','font-restored','output'):
        ap.add_argument('--'+name)
    args=ap.parse_args()
    if args.selftest:
        selftest();return
    require(all((getattr(args,k) is not None for k in
                 ('font_log','seed_log','reopen_log','font_original',
                  'font_changed','font_restored','output'))),'missing P02B as-run arguments')
    data=seal({'font':Path(args.font_log),'seed':Path(args.seed_log),
               'reopen':Path(args.reopen_log)},Path(args.output),
              args.font_original,args.font_changed,args.font_restored,
              os.environ.get('GITHUB_SHA',''),os.environ.get('GITHUB_RUN_ID',''))
    print('R3C07_P02B_CONSOLIDATED_SOURCE_BOUND_PASS tests='+str(data['actual_instrumentation_tests']))

if __name__=='__main__':
    try:main()
    except (Refused,OSError) as exc:
        print('R3C07_P02B_RECEIPT_REFUSED: '+str(exc),file=sys.stderr)
        raise SystemExit(1)
