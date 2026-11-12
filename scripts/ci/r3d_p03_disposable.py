#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R3D P03: actual disposable-fixture Android OS acceptance, NOT an Aurora UI claim.

No auto-run: manual GitHub workflow, explicit phrase, clean API36 emulator only.
No root, no PackageInstaller bypass, no uninstall of pre-existing packages.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from r3d_p03_fixture import PACKAGE, verify

AUTH = 'I_AUTHORIZE_DISPOSABLE_API36_EMULATOR_INSTALLS'
SHA = re.compile(r'^[0-9a-f]{40}$')
RUN = re.compile(r'^[1-9][0-9]{0,19}$')
SERIAL = 'emulator-5554'
DEVICE_FILE = '/data/local/tmp/r3d_p03_fixture_v2.apk'

class Refused(Exception): pass

def need(ok, msg):
    if not ok: raise Refused('R3D_P03_REFUSED '+msg)

def command(args, *, allow_failure=False, seconds=120):
    p = subprocess.run([str(x) for x in args], capture_output=True, text=True, timeout=seconds)
    output = (p.stdout+'\n'+p.stderr).strip()
    if p.returncode != 0 and not allow_failure:
        raise Refused('command failed '+str(args[:3])+' rc='+str(p.returncode)+' '+output[-500:])
    return p.returncode,output

def parse_device_inventory(output):
    """Fail closed on ANY extra ADB target; accept tabs or spaces only.

    Preserve the exact physical-device exclusion and online/emulator requirements;
    this fixes only the ADB CLI column-separator assumption.
    """
    need(isinstance(output,str) and len(output)<=16384,
         'invalid or oversized ADB inventory')
    lines=output.splitlines()
    need(bool(lines) and lines[0].strip()=='List of devices attached',
         'missing ADB device inventory header')
    records=[]
    for line in lines[1:]:
        if not line.strip():
            continue
        columns=line.split()
        need(len(columns)>=2 and columns[0] and columns[1],
             'malformed ADB inventory line')
        records.append((columns[0],columns[1]))
    need(records==[(SERIAL,'device')],
         'exactly one online disposable emulator required; ADB inventory='+repr(records[:8]))
    return records

class Android:
    def __init__(self, serial=SERIAL):
        need(serial==SERIAL, 'only private emulator-5554 is allowed')
        self.serial = serial

    def adb(self, *args, allow_failure=False):
        return command(('adb','-s',self.serial,*args),allow_failure=allow_failure)

    def shell(self, *args, allow_failure=False):
        return self.adb('shell',*args,allow_failure=allow_failure)

    def guard(self):
        _, devs = command(('adb','devices','-l'))
        parse_device_inventory(devs)
        _, marker = self.shell('getprop','ro.kernel.qemu')
        need(marker.strip()=='1', 'not an Android emulator; physical devices forbidden')
        _, sdk = self.shell('getprop','ro.build.version.sdk')
        need(sdk.strip()=='36', 'must be API36 emulator')
        _, brand = self.shell('getprop','ro.product.model')
        need(bool(brand.strip()), 'missing emulator model')
        # An emulator may itself be rooted; do not mistake qemu=1 for permission
        # to run shell commands with elevated privileges.
        _, uid = self.shell('id', '-u')
        need(uid.strip() == '2000', 'privileged adb/root shell refused')
        _, secure = self.shell('getprop', 'ro.secure')
        need(secure.strip() == '1', 'insecure emulator image refused')

    def installed(self):
        status,out = self.shell('pm','path',PACKAGE,allow_failure=True)
        if re.search(r'(?m)^package:',out):return True
        _, inventory = self.shell('pm','list','packages','--user','0',PACKAGE)
        packages={line.removeprefix('package:').strip() for line in inventory.splitlines()
                  if line.startswith('package:')}
        if PACKAGE in packages:return True
        need(status == 0 or 'not found' in out.lower() or
             'unable to find' in out.lower(),
             'could not independently establish fixture absence: '+out[-300:])
        return False

    def version(self):
        need(self.installed(), 'fixture absent when version required')
        _,info=self.shell('dumpsys','package',PACKAGE)
        versions={int(v) for v in re.findall(r'\bversionCode=(\d+)\b',info)}
        need(len(versions)==1, 'ambiguous installed version inventory '+str(versions))
        return versions.pop()

    def canary(self, operation, value=None):
        need(operation in ('WRITE','READ'),'invalid canary operation')
        argv=['am','broadcast','-W','--user','0','-n',PACKAGE+'/.CanaryReceiver',
              '-a',PACKAGE+'.CANARY','--es','operation',operation]
        if value is not None:
            need(operation=='WRITE' and bool(re.fullmatch('[0-9a-f]{48}',value)), 'invalid write canary')
            argv+=['--es','value',value]
        _,output=self.shell(*argv)
        codes=re.findall(r'\bresult=(-?\d+)\b',output)
        hashes=re.findall(r'\bsha256:([a-f0-9]{64})\b',output)
        need(codes==['-1'] and len(hashes)==1,
             'fixture broadcast did not acknowledge SHA256 canary: '+output[-500:])
        return hashes[0]

    def install(self, apk, *flags, allow_failure=False):
        return self.adb('install',*flags,str(apk),allow_failure=allow_failure)

    def uninstall(self):
        _,msg=self.adb('uninstall',PACKAGE)
        need('Success' in msg, 'fixture cleanup uninstall did not succeed')

    def assert_owned_temp_absent(self, path=DEVICE_FILE):
        # ls must fail specifically because the temporary file is absent.
        status, out = self.shell('ls', '-ld', path, allow_failure=True)
        need(status != 0 and ('No such file' in out or 'not found' in out.lower()),
             'test-owned temporary file is present or absence could not be proven: '+path)

    def cancel_populated_session(self, apk):
        # Shell-owned, uncommitted session. Never touch a pre-existing temp file.
        self.assert_owned_temp_absent()
        sid = None
        pushed = False
        try:
            pushed = True  # Even a failed adb push may leave partial bytes to remove.
            self.adb('push', str(apk), DEVICE_FILE)
            _, out = self.shell('pm', 'install-create', '-r', '-S', str(apk.stat().st_size))
            match = re.search(r'\[(\d+)\]', out)
            need(match is not None and 'Success' in out, 'session creation not acknowledged')
            sid = match.group(1)
            _, written = self.shell('pm', 'install-write', '-S', str(apk.stat().st_size), sid,
                                    'base.apk', DEVICE_FILE)
            need('Success' in written, 'fixture session did not accept bytes')
            _, abandoned = self.shell('pm', 'install-abandon', sid)
            need('Success' in abandoned, 'populated installation session not abandoned')
            sid = None
        finally:
            # Attempt *both* independent cleanup paths even if abandonment fails.
            # Never promote a partial cleanup to success.
            failures = []
            if sid is not None:
                rc, result = self.shell('pm', 'install-abandon', sid, allow_failure=True)
                if rc != 0 or 'Success' not in result:
                    failures.append('emergency session abandonment FAILED; human inspection required')
            if pushed:
                rc, result = self.shell('rm', '-f', DEVICE_FILE, allow_failure=True)
                if rc != 0:
                    failures.append('test-owned file removal failed: '+result[-300:])
                else:
                    try: self.assert_owned_temp_absent()
                    except Refused as error: failures.append(str(error))
            need(not failures, '; '.join(failures))


