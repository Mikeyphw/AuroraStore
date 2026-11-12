#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R3D P04 independently checks as-run *limited* OS fixture evidence.

Requires actual workflow-specific source SHA/run, exact fixture digests, all
measured transitions, and cleanup. Does not attest arbitrary app rollback,
Aurora UI approval/denial, rooted devices, physical Android or releases.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, subprocess
from datetime import datetime, timezone
from pathlib import Path
from r3d_p03_disposable import Refused as DeviceRefused, parse_device_inventory

SHA = re.compile(r'[0-9a-f]{40}\Z')
RUN = re.compile(r'[1-9][0-9]{0,19}\Z')
DIGEST = re.compile(r'[0-9a-f]{64}\Z')
PACKAGE = 'com.aurora.r3d.fixture.history'
EXPECTED = {
    'baseline_canary': 'PASS_ACTUAL_OS',
    'partial_write_session_abandoned': 'PASS_ACTUAL_OS',
    'process_stop_session_abandoned': 'PASS_ACTUAL_OS',
    'app_process_restart_persistence': 'PASS_ACTUAL_OS',
    'foreign_signer_rejection_recovered': 'PASS_ACTUAL_OS',
    'disallowed_downgrade_recovered': 'PASS_ACTUAL_OS',
    'test_only_rollback_reinstall': 'PASS_ACTUAL_OS_CANARY_PRESERVED',
}

class SignoffRefused(Exception): pass

def need(value, why):
    if not value: raise SignoffRefused('R3D_P04_SIGNOFF_REFUSED '+why)

