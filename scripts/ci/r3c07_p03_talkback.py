#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R3C07 P03: explicit, genuine TalkBack accessibility service API36 acceptance.

No TalkBack installation and NO implicit activation.  Only a manually selected
workflow_dispatch flag authorizes temporary service enablement on a disposable
API36 emulator.  Original secure settings are restored and independently
verified even on failure.  Actual focus events require real Android execution.
"""
from __future__ import annotations
import argparse, hashlib, json, os, pathlib, re, subprocess, sys, tempfile

PACKAGE='com.google.android.marvin.talkback'
SERVICE='com.google.android.marvin.talkback/com.google.android.accessibility.talkback.TalkBackService'
APP='com.aurora.store.debug'
CLASS='com.aurora.store.data.artifact.ArtifactTalkBackLiveDeviceTest'
KEYS=('enabled_accessibility_services','accessibility_enabled','touch_exploration_enabled')
SHA=re.compile(r'[0-9a-f]{40}\Z')
class Refused(RuntimeError): pass

def check(ok,why):
    if not ok: raise Refused('R3C07_P03_REFUSED: '+why)

def command(args,*,timeout=30,check_rc=True):
    p=subprocess.run(args,capture_output=True,text=True,timeout=timeout,check=False)
    if check_rc:check(p.returncode==0,'command failed: '+repr(args)+' '+p.stderr[-400:])
    return p.stdout.replace('\r','').strip()

def adb(*args,timeout=35):return command(['adb',*args],timeout=timeout)

def get(key):return adb('shell','settings','get','secure',key)

def put(key,value):
    if value=='null':adb('shell','settings','delete','secure',key)
    else: adb('shell','settings','put','secure',key,value)

def validate_log(raw):
    check(0<len(raw)<3_000_000,'missing/oversized instrumentation log')
    txt=raw.decode('utf-8')
    for bad in ('FAILURES!!!','INSTRUMENTATION_FAILED','Process crashed',
                'INSTRUMENTATION_STATUS_CODE: -1','INSTRUMENTATION_STATUS_CODE: -2',
                'INSTRUMENTATION_CODE: 0'):
        check(bad not in txt,'failed instrumentation: '+bad)
    check(CLASS in txt,'wrong instrumented test class')
    for method in ('talkBackServiceIsActuallyRunningDuringReview',
                   'twoRealTalkBackSwipeFocusEventsChangeTargets'):
        check(len(re.findall(r'^INSTRUMENTATION_STATUS: test='+method+r'\s*$',txt,re.M))>=1,
              'missing actual instrumented method '+method)
    check(len(re.findall(r'^INSTRUMENTATION_STATUS_CODE: 0\s*$',txt,re.M))==2,
          'not exactly two successful instrumented tests')
    check(len(re.findall(r'^OK \(2 tests\)\s*$',txt,re.M))==1,'missing two-test JUnit success')
    check(len(re.findall(r'^INSTRUMENTATION_CODE: -1\s*$',txt,re.M))==1,
          'missing actual Android terminal success')
    return hashlib.sha256(raw).hexdigest()

def verify_preflight():
    check(os.environ.get('R3C07_ALLOW_LIVE_TALKBACK')=='yes',
          'explicit r3c07_live_talkback workflow flag is required')
    source=os.environ.get('GITHUB_SHA','')
    run=os.environ.get('GITHUB_RUN_ID','')
    check(SHA.fullmatch(source) is not None and run.isdecimal() and int(run)>0,
          'exact source SHA and Actions run ID required')
    check(command(['git','rev-parse','HEAD'])==source,'checkout differs from Actions source')
    check(adb('shell','getprop','ro.build.version.sdk')=='36','not Android API36')
    check(adb('shell','getprop','ro.kernel.qemu')=='1','physical/non-emulator device refused')
    packages=set(adb('shell','pm','list','packages','--user','0').splitlines())
    check('package:'+APP in packages,'Aurora app not installed')
    check('package:'+PACKAGE in packages,'real TalkBack not installed: gate NOT_QUALIFIED')
    pkg=adb('shell','dumpsys','package',PACKAGE,timeout=50)
    check('com.google.android.accessibility.talkback.TalkBackService' in pkg,
          'exact TalkBack service component absent: gate NOT_QUALIFIED')
    return source,run

def qualified(log,baseline,after,source,run):
    check(set(baseline)==set(KEYS) and after==baseline,
          'secure settings were not independently restored')
    return {'overall':'PASS','phase':'R3C07_P03_REAL_TALKBACK',
       'source_sha':source,'run_id':run,'android_api':36,
       'actual_instrumentation_tests':2,'log_sha256':validate_log(log),
       'talkback_package':PACKAGE,'talkback_component':SERVICE,
       'genuine_talkback_service_enabled':True,
       'real_accessibility_focus_gestures_verified':True,
       'all_secure_accessibility_settings_restored':True,
       'installation_qualified':False,'physical_device_qualified':False,
       'publisher_authenticated':False,'release_qualified':False}

def run(runner,output):
    source,runid=verify_preflight()
    check('HiltInstrumentationTestRunner' in runner and '/' in runner,
          'wrong or missing source-bound Hilt instrumentation runner')
    out=pathlib.Path(output)
    check(out.is_dir() and not out.is_symlink(),'output must be an existing hosted directory')
    baseline={k:get(k) for k in KEYS}
    check(all(re.fullmatch(r'[A-Za-z0-9_./:;,-]{1,1500}|null',v) for v in baseline.values()),
          'unknown secure settings baseline; no modification attempted')
    updated=(baseline['enabled_accessibility_services'] if baseline['enabled_accessibility_services']!='null' else '')
    entries=[v for v in updated.split(':') if v]
    if SERVICE not in entries: entries.append(SERVICE)
    changed=False; primary=None; payload=None; restored=None
    try:
        changed=True # arm cleanup BEFORE first mutating command
        put('enabled_accessibility_services',':'.join(entries))
        put('accessibility_enabled','1')
        put('touch_exploration_enabled','1')
        active=adb('shell','dumpsys','accessibility',timeout=40)
        check('TalkBackService' in active and PACKAGE in active,
              'TalkBack not confirmed active by AccessibilityManager')
        check(SERVICE in get('enabled_accessibility_services'),
              'TalkBack service not enabled in exact system setting')
        selector=CLASS+'#talkBackServiceIsActuallyRunningDuringReview,'+CLASS+'#twoRealTalkBackSwipeFocusEventsChangeTargets'
        p=subprocess.run(['adb','shell','am','instrument','-w','-r','-e','class',selector,runner],
                         capture_output=True,timeout=240)
        log=p.stdout+(b'\n'+p.stderr if p.stderr else b'')
        (out/'r3c07_p03_talkback_instrumentation.txt').write_bytes(log)
        check(p.returncode==0,'Android instrumentation command failed')
        validate_log(log)
        payload=log
    except Exception as e:
        primary=e
    finally:
        if changed:
            failures=[]
            for k in reversed(KEYS):
                try:put(k,baseline[k])
                except Exception as e:failures.append(k+':'+str(e))
            try:restored={k:get(k) for k in KEYS}
            except Exception as e:
                restored={};failures.append('re-read: '+str(e))
            if restored!=baseline:failures.append('secure settings postimage mismatch')
            if failures:
                raise Refused('R3C07_P03_ACCESSIBILITY_SETTINGS_RESTORE_REFUSED: '+
                              '; '.join(failures)) from primary
    if primary:raise primary
    check(payload is not None and restored is not None,'TalkBack output absent')
    doc=qualified(payload,baseline,restored,source,runid)
    dest=out/'R3C07_P03_REAL_TALKBACK_RECEIPT.json'
    dest.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print('R3C07_P03_REAL_TALKBACK_SERVICE_AND_FOCUS_PASS source='+source+' run='+runid)

def selftest():
    lines='INSTRUMENTATION_STATUS: class='+CLASS+'\n'
    for method in ('talkBackServiceIsActuallyRunningDuringReview','twoRealTalkBackSwipeFocusEventsChangeTargets'):
        lines+='INSTRUMENTATION_STATUS: test='+method+'\nINSTRUMENTATION_STATUS_CODE: 0\n'
    log=(lines+'OK (2 tests)\nINSTRUMENTATION_CODE: -1\n').encode()
    base={k:'null' for k in KEYS}
    got=qualified(log,base,base,'a'*40,'12345')
    check(got['actual_instrumentation_tests']==2,'incorrect real test count')
    bad={'one test missing':log.replace(b'INSTRUMENTATION_STATUS_CODE: 0\n',b'',1),
         'wrong JUnit count':log.replace(b'OK (2 tests)',b'OK (1 test)'),
         'duplicate JUnit banner':log+b'OK (2 tests)\n',
         'failed result':log+b'FAILURES!!!\n',
         'wrong class':log.replace(CLASS.encode(),b'FakeClass'),
         'missing actual focus test':log.replace(b'twoRealTalkBackSwipeFocusEventsChangeTargets',b'fakeMethod'),
         'wrong terminal':log.replace(b'INSTRUMENTATION_CODE: -1',b'INSTRUMENTATION_CODE: 0'),
         'empty':b''}
    for name,b in bad.items():
        try:validate_log(b)
        except (Refused,UnicodeDecodeError):pass
        else:raise AssertionError('incorrect TalkBack log accepted: '+name)
    try:qualified(log,base,{**base,'accessibility_enabled':'1'},'a'*40,'12345')
    except Refused:pass
    else:raise AssertionError('unrestored secure settings were accepted')
    print('R3C07_P03_TALKBACK_RECEIPT_SELFTEST_PASS: 1 positive + 9 negatives')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--selftest',action='store_true')
    ap.add_argument('--run',action='store_true')
    ap.add_argument('--runner')
    ap.add_argument('--out')
    args=ap.parse_args()
    if args.selftest:selftest();return
    check(args.run and args.runner and args.out,'--run --runner --out required')
    run(args.runner,args.out)
if __name__=='__main__':
    try:main()
    except (Refused,OSError,ValueError,subprocess.TimeoutExpired) as e:
        print(str(e),file=sys.stderr)
        raise SystemExit(2)
