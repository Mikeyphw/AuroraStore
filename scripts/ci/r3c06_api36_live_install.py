#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit API36 emulator acceptance: real test-signed APK via Aurora PackageInstaller.

Never run from the PR-targeted source/compile lane. Never modify an installed app
other than the hard-coded, uniquely named lab fixture (and only if absent at start).
Requires an actual installer UI; never auto-approves a different dialog.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

TARGET = 'com.aurora.r3c06.fixture'
AURORA = 'com.aurora.store.debug'
TEST_CLASS = 'com.aurora.store.data.artifact.ArtifactActualInstallAcceptanceDeviceTest'
INSTALLER_PACKAGES = {'com.android.packageinstaller', 'com.google.android.packageinstaller'}
BUTTON_TEXT = {'accept': {'Install'}, 'deny': {'Cancel'}}

class Refused(Exception): pass

def require(cond, reason):
    if not cond: raise Refused(reason)

def run(argv, *, data=None, timeout=120, check=True):
    p = subprocess.run(argv, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=timeout)
    if check and p.returncode:
        raise Refused('command failed: ' + repr(argv[:5]) + ': ' +
                      p.stderr.decode(errors='replace')[-1000:])
    return p.stdout.decode(errors='replace').strip()

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def build_fixture(work, sdk):
    tools = sorted((sdk/'build-tools').glob('*'), reverse=True)
    tools = [p for p in tools if all((p/n).exists() for n in ('aapt2','zipalign','apksigner'))]
    require(tools, 'Android SDK build-tools with aapt2, zipalign and apksigner missing')
    build = tools[0]
    platform = sdk/'platforms/android-36/android.jar'
    require(platform.is_file(), 'Android SDK platform 36 missing')
    manifest = work/'AndroidManifest.xml'
    manifest.write_text('''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
 package="com.aurora.r3c06.fixture" android:versionCode="17" android:versionName="17.0">
 <uses-sdk android:minSdkVersion="23" android:targetSdkVersion="35" />
 <application android:label="Aurora R3C06 Fixture" android:hasCode="false"
  android:debuggable="false" />
</manifest>''')
    raw, aligned, final = (work/x for x in ('raw.apk','aligned.apk','r3c06-fixture.apk'))
    run([str(build/'aapt2'),'link','-I',str(platform),'--manifest',str(manifest),
         '-o',str(raw),'--min-sdk-version','23','--target-sdk-version','35'])
    run([str(build/'zipalign'),'-f','4',str(raw),str(aligned)])
    ks = work/'test-only.p12'
    storepass='r3c06-test-only-' + os.urandom(12).hex()
    run(['keytool','-genkeypair','-noprompt','-alias','r3c06','-keyalg','RSA',
         '-keysize','2048','-validity','2','-storetype','PKCS12',
         '-dname','CN=R3C06 Emulated Test Fixture,O=Local CI',
         '-keystore',str(ks),'-storepass',storepass,'-keypass',storepass],timeout=90)
    run([str(build/'apksigner'),'sign','--ks',str(ks),
         '--ks-key-alias','r3c06','--ks-pass','pass:'+storepass,
         '--key-pass','pass:'+storepass,'--v2-signing-enabled','true',
         '--v3-signing-enabled','true','--out',str(final),str(aligned)])
    checked=run([str(build/'apksigner'),'verify','--verbose','--print-certs',str(final)])
    require('Verified using v2 scheme (APK Signature Scheme v2): true' in checked,
            'fixture not genuinely signed using APK v2')
    return final