def validate_adb_trace(trace: dict, receipt: dict, sha: str, run_id: str) -> dict:
    """Cross-check observed ADB output, not merely self-declared PASS flags.

    Still a *limited* same-run artifact, never cryptographic OS attestation.
    Any missing command, ambiguous output or unsafe shell invocation refuses.
    """
    need(isinstance(trace, dict) and trace.get('schema') == 1 and
         trace.get('source_sha') == sha and str(trace.get('run_id')) == run_id and
         trace.get('device_serial') == 'emulator-5554',
         'ADB transcript identity or test device mismatched')
    events = trace.get('commands')
    need(isinstance(events, list) and 15 <= len(events) <= 300,
         'ADB evidence missing, unbounded or incomplete')
    need(receipt.get('adb_trace_commands') == len(events), 'ADB command count mismatch')
    need([e.get('seq') for e in events if isinstance(e,dict)] == list(range(1, len(events)+1)),
         'missing/duplicate/reordered ADB command sequence')
    for e in events:
        need(type(e) is dict and type(e.get('args')) is list and
             1 <= len(e['args']) <= 18 and all(type(x) is str and len(x) <= 600 for x in e['args'])
             and type(e.get('exit_code')) is int and type(e.get('output')) is str
             and len(e['output']) <= 8192,
             'ADB command structure invalid')
        argv = e['args']
        need(argv[0] in {'devices','shell','install','uninstall','push'},
             'ADB executed out-of-scope command')
        if argv[0] == 'shell':
            need(len(argv) >= 3 and argv[1] in {'getprop','id','pm','ls','am','rm','dumpsys'},
                 'ADB executed unexpected shell command')
        if argv[0] == 'install':
            need(Path(argv[-1]).name in {'v1.apk','v2.apk','v3_wrong_signer.apk'},
                 'unexpected install target')
        if argv[0] == 'uninstall':
            need(argv == ['uninstall', PACKAGE], 'unsafe uninstall target')
        if argv[0] == 'push':
            need(len(argv) == 3 and argv[-1] == '/data/local/tmp/r3d_p04_owned_partial.apk',
                 'push target outside test-owned temporary file')

    def hits(args, *, tail=False):
        return [(i,e) for i,e in enumerate(events) if
                (e['args'][:len(args)] == args if not tail else e['args'][-len(args):] == args)]
    device_events = hits(['devices','-l'])
    need(len(device_events) == 1 and device_events[0][1]['exit_code'] == 0,
         'as-run ADB device inventory not captured')
    try:
        parse_device_inventory(device_events[0][1]['output'])
    except DeviceRefused as error:
        need(False, 'ADB transcript does not prove exactly one isolated test emulator: '+str(error))
    for cmd, expected in [(['shell','getprop','ro.kernel.qemu'],'1'),
                          (['shell','getprop','ro.build.version.sdk'],'36'),
                          (['shell','getprop','ro.secure'],'1'),
                          (['shell','id','-u'],'2000')]:
        match = hits(cmd)
        need(len(match) == 1 and match[0][1]['exit_code'] == 0 and
             match[0][1]['output'].strip() == expected,
             'actual unprivileged API36 emulator identity missing: '+repr(cmd))
    installs = [(i,e) for i,e in enumerate(events) if e['args'][0] == 'install']
    expected_install = [('v1.apk',[],True,None),
                        ('v2.apk',['-r'],True,None),
                        ('v3_wrong_signer.apk',['-r'],False,'signer'),
                        ('v1.apk',['-r'],False,'downgrade'),
                        ('v1.apk',['-r','-d'],True,None),
                        ('v2.apk',['-r'],True,None)]
    need(len(installs) == len(expected_install), 'real signed APK installation command count incorrect')
    for (index,event),(file,flags,success,negative) in zip(installs,expected_install):
        argv = event['args']
        need(argv[1:-1] == flags and Path(argv[-1]).name == file,
             'actual OS install/rejection command order or version mismatch')
        output = event['output']
        if success:
            need(event['exit_code'] == 0 and 'Success' in output,
                 'actual OS install success not observed')
        else:
            needle = ('UPDATE_INCOMPATIBLE' in output or 'signature' in output.lower()) if negative=='signer' else (
                'VERSION_DOWNGRADE' in output or 'downgrade' in output.lower())
            need(event['exit_code'] != 0 and needle, 'OS rejection message not verified')
    creates = hits(['shell','pm','install-create'])
    writes = hits(['shell','pm','install-write'])
    abandons = hits(['shell','pm','install-abandon'])
    need(len(creates) == len(writes) == len(abandons) == 2,
         'not two independently abandoned uncommitted OS sessions')
    for (ci,ce),(wi,we),(ai,ae) in zip(creates,writes,abandons):
        need(ci < wi < ai and all(e['exit_code'] == 0 and 'Success' in e['output']
                                for e in (ce,we,ae)),
             'interrupted owned session did not create/write/abandon successfully')
    for (ci,ce),(wi,we),(ai,ae) in zip(creates,writes,abandons):
        create_size = int(ce['args'][-1]) if ce['args'][-1].isdigit() else 0
        count = int(we['args'][4]) if len(we['args']) > 5 and we['args'][4].isdigit() else 0
        match = re.search(r'created install session \[(\d+)\]', ce['output'])
        need(match is not None and len(we['args']) >= 8 and len(ae['args']) == 4 and
             we['args'][5] == match.group(1) and ae['args'][3] == match.group(1),
             'uncommitted session IDs do not match across create/write/abandon')
        need(create_size > 1 and 0 < count <= create_size,
             'invalid actual write amount or declared package size')
        if (ci,ce) == creates[0]:
            need(count < create_size, 'first alleged interrupted session was not a partial write')
        else:
            need(count == create_size, 'second session did not write full APK bytes')
    need(creates[0][0] > installs[0][0] and abandons[1][0] < installs[1][0],
         'session interruptions were not bracketed between v1 and v2')
    stops = hits(['shell','am','force-stop', PACKAGE])
    need(len(stops) >= 2 and all(e['exit_code']==0 for _,e in stops),
         'real fixture process interruption missing')
    canaries = hits(['shell','am','broadcast'])
    digest = receipt.get('canary_sha256')
    need(len(canaries) >= 9 and all(e['exit_code']==0 and
         re.search(r'\bresult=-1\b',e['output']) and
         ('sha256:'+digest) in e['output'] for _,e in canaries),
         'private fixture canary outputs not independently observed')
    need(len(canaries) == 9 and 'WRITE' in canaries[0][1]['args'] and
         all('READ' in e['args'] for _,e in canaries[1:]),
         'one test-canary write and eight re-reads required')
    stops_sorted = hits(['shell','am','force-stop', PACKAGE])
    need(len(stops_sorted) == 2, 'unexpected fixture process stop count')
    # Each read MUST occur after the operation whose survival it certifies.
    boundaries = [(installs[0][0],creates[0][0]),
                  (abandons[0][0],creates[1][0]),
                  (abandons[1][0],installs[1][0]),
                  (installs[1][0],stops_sorted[1][0]),
                  (stops_sorted[1][0],installs[2][0]),
                  (installs[2][0],installs[3][0]),
                  (installs[3][0],installs[4][0]),
                  (installs[4][0],installs[5][0]),
                  (installs[5][0],len(events))]
    # The first pair is WRITE-after-v1; the remaining pairs map exactly
    # to each persisted-data READ, in chronological order.
    need(all(low < index < high for (low,high),(index,_) in zip(boundaries,canaries)),
         'canary digest was observed before, not after, a claimed OS transition')
    uninstalls = hits(['uninstall',PACKAGE])
    need(len(uninstalls)==1 and uninstalls[0][1]['exit_code']==0 and
         'Success' in uninstalls[0][1]['output'],
         'successful disposable app teardown command not observed')
    need(uninstalls[0][0] > installs[-1][0], 'fixture removed before completion')
    need(any(i > uninstalls[0][0] and 'package:' not in e['output'] and
             (e['exit_code'] == 0 or 'not found' in e['output'].lower() or
              'unable to find' in e['output'].lower())
             for i,e in hits(['shell','pm','path',PACKAGE])),
         'no post-cleanup device package-path absence observation')
    need(any(i > uninstalls[0][0] and e['exit_code']==0 and
             ('package:'+PACKAGE) not in e['output']
             for i,e in hits(['shell','pm','list','packages','--user','0',PACKAGE])),
         'no independent post-cleanup package inventory proving absence')
    absent = hits(['shell','ls','-ld','/data/local/tmp/r3d_p04_owned_partial.apk'])
    need(len(absent) >= 3 and all(e['exit_code'] != 0 and
          ('No such file' in e['output'] or 'not found' in e['output'].lower()) for _,e in absent),
          'temporary device APK absence not reverified')
    return {'adb_commands_reviewed':len(events), 'canary_reads_verified':len(canaries),
            'abandoned_sessions_verified':2, 'signed_install_attempts_verified':len(installs)}

