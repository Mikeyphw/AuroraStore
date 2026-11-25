#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent R3C07 P04 actual system approval/denial evidence handoff.

Consumes only the explicitly opted-in, existing R3C06 real PackageInstaller
fixture gate; never stages, installs, or fabricates an Android outcome.
"""
from __future__ import annotations
import argparse,json,os,pathlib,re,sys,tempfile
import r3c06_p5_manual_receipt as upstream
class Refused(ValueError):pass

def require(ok,what):
    if not ok:raise Refused('R3C07_P04_REFUSED: '+what)

def verify(live:dict,manual:dict,sha:str,run:str)->dict:
    require(bool(re.fullmatch(r'[a-f0-9]{40}',sha)) and run.isdecimal() and int(run)>0,
            'exact GitHub source/run required')
    upstream.validate_live(live,sha,run)
    expected={'overall':'PASS','source_sha':sha,'run_id':run,'android_api':36,
              'live_install_requested':True,'live_install_qualified':True,
              'system_denial_and_acceptance_verified':True,'physical_device_qualified':False,
              'release_qualified':False,'production_play_evidence_modified':False}
    require(all(manual.get(k)==v for k,v in expected.items()),
            'independent manual P5 corroborating receipt absent/inconsistent')
    require(manual.get('qualification_scope')=='MANUAL_HOSTED_API36_ONLY',
            'invalid manual OS qualification scope')
    return {'overall':'PASS','phase':'R3C07_P04_ACTUAL_OS_OUTCOMES',
            'source_sha':sha,'run_id':run,'android_api':36,
            'fixture_package':upstream.PACKAGE,'fixture_sha256':live['fixture_sha256'],
            'actually_signed_fixture_verified':True,
            'android_system_denial_then_acceptance_verified':True,
            'android_callback_and_real_consent_ui_verified':True,
            'app_private_staging_and_cleanup_verified':True,
            'production_play_evidence_modified':False,
            'publisher_authenticated':False,'physical_device_qualified':False,
            'release_qualified':False}

def selftest():
    sha='a'*40;run='12345'
    live={'overall':'PASS','source_sha':sha,'run_id':run,'android_api':36,
        'fixture_package':upstream.PACKAGE,'signed_v2_verified':True,
        'private_app_uid_staging_verified':True,'private_fixture_cleanup_verified':True,
        'emulator_unknown_sources_preprovisioned':True,
        'emulator_unknown_sources_effective_verified':True,
        'instrumentation_status_proof_verified':True,'fixture_sha256':'b'*64,
        'results':[{'outcome':name,'system_consent_ui_verified':True,'android_callback_verified':True,
            'instrumentation_status_verified':True,'foreground_activity_verified':True}
            for name in ('DENY','ACCEPT')],
        'physical_device_qualified':False,'release_qualified':False}
    man={'overall':'PASS','source_sha':sha,'run_id':run,'android_api':36,
       'live_install_requested':True,'live_install_qualified':True,
       'system_denial_and_acceptance_verified':True,'physical_device_qualified':False,
       'release_qualified':False,'production_play_evidence_modified':False,
       'qualification_scope':'MANUAL_HOSTED_API36_ONLY'}
    out=verify(live,man,sha,run)
    assert out['android_system_denial_then_acceptance_verified'] is True
    neg=0
    for field,wrong in [('source_sha','c'*40),('run_id','2'),('fixture_package','org.untrusted'),
            ('signed_v2_verified',False),('private_app_uid_staging_verified',False),
            ('private_fixture_cleanup_verified',False),('instrumentation_status_proof_verified',False),
            ('emulator_unknown_sources_effective_verified',False),('physical_device_qualified',True)]:
        bad={**live,field:wrong}
        try:verify(bad,man,sha,run)
        except (Refused,upstream.QualificationRefused):neg+=1
        else:raise AssertionError('unsafe live receipt accepted '+field)
    for field,wrong in [('live_install_qualified',False),('system_denial_and_acceptance_verified',False),
                        ('qualification_scope','READ_ONLY')]:
        bad={**man,field:wrong}
        try:verify(live,bad,sha,run)
        except (Refused,upstream.QualificationRefused):neg+=1
        else:raise AssertionError('unsafe manual receipt accepted '+field)
    for newresults in ([live['results'][1],live['results'][0]], [live['results'][0]]):
        try:verify({**live,'results':newresults},man,sha,run)
        except (Refused,upstream.QualificationRefused):neg+=1
        else:raise AssertionError('missing/reversed OS action accepted')
    print('R3C07_P04_OS_RECEIPT_SELFTEST_PASS: 1 positive + '+str(neg)+' negatives')

def run(base:pathlib.Path,output:pathlib.Path,sha:str,rid:str):
    require(base.is_dir() and not base.is_symlink(),'logs directory unavailable')
    a=base/'R3C06_P3_LIVE_OS_INSTALL_RECEIPT.json'
    b=base/'R3C06_P5_MANUAL_RECEIPT.json'
    require(a.is_file() and b.is_file() and not a.is_symlink() and not b.is_symlink(),
            'actual opted-in live receipt and corroboration both required')
    raw=verify(json.loads(a.read_text()),json.loads(b.read_text()),sha,rid)
    require(output.parent.resolve()==base.resolve() and not output.exists(),
            'receipt must be unique inside original hosted artifact directory')
    output.write_text(json.dumps(raw,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print('R3C07_P04_REAL_ANDROID_DENY_ACCEPT_AND_CLEANUP_PASS source='+sha+' run='+rid)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--selftest',action='store_true')
    ap.add_argument('--logs',type=pathlib.Path)
    ap.add_argument('--output',type=pathlib.Path)
    ap.add_argument('--sha')
    ap.add_argument('--run-id')
    args=ap.parse_args()
    if args.selftest:selftest();return
    require(args.logs and args.output and args.sha and args.run_id,'missing required args')
    run(args.logs,args.output,args.sha,args.run_id)
if __name__=='__main__':
    try:main()
    except (Refused,upstream.QualificationRefused,ValueError,OSError,TypeError) as e:
        print(str(e),file=sys.stderr);raise SystemExit(2)
