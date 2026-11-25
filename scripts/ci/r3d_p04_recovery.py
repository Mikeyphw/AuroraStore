#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""P04 OS recovery test: MANUAL isolated API36 fixture; no production installation.

Interruption/rollback scope is explicitly bounded: abandoned *uncommitted* OS
sessions and a reversible, debuggable test-fixture version roundtrip, NOT
Android RollbackManager nor Aurora's production system-confirmation UI.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, secrets, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from r3d_p03_fixture import PACKAGE, verify
from r3d_p03_disposable import Android, Refused, need, command, SHA, RUN, SERIAL

AUTH = 'I_AUTHORIZE_R3D_P04_DISPOSABLE_API36_RECOVERY'
PARTIAL_DEVICE_PATH = '/data/local/tmp/r3d_p04_owned_partial.apk'

class RecoveryAndroid(Android):
    def __init__(self, serial=SERIAL):
        super().__init__(serial)
        self.adb_events = []
        self.unabandoned_sessions = set()

    def adb(self, *args, allow_failure=False):
        # Record REAL unprivileged ADB command outputs as separate audit evidence.
        # Preserve negative results; redact the synthetic private canary token.
        rc, output = command(('adb', '-s', self.serial, *args), allow_failure=True)
        shown = list(map(str, args))
        for index in range(len(shown) - 1):
            if shown[index] == 'value' and shown[index-1:index] == ['--es']:
                shown[index + 1] = '[redacted-test-canary]'
        self.adb_events.append({'seq': len(self.adb_events)+1, 'args': shown,
                                'exit_code': rc, 'output': output[-8192:]})
        if rc != 0 and not allow_failure:
            raise Refused('ADB command failed '+repr(shown[:5])+': '+output[-500:])
        return rc, output

    def assert_owned_temp_absent(self):
        rc, text = self.shell('ls', '-ld', PARTIAL_DEVICE_PATH, allow_failure=True)
        need(rc != 0 and ('No such file' in text or 'not found' in text.lower()),
             'P04 test-owned path still exists or absence not proven')

    def assert_no_owned_leaks(self):
        self.assert_owned_temp_absent()
        need(not self.unabandoned_sessions,
             'owned Android PackageInstaller sessions remain un-abandoned: '+
             repr(sorted(self.unabandoned_sessions)))

    def guard(self):
        rc, devices = command(('adb','devices','-l'), allow_failure=True)
        self.adb_events.append({'seq':len(self.adb_events)+1,
                                'args':['devices','-l'],'exit_code':rc,
                                'output':devices[-8192:]})
        need(rc == 0, 'ADB device inventory unavailable before live installation')
        super().guard()
        # P03 Android.guard already requires exactly one emulator, UID=2000 and ro.secure=1.
        self.assert_owned_temp_absent()

    def abandon_interrupted(self, apk: Path, *, partial: bool) -> str:
        """Abandon an uncommitted OS session across separate adb shell processes."""
        owned = None
        label = 'partial_write' if partial else 'post_process_restart'
        try:
            if partial:
                test_bytes = apk.read_bytes()[:max(1, apk.stat().st_size // 3)]
                Path(os.environ['RUNNER_TEMP']).mkdir(parents=True, exist_ok=True)
                host_file = Path(os.environ['RUNNER_TEMP'])/'r3d_p04_partial_owned.apk'
                need(not host_file.exists(), 'host partial fixture path already occupied')
                host_file.write_bytes(test_bytes)
                try: self.adb('push', str(host_file), PARTIAL_DEVICE_PATH)
                finally: host_file.unlink(missing_ok=True)
                count = len(test_bytes)
            else:
                self.adb('push', str(apk), PARTIAL_DEVICE_PATH)
                count = apk.stat().st_size
            _, created = self.shell('pm','install-create','-r','-S',str(apk.stat().st_size))
            match = re.search(r'\[(\d+)\]', created)
            need(match is not None and 'Success' in created, 'session creation not confirmed')
            owned = match.group(1)
            self.unabandoned_sessions.add(owned)
            code, written = self.shell('pm', 'install-write', '-S', str(count),
                                       owned, 'base.apk', PARTIAL_DEVICE_PATH,
                                       allow_failure=True)
            # A failed partial write is not proof that Android ever accepted
            # a partial session. Both forms must record a real successful write.
            need(code == 0 and 'Success' in written,
                 'partial/full session write refused by Android')
            if not partial:
                self.shell('am', 'force-stop', PACKAGE)
            # The shell process that created and populated the session has exited.
            # A later, separate process must abandon the same session.
            _, out = self.shell('pm', 'install-abandon', owned)
            need('Success' in out, 'owned interrupted OS session not abandoned')
            self.unabandoned_sessions.remove(owned)
            owned = None
            return 'ABANDONED_PARTIAL_BYTES' if partial else 'ABANDONED_AFTER_FIXTURE_PROCESS_STOP'
        finally:
            failures = []
            if owned is not None:
                # A failed session abandonment must not skip temp-file cleanup.
                code, out = self.shell('pm', 'install-abandon', owned, allow_failure=True)
                if code == 0 and 'Success' in out:
                    self.unabandoned_sessions.remove(owned)
                else:
                    failures.append('emergency session abandonment FAILED, manual recovery required')
            code, out = self.shell('rm', '-f', PARTIAL_DEVICE_PATH, allow_failure=True)
            if code != 0:
                failures.append('owned temporary file cleanup failed: '+out[-200:])
            try: self.assert_owned_temp_absent()
            except Refused as error: failures.append(str(error))
            need(not failures, '; '.join(failures))


def execute(android: RecoveryAndroid, fixtures: dict, source_sha: str, run_id: str) -> dict:
    report = {'schema': 1, 'milestone': 'R3D_P04', 'source_sha': source_sha,
              'run_id': run_id, 'package': PACKAGE, 'steps': {},
              'fixture_apks': {k: {'version_code': v['version_code'],
                                    'sha256': v['sha256'],
                                    'signing_certificate_sha256': v['signing_certificate_sha256']}
                               for k,v in fixtures['apks'].items()},
              'actual_os_installation': False,
              'disposable_fixture_only': True, 'hosted_api36_emulator_only': True,
              'production_package_tested': False, 'aurora_ui_install_qualified': False,
              'android_rollback_manager_qualified': False,
              'root_used': False, 'system_privileges_used': False,
              'physical_device_qualified': False, 'release_qualified': False,
              'final_security_signoff': False, 'manual_signoff_pending': True,
              'data_preservation_for_arbitrary_apps': False,
              'overall': 'REFUSED_UNQUALIFIED'}
    scoped = False
    try:
        android.guard()
        need(not android.installed(), 'fixture pre-exists; do not alter any existing app')
        scoped = True
        paths = {key: Path(fixtures['_folder'])/value['file']
                 for key,value in fixtures['apks'].items()}
        value = secrets.token_hex(24)
        expected = hashlib.sha256(value.encode('ascii')).hexdigest()
        report['canary_sha256'] = expected
        android.install(paths['v1'])
        report['actual_os_installation'] = True
        need(android.version() == 1 and android.canary('WRITE', value) == expected,
             'baseline fixture installation or private canary failed')
        report['steps']['baseline_canary'] = 'PASS_ACTUAL_OS'
        result = android.abandon_interrupted(paths['v2'], partial=True)
        need(result == 'ABANDONED_PARTIAL_BYTES' and android.version() == 1 and
             android.canary('READ') == expected, 'partial session abandonment changed installed data')
        report['steps']['partial_write_session_abandoned'] = 'PASS_ACTUAL_OS'
        result = android.abandon_interrupted(paths['v2'], partial=False)
        need(result == 'ABANDONED_AFTER_FIXTURE_PROCESS_STOP' and android.version() == 1 and
             android.canary('READ') == expected,
             'interrupted populated session changed installed data')
        report['steps']['process_stop_session_abandoned'] = 'PASS_ACTUAL_OS'
        android.install(paths['v2'], '-r')
        need(android.version() == 2 and android.canary('READ') == expected,
             'upgrade/restart corrupted private canary')
        android.shell('am', 'force-stop', PACKAGE)
        need(android.version() == 2 and android.canary('READ') == expected,
             'forced app process restart lost private canary')
        report['steps']['app_process_restart_persistence'] = 'PASS_ACTUAL_OS'
        code, msg = android.install(paths['v3_wrong_signer'], '-r', allow_failure=True)
        need(code != 0 and ('UPDATE_INCOMPATIBLE' in msg or 'signature' in msg.lower()),
             'Android did not refuse foreign signer')
        need(android.version() == 2 and android.canary('READ') == expected,
             'rejected foreign signer changed data')
        report['steps']['foreign_signer_rejection_recovered'] = 'PASS_ACTUAL_OS'
        code, msg = android.install(paths['v1'], '-r', allow_failure=True)
        need(code != 0 and ('VERSION_DOWNGRADE' in msg or 'downgrade' in msg.lower()),
             'Android did not refuse forbidden downgrade')
        need(android.version() == 2 and android.canary('READ') == expected,
             'rejected downgrade changed data')
        report['steps']['disallowed_downgrade_recovered'] = 'PASS_ACTUAL_OS'
        # Reversal of an explicitly debuggable disposable fixture ONLY.
        # This is NOT Android RollbackManager or production rollback support.
        code, msg = android.install(paths['v1'], '-r', '-d', allow_failure=True)
        if code:
            need('VERSION_DOWNGRADE' in msg or 'downgrade' in msg.lower(),
                 'test-only downgrade failed for unrelated cause')
            need(android.version() == 2 and android.canary('READ') == expected,
                 'unsupported downgrade modified fixture data')
            report['steps']['test_only_rollback_reinstall'] = 'ANDROID_REFUSED_UNQUALIFIED'
            report['overall'] = 'PARTIAL_TEST_ONLY_DOWNGRADE_NOT_SUPPORTED'
        else:
            need(android.version() == 1 and android.canary('READ') == expected,
                 'test-only downgrade lost private canary')
            android.install(paths['v2'], '-r')
            need(android.version() == 2 and android.canary('READ') == expected,
                 'fixture re-upgrade recovery lost data')
            report['steps']['test_only_rollback_reinstall'] = 'PASS_ACTUAL_OS_CANARY_PRESERVED'
            report['overall'] = 'PASS_P04_DISPOSABLE_RECOVERY_ONLY'
    except Exception as error:
        report['failure'] = str(error)[-900:]
        report['overall'] = 'REFUSED_UNQUALIFIED'
    finally:
        if scoped:
            try:
                if android.installed():
                    android.uninstall()
                need(not android.installed(), 'owned fixture remains after teardown')
                # A package-free system is still NOT clean if an install session
                # or uploaded temporary APK remains behind.
                if hasattr(android, 'assert_no_owned_leaks'):
                    android.assert_no_owned_leaks()
                report['cleanup'] = 'PASS_DISPOSABLE_FIXTURE_ABSENT'
            except Exception as error:
                report['cleanup'] = 'FAILED_DISPOSABLE_FIXTURE_MAY_REMAIN'
                report['cleanup_failure'] = str(error)[-600:]
                report['overall'] = 'REFUSED_CLEANUP_FAILED'
        else:
            report['cleanup'] = 'NO_INSTALL_ATTEMPTED'
        report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
    return report


def main():
    ap = argparse.ArgumentParser(description='Manual hosted API36 P04 unprivileged disposable recovery acceptance')
    ap.add_argument('action', choices=['run'])
    for flag in ('fixture-dir', 'sha', 'run-id', 'authorize', 'report', 'trace'):
        ap.add_argument('--'+flag, required=True)
    ap.add_argument('--serial', default=SERIAL)
    args = ap.parse_args()
    need(args.authorize == AUTH, 'P04 per-run explicit opt-in required')
    need(SHA.fullmatch(args.sha) is not None and RUN.fullmatch(args.run_id) is not None,
         'invalid source SHA or run identity')
    _, local_sha = command(['git','rev-parse','HEAD'])
    need(os.environ.get('GITHUB_ACTIONS') == 'true' and
         os.environ.get('GITHUB_SHA') == args.sha and
         os.environ.get('GITHUB_RUN_ID') == args.run_id and local_sha == args.sha,
         'hosted exact source/run identity required')
    fixtures = verify(args.fixture_dir)
    fixtures['_folder'] = str(Path(args.fixture_dir).resolve())
    android = RecoveryAndroid(args.serial)
    report = execute(android, fixtures, args.sha, args.run_id)
    target = Path(args.report).absolute()
    trace_path = Path(args.trace).absolute()
    need(target != trace_path and not target.is_symlink() and not trace_path.is_symlink() and
         target.parent.is_dir() and trace_path.parent.is_dir() and
         not target.exists() and not trace_path.exists(),
         'receipt and ADB transcript must be new, separate, existing-parent paths')
    transcript = {'schema': 1, 'source_sha': args.sha, 'run_id': args.run_id,
                  'device_serial': args.serial, 'commands': android.adb_events}
    raw = (json.dumps(transcript, sort_keys=True, indent=2)+'\n').encode('utf8')
    with trace_path.open('xb') as output:
        output.write(raw)
        output.flush()
        os.fsync(output.fileno())
    report['adb_trace_sha256'] = hashlib.sha256(raw).hexdigest()
    report['adb_trace_commands'] = len(android.adb_events)
    with target.open('x', encoding='utf8') as output:
        output.write(json.dumps(report, sort_keys=True, indent=2)+'\n')
        output.flush()
        os.fsync(output.fileno())
    print('R3D_P04_AS_RUN_RECEIPT='+str(target))
    print('R3D_P04_ACTUAL_OS_OUTCOME='+report['overall'])
    if report['overall'] != 'PASS_P04_DISPOSABLE_RECOVERY_ONLY':
        raise SystemExit(2)

if __name__ == '__main__':
    try: main()
    except (OSError, RuntimeError, Refused, subprocess.TimeoutExpired) as error:
        print('R3D_P04_REFUSED '+str(error), file=sys.stderr)
        raise SystemExit(2)
