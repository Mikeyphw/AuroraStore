#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R3C08 P01 real API36 test receipt. A synthetic self-test never qualifies Android.

This checks the exact AndroidJUnitRunner log from an opt-in test-APK-only grant
provider. The OS result and host SHA/run bind the uploaded evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

CLASS = 'com.aurora.store.data.artifact.ArtifactR3C08P01DeviceTest'
METHODS = (
    'realAndroidUriGrantAndRevocationRejectFreshOpens',
    'revokedDocumentIsRefusedByProductionImportWithoutConsent',
    'cancellingVerifiedSignedFileDiscardsSelectionAndAllConsent',
)
FLAGS = {
    'r3c08_grant_before': 'DENIED',
    'r3c08_grant_during': 'GRANTED',
    'r3c08_grant_after': 'DENIED',
}

class Refused(ValueError):
    pass

def require(test: bool, message: str) -> None:
    if not test:
        raise Refused(message)

def assess(raw: bytes, sha: str, run_id: str) -> dict:
    require(re.fullmatch(r'[0-9a-f]{40}', sha) is not None, 'invalid source commit')
    require(run_id.isdecimal() and int(run_id) > 0, 'missing hosted run identity')
    require(300 <= len(raw) <= 2_000_000, 'log absent or oversized')
    try:
        log = raw.decode('utf-8')
    except UnicodeError as error:
        raise Refused('log is not UTF-8') from error
    for bad in ('FAILURES!!!', 'INSTRUMENTATION_FAILED', 'INSTRUMENTATION_CODE: 0',
                'Process crashed', 'INSTRUMENTATION_STATUS_CODE: -1',
                'INSTRUMENTATION_STATUS_CODE: -2'):
        require(bad not in log, 'Android failure in log: '+bad)
    require(CLASS in log,'wrong Android instrumentation class')
    # AndroidJUnitRunner emits each test name twice: once with CODE 1 (start),
    # once with CODE 0 (finish). The independent sendStatus(0, grant flags)
    # contributes one additional successful code, but is NOT a test finish.
    # Explicit paired ordering prevents a duplicate start or lost finish from
    # being misrepresented as successful test evidence.
    events = re.findall(
        r'^INSTRUMENTATION_STATUS: test=([A-Za-z0-9_]+)\s*\n'
        r'INSTRUMENTATION_STATUS_CODE: ([01])\s*$', log, re.M)
    require(len(re.findall(r'^INSTRUMENTATION_STATUS: test=[A-Za-z0-9_]+\s*$',log,re.M))==6,
            'unexpected Android test marker count')
    require(len(events)==6,'R3C08 requires three test starts and three test finishes')
    require(set(method for method,code in events)==set(METHODS),
            'unexpected or missing actual Android test method')
    for method in METHODS:
        matching=[(i,code) for i,(name,code) in enumerate(events) if name==method]
        require(len(matching)==2 and [code for _,code in matching]==['1','0']
                and matching[0][0]<matching[1][0],
                'missing ordered Android start/completion pair: '+method)
    require(len(re.findall(r'^INSTRUMENTATION_STATUS_CODE: 1\s*$',log,re.M))==3,
            'unexpected Android test start count')
    for name,value in FLAGS.items():
        marker = 'INSTRUMENTATION_STATUS: '+name+'='+value
        require(len(re.findall('^'+re.escape(marker)+r'\s*$', log, re.M)) == 1,
                'missing verified Android grant/revocation status: '+name)
    require(len(re.findall(r'^OK \(3 tests\)\s*$', log, re.M)) == 1,
            'exact JUnit three-test count absent')
    require(len(re.findall(r'^INSTRUMENTATION_CODE: -1\s*$', log, re.M)) == 1,
            'final OS instrumentation success absent')
    require(len(re.findall(r'^INSTRUMENTATION_STATUS_CODE: 0\s*$', log, re.M)) == 4,
            'wrong number of real tests and independent grant-status events')
    return {
        'overall': 'PASS', 'phase': 'R3C08_P01_REAL_SAF_REVOCATION',
        'source_sha': sha, 'run_id': run_id, 'android_api': 36,
        'actual_instrumentation_tests': 3,
        'test_class': CLASS,
        'log_sha256': hashlib.sha256(raw).hexdigest(),
        'actual_os_uri_grant_and_revocation_tested': True,
        'fresh_open_after_revocation_rejected': True,
        'production_importer_revoked_document_refusal_tested': True,
        'explicit_cancel_resets_signed_selection_tested': True,
        'already_open_fd_revocation_guaranteed': False,
        'installation_qualified': False, 'publisher_authenticated': False,
        'real_talkback_service_qualified': False,
        'physical_device_qualified': False, 'release_qualified': False,
    }

def example() -> bytes:
    block = ''.join('INSTRUMENTATION_STATUS: test='+m+'\nINSTRUMENTATION_STATUS_CODE: 1\n' +
                    'INSTRUMENTATION_STATUS: test='+m+'\nINSTRUMENTATION_STATUS_CODE: 0\n'
                    for m in METHODS)
    flags = ''.join('INSTRUMENTATION_STATUS: '+k+'='+v+'\n' for k,v in FLAGS.items())
    return (('INSTRUMENTATION_STATUS: class='+CLASS+'\n'+block+flags+
             'INSTRUMENTATION_STATUS_CODE: 0\nOK (3 tests)\n'
             'INSTRUMENTATION_CODE: -1\n')+'#'*200+'\n').encode()

