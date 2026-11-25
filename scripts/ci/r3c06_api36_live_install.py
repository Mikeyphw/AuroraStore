#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit API36 emulator acceptance: real test-signed APK via Aurora PackageInstaller.

Never run from the PR-targeted source/compile lane. Never modify an installed app
other than the hard-coded, uniquely named lab fixture (and only if absent at start).
Requires an actual installer UI; never auto-approves a different dialog.
"""
import argparse
import base64
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
MAX_FIXTURE_BYTES = 64 * 1024  # bounded Android instrumentation Bundle IPC

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
    # Label must belong to the same trusted Android installer package as the
    # action button. An unrelated overlay/app cannot supply fixture identity.
    labels=' '.join(n.get('text','')+' '+n.get('content-desc','') for n in nodes
                    if n.get('package') in INSTALLER_PACKAGES)
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

def fixture_present(adb):
    # API36 may return exit 1 (with empty stderr) for `pm path` on a package
    # that is *not installed*.  Do not turn a nonzero exit status into an
    # absence claim. Instead query the complete user-0 package inventory:
    # success, correctly shaped records and Aurora's own installed package
    # must ALL be observed before an absent fixture can be established.
    inventory = run(adb + ['shell', 'pm', 'list', 'packages', '--user', '0'], timeout=45)
    records = [line.strip() for line in inventory.splitlines() if line.strip()]
    require(records and all(re.fullmatch(r'package:[A-Za-z0-9_.]+', line)
                            for line in records),
            'Android package inventory is empty, malformed or contains diagnostics')
    require(len(records) == len(set(records)), 'Android package inventory has duplicates')
    require('package:' + AURORA in records,
            'Aurora absent from user-0 inventory: cannot establish fixture state')
    return 'package:' + TARGET in records

def provision_hosted_unknown_sources(adb):
    """Prepare only this explicitly opted-in, ephemeral API36 emulator.

    This is environment setup, NOT evidence of user consent. The separate
    PackageInstaller confirmation is still required and verified on-screen.
    """
    require(not fixture_present(adb), 'fixture present before app-op provisioning')
    run(adb + ['shell', 'appops', 'set', '--uid', AURORA,
               'REQUEST_INSTALL_PACKAGES', 'allow'], timeout=30)
    # `appops get --uid` is human-readable diagnostics and does not have a
    # stable output format across Android versions. An exact output regexp
    # cannot prove the target app's effective entitlement. Instead the
    # Android instrumentation checks PackageManager.canRequestPackageInstalls()
    # under Aurora's UID and reports a signed-test-scoped status receipt.
    # If the UID-level write did not take effect, staging fails closed.
    return True


def require_foreground_receipt(output):
    lines = output.splitlines()
    require(lines.count('INSTRUMENTATION_STATUS: r3c06_foreground_activity=VISIBLE') == 1,
            'real Aurora import activity was not proved foreground for OS consent')


def capture_ui_failure_diagnostics(adb, logdir, scenario):
    """Bounded failure-only evidence. No signing key, APK or raw secret argv."""
    logdir = Path(logdir)
    logdir.mkdir(parents=True, exist_ok=True)
    try:
        raw = run(adb + ['shell', 'uiautomator', 'dump', '/sdcard/r3c06-final.xml'], timeout=25)
        xml = run(adb + ['shell', 'cat', '/sdcard/r3c06-final.xml'], timeout=20)
        root = ET.fromstring(xml)
        lines = []
        for item in list(root.iter('node'))[:128]:
            # Avoid recording arbitrary text from the device. Only structural
            # metadata and short installer-relevant labels are captured.
            pkg = item.get('package', '')[:100]
            label = item.get('text', '').strip()
            if label not in {'Install', 'Cancel', 'Allow', 'Not now',
                             'Aurora R3C06 Fixture', 'Allow from this source'}:
                label = '[OTHER]' if label else ''
            lines.append(f"package={pkg} class={item.get('class', '')[:120]} label={label} enabled={item.get('enabled', '')} clickable={item.get('clickable', '')}")
        (logdir / ('ui-'+scenario+'.txt')).write_text('\n'.join(lines)+'\n', encoding='utf-8')
    except (Refused, subprocess.TimeoutExpired, ET.ParseError, OSError) as error:
        (logdir / ('ui-'+scenario+'.txt')).write_text('UI_CAPTURE_FAILED '+str(type(error).__name__)+'\n')
    try:
        p = subprocess.run(adb + ['logcat','-d','-t','250',
                            'AuroraArtifactImport:W','ActivityTaskManager:W',
                            'PackageInstaller:W','*:S'],capture_output=True,timeout=30)
        if p.returncode == 0:
            lines = p.stdout.decode(errors='replace').splitlines()[-150:]
            (logdir / ('android-'+scenario+'.txt')).write_text('\n'.join(lines)+'\n',encoding='utf-8')
    except (OSError, subprocess.TimeoutExpired):
        pass


def check_single_instrumentation_result(output, method, key, value):
    """Require one real successful AndroidJUnitRunner execution and one exact
    instrumentation *status* receipt, never logcat/println/string substring.
    A fake line in JUnit's result stream cannot satisfy the status requirement.
    """
    require(method in {'seedSignedFixtureIntoPrivateCache',
                       'removeSignedFixtureFromPrivateCache',
                       'androidInstallerActuallyAcceptsOrRejectsFixture'},
            'unknown fixture test method')
    require((key, method) in {
        ('r3c06_fixture_stage_sha256', 'seedSignedFixtureIntoPrivateCache'),
        ('r3c06_fixture_cleanup_sha256', 'removeSignedFixtureFromPrivateCache'),
        ('r3c06_os_result', 'androidInstallerActuallyAcceptsOrRejectsFixture')},
        'fixture status field does not match test method')
    require(re.fullmatch(r'[0-9a-f]{64}', value) is not None if key != 'r3c06_os_result'
            else value in ('DENY', 'ACCEPT'), 'invalid fixture status value')
    lines = output.splitlines()
    require(not any(token in output for token in (
        'FAILURES!!!', 'INSTRUMENTATION_FAILED', 'INSTRUMENTATION_ABORTED',
        'INSTRUMENTATION_STATUS_CODE: -1', 'INSTRUMENTATION_STATUS_CODE: -2',
    )), 'instrumentation reported failure or crash')
    require(lines.count('INSTRUMENTATION_CODE: -1') == 1 and
            lines.count('OK (1 test)') == 1,
            'instrumentation did not complete exactly one successful JUnit test')
    require('INSTRUMENTATION_STATUS: class=' + TEST_CLASS in lines and
            'INSTRUMENTATION_STATUS: test=' + method in lines,
            'instrumentation class or executed test identity missing')
    prefix = 'INSTRUMENTATION_STATUS: ' + key + '='
    status_lines = [line for line in lines if line.startswith(prefix)]
    require(status_lines == [prefix + value],
            'exact structured instrumentation status receipt missing or ambiguous')
    if method == 'seedSignedFixtureIntoPrivateCache':
        # The app itself must verify the effective Android permission. A shell
        # app-op write or a formatted `appops get` line cannot substitute.
        require(lines.count('INSTRUMENTATION_STATUS: '
                            'r3c06_unknown_sources_effective=ALLOWED') == 1,
                'Aurora did not prove effective unknown-source permission')
        require(not any(line.startswith('INSTRUMENTATION_STATUS: '
                             'r3c06_unknown_sources_effective=') and
                        line != ('INSTRUMENTATION_STATUS: '
                                 'r3c06_unknown_sources_effective=ALLOWED')
                        for line in lines),
                'contradictory Android unknown-source permission evidence')
    return True


def run_fixture_instrumentation(cmd, log_path, method, key, value, *, redact=()):
    """Always retain sanitized instrumentation diagnostics in the uploaded R1D
    artifact, including on nonzero adb return or missing proof. Never log argv
    because staging passes an ephemeral signed fixture as a bounded argument.
    """
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=180, check=False)
    except subprocess.TimeoutExpired as failure:
        partial = failure.stdout or b''
        output = partial.decode(errors='replace') if isinstance(partial, bytes) else str(partial)
        for secret in redact:
            output = output.replace(secret, '[REDACTED_FIXTURE_BYTES]')
        log_path.write_text(output[-65536:]+'\nTIMEOUT\n',encoding='utf-8')
        raise Refused('fixture instrumentation timed out; see '+str(log_path)) from failure
    output = proc.stdout.decode(errors='replace')
    for secret in redact:
        output = output.replace(secret, '[REDACTED_FIXTURE_BYTES]')
    log_path.write_text(output[-65536:]+'\n',encoding='utf-8')
    require(proc.returncode == 0,
            'fixture instrumentation command failed rc='+str(proc.returncode)+
            '; see '+str(log_path)+'; tail='+output[-800:])
    try:
        check_single_instrumentation_result(output, method, key, value)
    except Refused as failure:
        raise Refused(str(failure)+'; see '+str(log_path)+'; tail='+output[-900:]) from failure
    return True


def stage_fixture(adb, runner, fixture, work):
    data = Path(fixture).read_bytes()
    require(0 < len(data) <= MAX_FIXTURE_BYTES,
            'test-signed fixture is too large for bounded instrumentation transfer')
    digest = hashlib.sha256(data).hexdigest()
    encoded = base64.b64encode(data).decode('ascii')
    require(len(encoded) <= (MAX_FIXTURE_BYTES + 2) // 3 * 4,
            'encoded fixture exceeds instrumentation transfer bound')
    cmd = (adb + ['shell', 'am', 'instrument', '-w', '-r', '-e', 'class',
                  TEST_CLASS + '#seedSignedFixtureIntoPrivateCache',
                  '-e', 'r3c06_fixture_sha256', digest,
                  '-e', 'r3c06_fixture_base64', encoded, runner])
    run_fixture_instrumentation(
        cmd, work / 'fixture-private-stage.txt',
        'seedSignedFixtureIntoPrivateCache', 'r3c06_fixture_stage_sha256', digest,
        redact=(encoded,))
    return digest


def cleanup_fixture(adb, runner, digest, work):
    require(re.fullmatch(r'[0-9a-f]{64}', digest) is not None,
            'cannot clean up fixture without its exact expected digest')
    cmd = (adb + ['shell', 'am', 'instrument', '-w', '-r', '-e', 'class',
                  TEST_CLASS + '#removeSignedFixtureFromPrivateCache',
                  '-e', 'r3c06_fixture_sha256', digest, runner])
    run_fixture_instrumentation(
        cmd, work / 'fixture-private-cleanup.txt',
        'removeSignedFixtureFromPrivateCache', 'r3c06_fixture_cleanup_sha256', digest)


def instrument(adb, runner, scenario, work, digest):
    cmd=adb+['shell','am','instrument','-w','-r','-e','class',TEST_CLASS+'#androidInstallerActuallyAcceptsOrRejectsFixture',
             '-e','r3c06_expected',scenario, '-e', 'r3c06_fixture_sha256', digest, runner]
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
            if not tapped:
                capture_ui_failure_diagnostics(adb, work, scenario)
                require(False, 'expected Android fixture confirmation UI never appeared (no blind tap); inspect sanitized UI/logcat evidence')
            require(p.wait(timeout=220)==0, 'instrumentation command failed')
        finally:
            if p.poll() is None:
                p.terminate()
                try:p.wait(timeout=10)
                except subprocess.TimeoutExpired:p.kill()
    output=(work/('instrument-'+scenario+'.txt')).read_text(errors='replace')
    try:
        check_single_instrumentation_result(
            output, 'androidInstallerActuallyAcceptsOrRejectsFixture',
            'r3c06_os_result', scenario.upper())
    except Refused as failure:
        raise Refused(str(failure)+'; see '+str(work/('instrument-'+scenario+'.txt'))+
                      '; tail='+output[-900:]) from failure
    require_foreground_receipt(output)
    return {'outcome':scenario.upper(),'system_consent_ui_verified':True,
            'android_callback_verified':True, 'instrumentation_status_verified':True,
            'foreground_activity_verified':True}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--serial',default=None)
    parser.add_argument('--receipt',required=True)
    args=parser.parse_args()
    require(os.environ.get('R3C06_ALLOW_LIVE_INSTALL')=='yes',
            'explicit R3C06_ALLOW_LIVE_INSTALL=yes authorization required')
    source_sha=os.environ.get('GITHUB_SHA','')
    require(re.fullmatch(r'[0-9a-f]{40}',source_sha) is not None,
            'exact GITHUB_SHA required for qualified installation receipt')
    require(run(['git','rev-parse','HEAD'])==source_sha,
            'live-install checkout differs from exact Actions commit')
    sdk=Path(os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT') or '')
    require(sdk.is_dir(), 'ANDROID_HOME/ANDROID_SDK_ROOT missing')
    adb=['adb']+(['-s',args.serial] if args.serial else [])
    require(run(adb+['shell','getprop','ro.build.version.sdk'])=='36','API36 only')
    require(run(adb+['shell','getprop','ro.kernel.qemu'])=='1',
            'not an Android emulator (physical devices forbidden)')
    require(not fixture_present(adb),
            'fixture package already installed: refuse to touch existing install')
    instruments=run(adb+['shell','pm','list','instrumentation'])
    matches=re.findall(r'instrumentation:([^ ]+).*target='+re.escape(AURORA)+r'\)',instruments)
    runner=next((x for x in matches if 'HiltInstrumentationTestRunner' in x),None)
    require(runner,'Aurora Hilt instrument runner not installed')
    provision_hosted_unknown_sources(adb)
    tmp=Path(os.environ.get('RUNNER_TEMP') or os.environ.get('TMPDIR') or tempfile.gettempdir())
    # Existing R1D upload-artifact includes aurora-r3c03-c02. Save all
    # sanitized stage/OS/cleanup outputs there even when a test fails.
    logs_parent = tmp / 'aurora-r3c03-c02' / 'r3c06-live-install'
    logs_parent.mkdir(parents=True, exist_ok=True)
    # Keep the ephemeral signing key and generated APK OUTSIDE uploaded artifacts.
    # Only short sanitized Android diagnostics go into aurora-r3c03-c02.
    work=Path(tempfile.mkdtemp(prefix='aurora-r3c06-private-',dir=tmp))
    evidence=Path(tempfile.mkdtemp(prefix='attempt-',dir=logs_parent))
    results=[]
    fixture_digest=None
    seed_attempted=False
    receipt=None
    primary_error=None
    cleanup_errors=[]
    try:
        fixture=build_fixture(work,sdk)
        fixture_digest=sha(fixture)
        # Android itself owns the cache directory. Stage via the app's bounded
        # instrumentation entry point; never assume `adb run-as` can write it.
        seed_attempted=True
        require(stage_fixture(adb, runner, fixture, evidence)==fixture_digest,
                'signed fixture digest changed during Android-private staging')
        for scenario in ('deny','accept'):
            require(not fixture_present(adb),
                    'fixture unexpectedly installed before test')
            results.append(instrument(adb,runner,scenario,evidence,fixture_digest))
            installed=fixture_present(adb)
            require(installed==(scenario=='accept'), 'package manager state mismatches callback')
        receipt={'overall':'PASS','source_sha':source_sha,
                 'run_id':os.environ.get('GITHUB_RUN_ID',''),
                 'android_api':36,'fixture_package':TARGET,
                 'fixture_sha256':fixture_digest,'signed_v2_verified':True,
                 'private_app_uid_staging_verified':True,
                 'emulator_unknown_sources_preprovisioned':True,
                 'emulator_unknown_sources_effective_verified':True,
                 'instrumentation_status_proof_verified':True,
                 'results':results,'play_evidence_changes_checked':False,
                 'physical_device_qualified':False,'release_qualified':False}
        # Never write PASS until both system uninstallation and private-file
        # cleanup are independently established in finally.
    except Exception as failure:
        primary_error=failure
    finally:
        try:
            if fixture_present(adb):
                run(adb+['uninstall',TARGET],timeout=90)
            require(not fixture_present(adb),
                    'fixture package uninstall failed: NO QUALIFICATION')
        except (Refused, subprocess.TimeoutExpired, OSError) as failure:
            cleanup_errors.append(str(failure))
        if seed_attempted and fixture_digest is not None:
            try:
                cleanup_fixture(adb,runner,fixture_digest,evidence)
            except (Refused, subprocess.TimeoutExpired, OSError) as failure:
                cleanup_errors.append(str(failure))
    # A private test-only signing key must never become a downloadable CI artifact
    # and must not persist in the ephemeral runner after the attempt.
    try:
        shutil.rmtree(work)
        require(not work.exists(), 'private fixture signing material persists')
    except (OSError, Refused) as failure:
        cleanup_errors.append('test signing material cleanup failed: '+str(failure))
    if primary_error is not None or cleanup_errors:
        problems=[]
        if primary_error is not None:
            problems.append('original acceptance failure: '+str(primary_error))
        if cleanup_errors:
            problems.append('fixture package/private-file cleanup incomplete: '+
                            '; '.join(cleanup_errors))
        raise Refused(' | '.join(problems)) from primary_error
    require(receipt is not None, 'successful OS receipt absent after cleanup')
    receipt['private_fixture_cleanup_verified']=True
    path=Path(args.receipt);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print('R3C06_REAL_API36_INSTALL_PASS receipt='+str(path))

if __name__=='__main__':
    try:main()
    except (Refused,subprocess.TimeoutExpired,ET.ParseError,OSError) as error:
        print('R3C06_REAL_API36_INSTALL_REFUSED: '+str(error),file=sys.stderr)
        raise SystemExit(2)
