#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""P05 independent actual API36 read-only evidence signoff.

Must run in the hosted emulator workflow AFTER P01 and P02-P04 receipt sealing.
Never converts isolated provider death, policy tests or opt-in absent installer
sessions into actual rollback, Play authentication, physical or release evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from r3c08_p01_receipt import assess as p01_assess
from r3c08_p02_p04_receipt import validate as p02_assess
from r3c07_p03b_receipt import verify as p03b_verify

SHA=re.compile(r'[0-9a-f]{40}\Z')
HEX64=re.compile(r'[0-9a-f]{64}\Z')
RUN=re.compile(r'[1-9][0-9]*\Z')
class Refused(ValueError):pass

def need(ok,why):
    if not ok:raise Refused('R3C08_P05_REFUSED: '+why)
def digest(raw):return hashlib.sha256(raw).hexdigest()
def duplicate_check(pairs):
    d={}
    for k,v in pairs:
        if k in d:raise Refused('duplicate JSON key: '+k)
        d[k]=v
    return d

def same(a,b):
    return json.dumps(a,sort_keys=True,separators=(',',':'))==json.dumps(b,sort_keys=True,separators=(',',':'))

def source_bound(doc,sha,run,tag):
    need(isinstance(doc,dict) and doc.get('overall')=='PASS',tag+' not PASS')
    need(doc.get('source_sha')==sha and str(doc.get('run_id'))==run,
         tag+' source SHA/run mismatch')
    need(doc.get('physical_device_qualified') is False and
         doc.get('release_qualified') is False,tag+' overclaims device/release')

def forbidden_elevations(doc,tag):
    for field in ('installation_qualified','publisher_authenticated','play_delivery_verified',
                  'actual_install_rollback_qualified','actual_provider_process_death_qualified',
                  'release_qualified','physical_device_qualified'):
        need(doc.get(field) is not True,tag+' falsely asserted '+field)

def read_bytes(root,name,limit=3_000_000):
    need('/' not in name and '\\' not in name and name not in ('.','..'), 'unsafe file identity')
    path=root/name
    need(path.is_file() and not path.is_symlink(), 'missing or symlink evidence '+name)
    size=path.stat().st_size
    need(0<size<=limit, 'invalid evidence size '+name)
    return path.read_bytes()

def require_completed_device_log(raw, count, label):
    """Independently verify each AndroidJUnitRunner start/completion pairing.

    A receipt's claimed test count and SHA digest are insufficient if that
    receipt can be edited together with a synthetic or truncated log.
    """
    need(isinstance(count,int) and not isinstance(count,bool) and 1<=count<=128,
         'invalid Android device-test count: '+label)
    try:
        log=raw.decode('utf-8')
    except UnicodeError as error:
        raise Refused('non-UTF8 Android test stream '+label) from error
    for bad in ('FAILURES!!!','INSTRUMENTATION_FAILED','Process crashed',
                'INSTRUMENTATION_CODE: 0','INSTRUMENTATION_STATUS_CODE: -1',
                'INSTRUMENTATION_STATUS_CODE: -2'):
        need(bad not in log,'failed Android instrumentation '+label+': '+bad)
    need(len(re.findall(r'^INSTRUMENTATION_CODE: -1\s*$',log,re.M))==1,
         'absent or duplicated Android success terminal '+label)
    suffix='test' if count==1 else 'tests'
    need(len(re.findall('^'+re.escape(f'OK ({count} {suffix})')+r'\s*$',log,re.M))==1,
         'AndroidJUnitRunner count mismatch '+label)
    names=re.findall(r'^INSTRUMENTATION_STATUS: test=([^\r\n]+)$',log,re.M)
    need(len(names)==2*count and len(set(names))==count and
         all(names.count(name)==2 for name in set(names)),
         'Android start/end test identity mismatch '+label)
    need(len(re.findall(r'^INSTRUMENTATION_STATUS_CODE: 1\s*$',log,re.M))==count and
         len(re.findall(r'^INSTRUMENTATION_STATUS_CODE: 0\s*$',log,re.M))>=count,
         'Android test-start/completion count mismatch '+label)
    for name in set(names):
        start=re.search(r'^INSTRUMENTATION_STATUS: test='+re.escape(name)+
                        r'\r?\nINSTRUMENTATION_STATUS_CODE: 1\s*$',log,re.M)
        end=re.search(r'^INSTRUMENTATION_STATUS: test='+re.escape(name)+
                      r'\r?\nINSTRUMENTATION_STATUS_CODE: 0\s*$',log,re.M)
        need(start is not None and end is not None and start.start()<end.start(),
             'unpaired Android start/completion '+label+': '+name)
    return len(set(names))