def selftest() -> None:
    good=example()
    assess(good,'a'*40,'123')
    mutations = {
        'wrong-source': (good,'A'*40,'123'),
        'wrong-run': (good,'a'*40,'0'),
        'missing-test': (good.replace(METHODS[1].encode(),b'wrongMethod'),'a'*40,'123'),
        'duplicate-test': (good+('INSTRUMENTATION_STATUS: test='+METHODS[0]+'\nINSTRUMENTATION_STATUS_CODE: 1\n').encode(),'a'*40,'123'),
        'missing-grant-status': (good.replace(b'r3c08_grant_during=GRANTED',b'r3c08_grant_during=DENIED'),'a'*40,'123'),
        'duplicate-grant-status': (good+b'INSTRUMENTATION_STATUS: r3c08_grant_after=DENIED\n','a'*40,'123'),
        'wrong-count': (good.replace(b'OK (3 tests)',b'OK (2 tests)'),'a'*40,'123'),
        'wrong-junit-suffix': (good.replace(b'OK (3 tests)',b'OK (3 test)'),'a'*40,'123'),
        'absent-os-terminal': (good.replace(b'INSTRUMENTATION_CODE: -1',b'no terminal'),'a'*40,'123'),
        'duplicate-os-terminal': (good+b'INSTRUMENTATION_CODE: -1\n','a'*40,'123'),
        'failed-test': (good+b'FAILURES!!!\n','a'*40,'123'),
        'missing-status-code': (good.replace(b'INSTRUMENTATION_STATUS_CODE: 0',b'bad code',1),'a'*40,'123'),
        'malformed-utf8': (good+b'\xff','a'*40,'123'),
        'missing-finish': (good.replace((b'INSTRUMENTATION_STATUS: test='+METHODS[0].encode()+b'\nINSTRUMENTATION_STATUS_CODE: 0'),b'INSTRUMENTATION_STATUS: test=other\nINSTRUMENTATION_STATUS_CODE: 0',1),'a'*40,'123'),
        'duplicate-start': (good.replace((b'INSTRUMENTATION_STATUS: test='+METHODS[1].encode()+b'\nINSTRUMENTATION_STATUS_CODE: 0'),(b'INSTRUMENTATION_STATUS: test='+METHODS[1].encode()+b'\nINSTRUMENTATION_STATUS_CODE: 1'),1),'a'*40,'123'),
        'finish-before-start': (good.replace((b'INSTRUMENTATION_STATUS: test='+METHODS[2].encode()+b'\nINSTRUMENTATION_STATUS_CODE: 1'),b'INSTRUMENTATION_STATUS: test='+METHODS[2].encode()+b'\nINSTRUMENTATION_STATUS_CODE: 0',1),'a'*40,'123'),
        'duplicate-terminal-test': (good + (b'INSTRUMENTATION_STATUS: test='+METHODS[0].encode()+b'\nINSTRUMENTATION_STATUS_CODE: 0\n'),'a'*40,'123'),
        'out-of-order-pair': (good.replace((b'INSTRUMENTATION_STATUS: test='+METHODS[0].encode()+b'\nINSTRUMENTATION_STATUS_CODE: 1\nINSTRUMENTATION_STATUS: test='+METHODS[0].encode()+b'\nINSTRUMENTATION_STATUS_CODE: 0'),(b'INSTRUMENTATION_STATUS: test='+METHODS[0].encode()+b'\nINSTRUMENTATION_STATUS_CODE: 0\nINSTRUMENTATION_STATUS: test='+METHODS[0].encode()+b'\nINSTRUMENTATION_STATUS_CODE: 1'),1),'a'*40,'123'),
    }
    for label,(raw,sha,run) in mutations.items():
        try:
            assess(raw,sha,run)
        except Refused:
            continue
        raise AssertionError('unsafe evidence mutation accepted: '+label)
    print('R3C08_P01_RECEIPT_SELFTEST_PASS: 1 synthetic parser positive, '+str(len(mutations))+' negatives (not device evidence)')

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument('--selftest',action='store_true')
    cli.add_argument('--log',type=Path)
    cli.add_argument('--sha')
    cli.add_argument('--run-id')
    cli.add_argument('--output',type=Path)
    args=cli.parse_args()
    if args.selftest:
        selftest();return
    require(args.log is not None and args.sha and args.run_id and args.output is not None,
            'missing live receipt arguments')
    require(args.log.is_file() and not args.log.is_symlink() and
            args.log.name == 'r3c08_p01_revoked_saf.txt', 'wrong or missing as-run log')
    require(args.output.resolve()!=args.log.resolve(), 'output cannot overwrite log')
    document=assess(args.log.read_bytes(),args.sha,args.run_id)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(document,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print('R3C08_P01_REAL_API36_REVOCATION_RECEIPT_PASS sha='+args.sha+' run='+args.run_id)

if __name__=='__main__':
    try:main()
    except (Refused, OSError, ValueError, AssertionError) as err:
        print('R3C08_P01_RECEIPT_REFUSED: '+str(err),file=sys.stderr)
        raise SystemExit(2)