def execute(android, fixtures, source_sha, run_id):
    """Live only. The caller has already verified opt-in and source/fixture pins."""
    report={'schema':1,'milestone':'R3D_P03','source_sha':source_sha,
            'run_id':run_id,'package':PACKAGE,'disposable_fixture_only':True,
            'hosted_api36_emulator_only':True,'production_package_tested':False,
            'aurora_ui_packageinstaller_tested':False,'physical_device_qualified':False,
            'release_qualified':False,'backup_verified':False,
            'data_preservation_for_arbitrary_apps':False,'steps':{},
            'fixture_apks':{key:{'version_code':ap['version_code'],
                                'sha256':ap['sha256'],
                                'signing_certificate_sha256':ap['signing_certificate_sha256']}
                            for key,ap in fixtures['apks'].items()},
            'overall':'REFUSED_UNQUALIFIED'}
    clean_scope_authorized=False
    clean_error=None
    try:
        android.guard()
        need(not android.installed(), 'fixture already installed; never touch existing package')
        # If the test-owned temp path predates this run, refuse *before* even
        # installing the disposable fixture; no overwriting stale evidence.
        if hasattr(android, 'assert_owned_temp_absent'):
            android.assert_owned_temp_absent()
        clean_scope_authorized=True  # Package and test-owned temp were proven absent.
        apks=fixtures['apks']
        paths={name:Path(fixtures['_folder'])/item['file'] for name,item in apks.items()}
        value=secrets.token_hex(24)
        expected=hashlib.sha256(value.encode('ascii')).hexdigest()
        report['canary_sha256']=expected
        android.install(paths['v1'])
        need(android.version()==1,'baseline signed fixture v1 not installed')
        need(android.canary('WRITE',value)==expected,'v1 could not persist private canary')
        report['steps']['v1_install_private_canary']='PASS_ACTUAL_ANDROID'
        android.cancel_populated_session(paths['v2'])
        need(android.version()==1 and android.canary('READ')==expected,
             'cancelled populated install modified app or data')
        report['steps']['session_cancel_preserved_v1']='PASS_ACTUAL_ANDROID'
        android.install(paths['v2'],'-r')
        need(android.version()==2 and android.canary('READ')==expected,
             'upgrade lost private canary or wrong installed version')
        report['steps']['v1_to_v2_upgrade_data_preserved']='PASS_ACTUAL_ANDROID'
        status,os_error=android.install(paths['v3_wrong_signer'],'-r',allow_failure=True)
        need(status!=0 and ('UPDATE_INCOMPATIBLE' in os_error or 'signatures do not match' in os_error.lower()
              or 'signature' in os_error.lower()),'mismatched signer was not explicitly refused by OS')
        need(android.version()==2 and android.canary('READ')==expected,
             'signer rejection changed installed app/data')
        report['steps']['signature_mismatch_rejected_preserved']='PASS_ACTUAL_ANDROID'
        status,os_error=android.install(paths['v1'],'-r',allow_failure=True)
        need(status!=0 and ('VERSION_DOWNGRADE' in os_error or 'downgrade' in os_error.lower()),
             'downgrade without -d was not explicitly rejected by OS')
        need(android.version()==2 and android.canary('READ')==expected,
             'rejected downgrade modified data or installed version')
        report['steps']['version_restriction_rejected_preserved']='PASS_ACTUAL_ANDROID'
        # ADB -d is explicitly used only for a debuggable *disposable* fixture.
        # It is NOT a new permission path in production AuroraStore.
        status,os_error=android.install(paths['v1'],'-r','-d',allow_failure=True)
        if status != 0:
            need('VERSION_DOWNGRADE' in os_error or 'downgrade' in os_error.lower(),
                 'debug downgrade failed for unrelated reason')
            report['steps']['debuggable_downgrade']='ANDROID_REFUSED_NOT_QUALIFIED'
            need(android.version()==2 and android.canary('READ')==expected,
                 'refused debug downgrade altered existing data')
            report['overall']='PARTIAL_OS_REJECTED_DOWNGRADE'
        else:
            need(android.version()==1 and android.canary('READ')==expected,
                 'successful downgrade did not preserve private data')
            report['steps']['debuggable_downgrade']='PASS_ACTUAL_ANDROID_DATA_PRESERVED'
            android.install(paths['v2'],'-r')
            need(android.version()==2 and android.canary('READ')==expected,
                 'post-downgrade re-upgrade did not preserve private data')
            report['steps']['round_trip_reupgrade']='PASS_ACTUAL_ANDROID_DATA_PRESERVED'
            report['overall']='PASS_DISPOSABLE_OS_ONLY'
    except Exception as exc:
        report['overall']='REFUSED_UNQUALIFIED'
        report['failure']=str(exc)[-900:]
    finally:
        if clean_scope_authorized:
            try:
                if android.installed():
                    android.uninstall()  # Only package proven absent before this run.
                need(not android.installed(), 'disposable fixture still installed after cleanup')
                if hasattr(android, 'assert_owned_temp_absent'):
                    android.assert_owned_temp_absent()
                report['cleanup']='PASS_DISPOSABLE_FIXTURE_AND_TEMP_ABSENT'
            except Exception as exc:
                clean_error=str(exc)[-900:]
                report['cleanup']='FAILED_FIXTURE_MAY_REMAIN'
                report['cleanup_failure']=clean_error
                report['overall']='REFUSED_CLEANUP_FAILED'
        else:
            report['cleanup']='NO_INSTALL_ATTEMPTED'
        report['finished_at_utc']=datetime.now(timezone.utc).isoformat()
    return report