def ui_action(adb, scenario):
    # adb uiautomator dump can be slow. Never tap unless exact fixture label,
    # system installer process and one explicit enabled action agree.
    run(adb+['shell','uiautomator','dump','/sdcard/r3c06-install.xml'],timeout=25)
    text=run(adb+['shell','cat','/sdcard/r3c06-install.xml'],timeout=20)
    root=ET.fromstring(text)
    nodes=list(root.iter('node'))
    labels=' '.join(n.get('text','')+' '+n.get('content-desc','') for n in nodes)
    if 'Aurora R3C06 Fixture' not in labels:
        return None
    candidates=[]
    for node in nodes:
        if node.get('package') not in INSTALLER_PACKAGES:
            continue
        if node.get('text','').strip() not in BUTTON_TEXT[scenario]:
            continue
        if node.get('enabled') != 'true' or node.get('clickable') != 'true':
            continue
        match=re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds',''))
        if match:
            x1,y1,x2,y2=map(int,match.groups())
            if x2>x1 and y2>y1: candidates.append(((x1+x2)//2,(y1+y2)//2))
    require(len(candidates)<=1, 'multiple matching Android installer buttons')
    if not candidates:return None
    x,y=candidates[0]
    run(adb+['shell','input','tap',str(x),str(y)],timeout=15)
    return {'scenario':scenario,'verified_label':True,'installer_button':scenario,'tap_coordinates_redacted':True}

def instrument(adb, runner, scenario, work):
    cmd=adb+['shell','am','instrument','-w','-r','-e','class',TEST_CLASS+'#androidInstallerActuallyAcceptsOrRejectsFixture',
             '-e','r3c06_expected',scenario,runner]
    with (work/('instrument-'+scenario+'.txt')).open('wb') as output:
        p=subprocess.Popen(cmd,stdout=output,stderr=subprocess.STDOUT)
        tapped=False
        try:
            end=time.monotonic()+150
            while time.monotonic()<end:
                if p.poll() is not None:break
                try:
                    proof=ui_action(adb,scenario)
                    if proof:
                        tapped=True
                        break
                except (subprocess.TimeoutExpired,ET.ParseError):
                    pass
                time.sleep(2)
            require(tapped, 'expected Android fixture confirmation UI never appeared (no blind tap)')
            require(p.wait(timeout=220)==0, 'instrumentation command failed')
        finally:
            if p.poll() is None:
                p.terminate()
                try:p.wait(timeout=10)
                except subprocess.TimeoutExpired:p.kill()
    output=(work/('instrument-'+scenario+'.txt')).read_text(errors='replace')
    require('FAILURES!!!' not in output and 'INSTRUMENTATION_FAILED' not in output,
            'Android instrumentation failure')
    require(re.search(r'^OK \(1 test\)',output,re.M), '1 actual OS session test not reported')
    require('R3C06_API36_OS_RESULT='+scenario.upper() in output,
            'matching terminal OS result missing from instrumentation')
    return {'outcome':scenario.upper(),'system_consent_ui_verified':True,'android_callback_verified':True}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--serial',default=None)
    parser.add_argument('--receipt',required=True)
    args=parser.parse_args()
    require(os.environ.get('R3C06_ALLOW_LIVE_INSTALL')=='yes',
            'explicit R3C06_ALLOW_LIVE_INSTALL=yes authorization required')
    sdk=Path(os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT') or '')
    require(sdk.is_dir(), 'ANDROID_HOME/ANDROID_SDK_ROOT missing')
    adb=['adb']+(['-s',args.serial] if args.serial else [])
    require(run(adb+['shell','getprop','ro.build.version.sdk'])=='36','API36 only')
    require(run(adb+['shell','getprop','ro.kernel.qemu'])=='1',
            'not an Android emulator (physical devices forbidden)')
    require(not run(adb+['shell','pm','path',TARGET],check=False),
            'fixture package already installed: refuse to touch existing install')
    instruments=run(adb+['shell','pm','list','instrumentation'])
    matches=re.findall(r'instrumentation:([^ ]+).*target='+re.escape(AURORA)+r'\)',instruments)
    runner=next((x for x in matches if 'HiltInstrumentationTestRunner' in x),None)
    require(runner,'Aurora Hilt instrument runner not installed')
    tmp=Path(os.environ.get('RUNNER_TEMP') or os.environ.get('TMPDIR') or tempfile.gettempdir())
    work=Path(tempfile.mkdtemp(prefix='aurora-r3c06-real-install-',dir=tmp))
    safe_created=False
    results=[]
    try:
        fixture=build_fixture(work,sdk)
        remote='cache/r3c06-fixture.apk'
        # Pipe via non-PTY adb shell; never copy to shared/external device storage.
        run(adb+['shell','-T','run-as',AURORA,'sh','-c','cat > '+remote],
            data=fixture.read_bytes(),timeout=90)
        on_device=run(adb+['shell','run-as',AURORA,'sha256sum',remote]).split()[0]
        require(on_device==sha(fixture),'fixture bytes changed during device transfer')
        for scenario in ('deny','accept'):
            require(not run(adb+['shell','pm','path',TARGET],check=False),
                    'fixture unexpectedly installed before test')
            results.append(instrument(adb,runner,scenario,work))
            installed=bool(run(adb+['shell','pm','path',TARGET],check=False))
            require(installed==(scenario=='accept'), 'package manager state mismatches callback')
            if installed:safe_created=True
        receipt={'overall':'PASS','source_sha':os.environ.get('GITHUB_SHA',''),
                 'run_id':os.environ.get('GITHUB_RUN_ID',''),
                 'android_api':36,'fixture_package':TARGET,
                 'fixture_sha256':sha(fixture),'signed_v2_verified':True,
                 'results':results,'play_evidence_changes_checked':False,
                 'physical_device_qualified':False,'release_qualified':False}
        # Write PASS only after cleanup in finally; see below.
    finally:
        if safe_created or bool(run(adb+['shell','pm','path',TARGET],check=False)):
            run(adb+['uninstall',TARGET],timeout=90)
        require(not run(adb+['shell','pm','path',TARGET],check=False),
                'fixture cleanup failed: NO QUALIFICATION')
        run(adb+['shell','run-as',AURORA,'rm','-f','cache/r3c06-fixture.apk'],check=False)
        # Do not delete diagnostics: current ephemeral RUNNER_TEMP can retain them.
    path=Path(args.receipt);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print('R3C06_REAL_API36_INSTALL_PASS receipt='+str(path))

if __name__=='__main__':
    try:main()
    except (Refused,subprocess.TimeoutExpired,ET.ParseError,OSError) as error:
        print('R3C06_REAL_API36_INSTALL_REFUSED: '+str(error),file=sys.stderr)
        raise SystemExit(2)