def assess(receipt: dict, fixture: dict, sha: str, run_id: str, trace: dict | None = None) -> dict:
    need(bool(SHA.fullmatch(sha)) and bool(RUN.fullmatch(run_id)), 'invalid source identity')
    need(type(receipt) is dict and type(fixture) is dict, 'invalid structured reports')
    need(receipt.get('schema') == 1 and receipt.get('milestone') == 'R3D_P04', 'wrong milestone')
    need(receipt.get('source_sha') == sha and str(receipt.get('run_id')) == run_id,
         'different or absent hosted source/run')
    need(receipt.get('package') == PACKAGE and fixture.get('package') == PACKAGE,
         'fixture package mismatch')
    need(receipt.get('overall') == 'PASS_P04_DISPOSABLE_RECOVERY_ONLY', 'OS result not qualified')
    need(receipt.get('steps') == EXPECTED, 'missing, forged, or inconclusive OS step')
    need(receipt.get('cleanup') == 'PASS_DISPOSABLE_FIXTURE_ABSENT', 'cleanup incomplete')
    need(receipt.get('actual_os_installation') is True, 'no actual installed fixture')
    need(bool(DIGEST.fullmatch(str(receipt.get('canary_sha256')))), 'missing private SHA canary')
    for claim in ('disposable_fixture_only', 'hosted_api36_emulator_only',
                  'manual_signoff_pending'):
        need(receipt.get(claim) is True, 'required bounded scope missing '+claim)
    for claim in ('production_package_tested', 'aurora_ui_install_qualified',
                  'android_rollback_manager_qualified', 'root_used',
                  'system_privileges_used', 'physical_device_qualified',
                  'release_qualified', 'final_security_signoff',
                  'data_preservation_for_arbitrary_apps'):
        need(receipt.get(claim) is False, 'prohibited promotion of '+claim)
    need(fixture.get('schema') == 1 and fixture.get('fixture_scope') == 'DISPOSABLE_ONLY'
         and fixture.get('production_signature') is False and fixture.get('android_api') == 36,
         'fixture origin/SDK not scoped')
    aps = fixture.get('apks')
    need(type(aps) is dict and set(aps) == {'v1','v2','v3_wrong_signer'},
         'fixture manifest incomplete')
    match = receipt.get('fixture_apks')
    need(type(match) is dict and set(match) == set(aps), 'receipt signer inventory mismatch')
    for name, version in [('v1',1),('v2',2),('v3_wrong_signer',3)]:
        item = aps[name]
        observed = match[name]
        need(item.get('package') == PACKAGE and item.get('version_code') == version,
             'wrong fixture identity '+name)
        need(observed == {k:item[k] for k in ('version_code','sha256','signing_certificate_sha256')},
             'OS fixture receipt mismatch '+name)
        need(all(DIGEST.fullmatch(str(item[k])) for k in ('sha256','signing_certificate_sha256')),
             'invalid hash/certificate '+name)
    need(aps['v1']['signing_certificate_sha256'] == aps['v2']['signing_certificate_sha256'] and
         aps['v1']['signing_certificate_sha256'] != aps['v3_wrong_signer']['signing_certificate_sha256'],
         'signer identity/control incorrect')
    time_label = receipt.get('finished_at_utc')
    need(isinstance(time_label,str) and len(time_label) <= 50,
         'missing/invalid finished observation time')
    try:
        finished = datetime.fromisoformat(time_label)
    except ValueError:
        raise SignoffRefused('R3D_P04_SIGNOFF_REFUSED non-ISO result timestamp')
    need(finished.tzinfo is not None and finished.utcoffset().total_seconds() == 0,
         'finish time must be offset-aware UTC')
    # Direct source-level unit tests validate only the receipt structure.
    # CLI signoff absolutely requires a separately SHA-bound ADB transcript.
    evidence = validate_adb_trace(trace, receipt, sha, run_id) if trace is not None else None
    return {
        'schema':1, 'source_sha':sha, 'run_id':run_id,
        'scope':'R3D_P04_DISPOSABLE_API36_EMULATOR_ONLY',
        'overall':('LIMITED_DISPOSABLE_OS_RECOVERY_PASS_MANUAL_SIGNOFF_PENDING' if evidence else
                   'STRUCTURAL_RECEIPT_ONLY_NOT_OS_QUALIFIED'),
        'actual_disposable_os_installation':bool(evidence),
        'adb_evidence':evidence,
        'os_steps_verified':len(EXPECTED),
        'data_canary_sha256':receipt['canary_sha256'],
        'source_fixture_receipt_sha256':hashlib.sha256(
            json.dumps(receipt,sort_keys=True).encode()).hexdigest(),
        'manual_aurora_ui_denial_acceptance':False,
        'android_rollback_manager_qualified':False,
        'root_path_qualified':False,'physical_device_qualified':False,
        'r3c08_p05_new_sha_independent_signoff':False,
        'final_security_signoff':False,'release_qualified':False,
    }