def read_json(root,name):
    raw=read_bytes(root,name,1_000_000)
    try: d=json.loads(raw.decode('utf-8'),object_pairs_hook=duplicate_check)
    except (UnicodeError,ValueError) as e:raise Refused('invalid JSON '+name+': '+str(e)) from e
    need(isinstance(d,dict), 'JSON receipt must be object '+name)
    return d,raw

def assess(root,sha,run):
    root=Path(root)
    need(root.is_dir() and not root.is_symlink(), 'missing as-run evidence directory')
    need(SHA.fullmatch(sha) is not None and RUN.fullmatch(run) is not None,'invalid source/run identity')
    proof={}
    # The receipt must equal a complete independent reconstruction using the
    # current source tree's real parsers, not unchecked assertions in JSON.
    p01_name='R3C08_P01_API36_REVOCATION_RECEIPT.json'
    observed,_=read_json(root,p01_name)
    rebuilt=p01_assess(read_bytes(root,'r3c08_p01_revoked_saf.txt'),sha,run)
    need(same(observed,rebuilt),'P01 actual Android log/receipt mismatch')
    source_bound(observed,sha,run,'P01');forbidden_elevations(observed,'P01')
    need(observed.get('actual_instrumentation_tests')==3,'missing 3 real P01 tests')
    proof['p01']=digest(read_bytes(root,p01_name))

    p02_name='R3C08_P02_P04_API36_ADVERSARIAL_RECEIPT.json'
    observed,_=read_json(root,p02_name)
    rebuilt=p02_assess(read_bytes(root,'r3c08_p02_p04_adversarial_ui.txt'),
        read_bytes(root,'r3c08_p02_p04_packages_before.txt',100_000),
        read_bytes(root,'r3c08_p02_p04_packages_after.txt',100_000),
        sha,run,read_bytes(root,'r3c08_p02_remote_provider_lifecycle.log',200_000))
    need(same(observed,rebuilt),'P02-P04 actual 21-test/log/provider/inventory receipt mismatch')
    source_bound(observed,sha,run,'P02-P04');forbidden_elevations(observed,'P02-P04')
    need(observed.get('actual_instrumentation_tests')==21 and
         isinstance(observed.get('isolated_provider_verified_restart_cycles'),int) and
         observed['isolated_provider_verified_restart_cycles']>=1 and
         observed.get('package_inventory_unchanged') is True,
         'missing actual P02-P04 test or provider/inventory proof')
    proof['p02_p04']=digest(read_bytes(root,p02_name))

    # Existing R3C07 real signed import/review proof is independently
    # reconstructed from its genuine PNGs and instrumentation stream.
    p03b_name='R3C07_P03B_API36_REAL_UI_RECEIPT.json'
    observed,_=read_json(root,p03b_name)
    pngs={name:read_bytes(root,name,12_000_000) for name in (
       'r3c07_p03b_provider_choice.png','r3c07_p03b_failed_retry.png',
       'r3c07_p03b_signed_review.png')}
    rebuilt=p03b_verify(read_bytes(root,'r3c07_p03b_real_ui.txt'),pngs,sha,run)
    need(same(observed,rebuilt),'P03B actual signed-file/UI/screenshot receipt mismatch')
    source_bound(observed,sha,run,'P03B');forbidden_elevations(observed,'P03B')
    need(observed.get('actual_instrumentation_tests')==5,'P03B five tests missing')
    proof['r3c07_p03b']=digest(read_bytes(root,p03b_name))

    # Earlier real read-only Android test logs are bound by their own
    # source/run receipts and the SHA256 of the uploaded execution logs.
    prev_name='R3C07_P02B_API36_RECEIPT.json'
    prev,_=read_json(root,prev_name);source_bound(prev,sha,run,'P02B')
    forbidden_elevations(prev,'P02B')
    need(prev.get('actual_instrumentation_tests')==5 and
         prev.get('actual_android_process_restarted') is True and
         prev.get('actual_android_system_font_changed_and_restored') is True and
         prev.get('read_only_ui') is True,
         'P02B source-bound real font/process tests absent')
    for key,filename in {'font':'r3c07_p02b_font_a11y_outcome.txt',
                         'seed':'r3c07_p02b_seed_consent.txt',
                         'reopen':'r3c07_p02b_reopen_after_force_stop.txt'}.items():
        need(prev.get('log_sha256',{}).get(key)==digest(read_bytes(root,filename)),
             'P02B hosted device log hash mismatch: '+key)
    phases=prev.get('per_phase_instrumentation')
    need(phases=={'font':3,'seed':1,'reopen':1},
         'P02B genuine phase count and names absent')
    for phase,filename in {'font':'r3c07_p02b_font_a11y_outcome.txt',
                           'seed':'r3c07_p02b_seed_consent.txt',
                           'reopen':'r3c07_p02b_reopen_after_force_stop.txt'}.items():
        require_completed_device_log(read_bytes(root,filename),phases[phase],
                                     'P02B-'+phase)
    need(isinstance(prev.get('seed_process_pid'),int) and
         isinstance(prev.get('reopened_process_pid'),int) and
         prev['seed_process_pid']>0 and prev['reopened_process_pid']>0 and
         prev['seed_process_pid']!=prev['reopened_process_pid'],
         'P02B recorded process restart PID not distinct')
    proof['r3c07_p02b']=digest(read_bytes(root,prev_name))

    c06_name='R3C06_P4_API36_READONLY_RECEIPT.json'
    c06,_=read_json(root,c06_name);source_bound(c06,sha,run,'R3C06')
    forbidden_elevations(c06,'R3C06')
    need(c06.get('executed_tests')==51 and c06.get('suite_count')==8 and
         c06.get('qualification_scope')=='API36_READONLY_DEVICE_TESTS_ONLY' and
         c06.get('real_android_installation_performed_by_this_gate') is False,
         'inherited real R3C06 suite count/scope mismatch')
    suites=c06.get('suites')
    need(isinstance(suites,dict) and len(suites)==8 and
         sum(int(x.get('tests_executed',0)) for x in suites.values())==51,
         'R3C06 as-run suite metadata/count mismatch')
    for key,suite in suites.items():
        need(isinstance(suite,dict) and isinstance(suite.get('log_file'),str),
             'invalid R3C06 suite '+str(key))
        filename=suite['log_file']
        need(re.fullmatch(r'[A-Za-z0-9_.-]{1,120}',filename) is not None,
             'untrusted R3C06 log path')
        need(suite.get('log_sha256')==digest(read_bytes(root,filename)),
             'R3C06 actual Android log hash mismatch '+str(key))
        require_completed_device_log(read_bytes(root,filename),
                                     suite['tests_executed'],'R3C06-'+str(key))
    need(c06.get('google_play_evidence_qualified_by_this_gate') is False and
         c06.get('real_android_installation_qualified') is False and
         c06.get('real_world_apkm_xapk_dialect_qualified') is False,
         'inherited R3C06 overclaimed Play, installer or real-world archive proof')
    proof['r3c06']=digest(read_bytes(root,c06_name))

    pair_name='R3C07_HF03_APK_SOURCE_RECEIPT.json'
    pair,_=read_json(root,pair_name);source_bound(pair,sha,run,'targeted APK pair')
    forbidden_elevations(pair,'targeted APK pair')
    need(pair.get('role')=='APK_INPUT_PROVENANCE_ONLY' and
         pair.get('mode') in ('EXACT_TARGETED_ARTIFACT','HOSTED_LOCAL_BUILD') and
         RUN.fullmatch(str(pair.get('targeted_run_id',''))) is not None,
         'source-pinned APK pair or successful targeted-run source missing')
    apk=pair.get('apk_pair')
    need(isinstance(apk,dict) and set(apk)=={'app','androidTest'} and
         apk['app'].get('signer_sha256')==apk['androidTest'].get('signer_sha256') and
         all(HEX64.fullmatch(x.get('sha256','')) is not None and
             HEX64.fullmatch(x.get('signer_sha256','')) is not None and
             isinstance(x.get('size'),int) and x['size']>0
             for x in apk.values()), 'APK pair digest or signer proof invalid')
    need(pair.get('instrumentation_qualified') is False and
         pair.get('installation_qualified') is False,
         'APK input provenance cannot certify instrumentation or OS installation')
    need(apk['app'].get('package')=='com.aurora.store.debug' and
         apk['androidTest'].get('package')=='com.aurora.store.debug.test' and
         apk['app'].get('filename')=='app.apk' and
         apk['androidTest'].get('filename')=='androidTest.apk',
         'matched APK input packages/roles missing')
    proof['targeted_apk_pair']=digest(read_bytes(root,pair_name))

    # NO final declaration from purely read-only testing, no matter how many
    # individual tests passed. Manual live DENY/ACCEPT, rollback/data retention,
    # broader provider-failure recovery and physical-device acceptance remain.
    pending=['actual_os_deny_accept_with_restoration',
             'actual_installer_rollback_and_app_data_retention',
             'concurrent_real_os_callback_replay',
             'third_party_provider_failure_matrix',
             'physical_android_device_acceptance']
    return {'phase':'R3C08_P05_SECURITY_SIGNOFF',
            'overall':'READ_ONLY_QUALIFIED_MANUAL_PENDING',
            'source_sha':sha,'run_id':run,'android_api':36,
            'targeted_run_id':str(pair['targeted_run_id']),
            'real_r3c08_readonly_device_tests':24,
            'independent_source_run_bound_evidence_sha256':proof,
            'isolated_test_provider_process_death_qualified':True,
            'package_inventory_unchanged':True,
            'actual_third_party_provider_death_qualified':False,
            'actual_os_install_deny_accept_qualified':False,
            'actual_installer_rollback_qualified':False,
            'actual_concurrent_os_callback_replay_qualified':False,
            'physical_device_qualified':False,
            'publisher_authenticated':False,
            'play_delivery_verified':False,
            'release_qualified':False,
            'final_security_signoff':False,
            'pending_manual_gates':pending}