def main():
    ap=argparse.ArgumentParser(description='Manual hosted disposable API36 fixture runner')
    ap.add_argument('action',choices=['run'])
    ap.add_argument('--fixture-dir',required=True)
    ap.add_argument('--sha',required=True)
    ap.add_argument('--run-id',required=True)
    ap.add_argument('--serial',default=SERIAL)
    ap.add_argument('--authorize',required=True)
    ap.add_argument('--report',required=True)
    a=ap.parse_args()
    need(a.authorize==AUTH,'explicit one-run authorization is required')
    need(SHA.fullmatch(a.sha) is not None and RUN.fullmatch(a.run_id) is not None,
         'invalid Git source SHA or workflow run identifier')
    _,live_sha=command(['git','rev-parse','HEAD'])
    need(live_sha==a.sha,'local source does not match workflow SHA')
    need(os.environ.get('GITHUB_ACTIONS')=='true' and
         os.environ.get('GITHUB_SHA')==a.sha and
         os.environ.get('GITHUB_RUN_ID')==a.run_id, 'hosted exact SHA and run required')
    fixtures=verify(a.fixture_dir)
    fixtures['_folder']=str(Path(a.fixture_dir).resolve())
    report=execute(Android(a.serial),fixtures,a.sha,a.run_id)
    target=Path(a.report).resolve()
    need(target.parent.is_dir() and not target.exists(), 'report path must be new')
    target.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print('R3D_P03_ACTUAL_ANDROID_REPORT='+str(target))
    print('R3D_P03_OUTCOME='+report['overall'])
    if report['overall']!='PASS_DISPOSABLE_OS_ONLY':
        raise SystemExit(2)

if __name__=='__main__':
    try:main()
    except (Refused, RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        print(str(error),file=sys.stderr)
        raise SystemExit(2)