def main():
    p=argparse.ArgumentParser(description='Strict independent as-run P04 limited signoff')
    for flag in ('receipt','fixture','sha','run-id','out','trace'):
        p.add_argument('--'+flag,required=True)
    a=p.parse_args()
    # A JSON file alone must never confer a new-SHA GitHub-hosted signoff.
    need(os.environ.get('GITHUB_ACTIONS') == 'true' and
         os.environ.get('GITHUB_SHA') == a.sha and
         os.environ.get('GITHUB_RUN_ID') == a.run_id,
         'actual GitHub-hosted exact source/run environment required')
    checked = subprocess.run(['git','rev-parse','HEAD'],capture_output=True,
                             text=True,timeout=20,check=False)
    need(checked.returncode == 0 and checked.stdout.strip() == a.sha,
         'checked-out Git source does not equal exact hosted SHA')
    source=Path(a.receipt)
    fixture=Path(a.fixture)
    output=Path(a.out)
    need(source.is_file() and fixture.is_file() and not source.is_symlink() and
         not fixture.is_symlink(), 'actual non-symlink evidence required')
    need(not output.exists() and not output.is_symlink() and output.parent.is_dir(),
         'new output path required')
    log = Path(a.trace)
    need(log.is_file() and not log.is_symlink() and log != source and log != fixture,
         'separate, existing, non-symlinked ADB as-run transcript required')
    raw = log.read_bytes()
    need(0 < len(raw) <= 1_500_000, 'ADB transcript empty or unbounded')
    receipt = json.loads(source.read_text())
    need(hashlib.sha256(raw).hexdigest() == receipt.get('adb_trace_sha256'),
         'ADB transcript SHA-256 does not bind the OS result receipt')
    result=assess(receipt,json.loads(fixture.read_text()),a.sha,a.run_id,json.loads(raw))
    need(result['overall'] == 'LIMITED_DISPOSABLE_OS_RECOVERY_PASS_MANUAL_SIGNOFF_PENDING',
         'raw Android OS evidence was not independently qualified')
    with output.open('x',encoding='utf8') as stream:
        stream.write(json.dumps(result,sort_keys=True,indent=2)+'\n')
        stream.flush()
        os.fsync(stream.fileno())
    print('R3D_P04_INDEPENDENT_DISPOSABLE_SIGNOFF_PASS_MANUAL_GATES_PENDING')

if __name__=='__main__':
    try:main()
    except (SignoffRefused,OSError,ValueError,KeyError,TypeError) as e:
        print(str(e),file=__import__('sys').stderr)
        raise SystemExit(2)