def selftest():
    source='a'*40;run='123'
    good={'overall':'PASS','source_sha':source,'run_id':run,
          'physical_device_qualified':False,'release_qualified':False}
    source_bound(good,source,run,'fixture')
    forbidden_elevations(good,'fixture')
    negatives=[('wrong-sha',{**good,'source_sha':'b'*40},source,run),
               ('wrong-run',{**good,'run_id':'999'},source,run),
               ('bad-overall',{**good,'overall':'NOT_RUN'},source,run),
               ('fake-physical',{**good,'physical_device_qualified':True},source,run),
               ('fake-release',{**good,'release_qualified':True},source,run)]
    for name,value,sha,rid in negatives:
        try:source_bound(value,sha,rid,'fixture')
        except Refused:continue
        raise AssertionError('false signoff accepted: '+name)
    for field in ('installation_qualified','publisher_authenticated',
                  'play_delivery_verified','actual_install_rollback_qualified',
                  'actual_provider_process_death_qualified'):
        try:forbidden_elevations({**good,field:True},field)
        except Refused:continue
        raise AssertionError('false provenance accepted: '+field)
    need(not same({'x':1},{'x':True}),'typed JSON proof values collapse')
    try:json.loads('{"a":1,"a":2}',object_pairs_hook=duplicate_check)
    except Refused:pass
    else:raise AssertionError('duplicate JSON key accepted')
    # A forged receipt/log pair must not suffice: require actual JUnit START/END
    # records and the exact successful Android terminal from every inherited suite.
    name='securityPolicyRejectsUnsignedApk'
    sample=(f'INSTRUMENTATION_STATUS: test={name}\nINSTRUMENTATION_STATUS_CODE: 1\n'
            f'INSTRUMENTATION_STATUS: test={name}\nINSTRUMENTATION_STATUS_CODE: 0\n'
            'OK (1 test)\nINSTRUMENTATION_CODE: -1\n').encode()
    require_completed_device_log(sample,1,'positive-synthetic')
    corrupt={
        'missing-start':sample.replace(b'INSTRUMENTATION_STATUS_CODE: 1',b'INSTRUMENTATION_STATUS_CODE: 0'),
        'missing-completion':sample.replace(b'INSTRUMENTATION_STATUS_CODE: 0',b'INSTRUMENTATION_STATUS_CODE: 1'),
        'missing-terminal':sample.replace(b'INSTRUMENTATION_CODE: -1',b'INSTRUMENTATION_CODE: 1'),
        'wrong-count':sample.replace(b'OK (1 test)',b'OK (2 tests)'),
        'wrong-completed-identity':sample.replace(name.encode(),b'otherTest',1),
        'duplicate-identity':sample+f'INSTRUMENTATION_STATUS: test={name}\n'.encode(),
        'crash-marker':sample+b'Process crashed\n',
    }
    for label,altered in corrupt.items():
        try:require_completed_device_log(altered,1,label)
        except Refused:continue
        raise AssertionError('forged inherited device stream accepted: '+label)
    print('R3C08_P05_SIGNOFF_SELFTEST_PASS: 11 core adversarial negatives; '
          '7 additional Android device-stream mutations; final signoff locked')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--selftest',action='store_true')
    p.add_argument('--evidence-dir',type=Path)
    p.add_argument('--sha')
    p.add_argument('--run-id')
    p.add_argument('--output',type=Path)
    p.add_argument('--final',action='store_true',help='Refuse final acceptance until independently verified manual OS/rollback gates exist')
    a=p.parse_args()
    if a.selftest:selftest();return
    need(a.evidence_dir and a.sha and a.run_id and a.output, 'missing as-run evidence arguments')
    report=assess(a.evidence_dir,a.sha,a.run_id)
    if a.final:
        raise Refused('FINAL_UNQUALIFIED: read-only evidence cannot qualify real installer, '
                      'rollback, callback replay or physical device')
    need(a.output.resolve()!=a.evidence_dir.resolve(), 'output overwrites evidence directory')
    need(not a.output.exists() and not a.output.is_symlink(),
         'receipt output exists or is a symlink; refuse overwriting as-run evidence')
    need(a.output.parent.is_dir() and not a.output.parent.is_symlink(),
         'receipt output parent must exist and not be a symlink')
    with a.output.open('x',encoding='utf8') as output:
        output.write(json.dumps(report,sort_keys=True,indent=2)+'\n')
        output.flush()
        os.fsync(output.fileno())
    print('R3C08_P05_READONLY_EVIDENCE_PASS_MANUAL_GATES_PENDING sha='+a.sha+' run='+a.run_id)

if __name__=='__main__':
    try:main()
    except (Refused,OSError,ValueError,KeyError,TypeError) as e:
        print('R3C08_P05_SIGNOFF_REFUSED: '+str(e),file=sys.stderr)
        raise SystemExit(2)
