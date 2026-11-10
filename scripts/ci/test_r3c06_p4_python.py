#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline regressions for P4 receipt integrity, bundletool and UI confirmation.

Runs with stock Python; never requires Android, Gradle or network access.
"""
from pathlib import Path
import importlib.util
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent

def load(short, file):
    spec = importlib.util.spec_from_file_location(short, HERE / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

readonly = load('r3c06_p4_receipt_test', 'r3c06_readonly_receipt.py')
bundle = load('r3c06_p4_bundle_test', 'r3c06_bundletool_matrix.py')
live = load('r3c06_p4_live_test', 'r3c06_api36_live_install.py')
SHA = 'b' * 40

class AcceptanceRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.logs = Path(self.temp.name)
        for name, (count, _) in readonly.SPECS.items():
            (self.logs / name).write_text(f'Time: 0.5\nOK ({count} tests)\n')

    def proof(self, **kw):
        return readonly.measure(self.logs, kw.get('sha', SHA), kw.get('run_id', '123'),
                                kw.get('api', 36))

    def test_readonly_pass_is_truthfully_scoped(self):
        receipt = self.proof()
        self.assertEqual(receipt['executed_tests'], 51)
        self.assertEqual(receipt['suite_count'], 8)
        self.assertFalse(receipt['real_android_installation_qualified'])
        self.assertFalse(receipt['bundletool_device_matrix_qualified'])
        self.assertFalse(receipt['release_qualified'])

    def test_missing_log_refuses(self):
        (self.logs / 'r3c06_real_signed_archives.txt').unlink()
        with self.assertRaises(readonly.Refused): self.proof()

    def test_duplicate_or_forged_pass_refuses(self):
        p = self.logs / 'r3c06_real_signed_archives.txt'
        p.write_text('OK (6 tests)\nOK (6 tests)\n')
        with self.assertRaises(readonly.Refused): self.proof()
        p.write_text('FAILURES!!!\nOK (6 tests)\n')
        with self.assertRaises(readonly.Refused): self.proof()

    def test_refuses_wrong_version_and_missing_identity(self):
        with self.assertRaises(readonly.Refused): self.proof(api=35)
        with self.assertRaises(readonly.Refused): self.proof(sha='')
        with self.assertRaises(readonly.Refused): self.proof(run_id='')

    def test_refused_bundletool_variant_does_not_count(self):
        baseline = {'status': 'SIGNED', 'apks': ['base.apk'], 'sha256': ['aa']}
        self.assertFalse(bundle.qualifies_variant(baseline, {'status': 'REFUSED', 'apks': []}))
        self.assertFalse(bundle.qualifies_variant(baseline, baseline))
        self.assertTrue(bundle.qualifies_variant(
            baseline, {'status': 'SIGNED', 'apks': ['base.apk','config.apk'], 'sha256': ['aa','bb']}))

    def test_adb_package_query_failure_not_misread_as_absence(self):
        with patch.object(live, 'run', side_effect=live.Refused('adb failed')):
            with self.assertRaises(live.Refused): live.fixture_present(['adb'])
        with patch.object(live, 'run', return_value='package:com.aurora.store.debug\npackage:android') as call:
            self.assertFalse(live.fixture_present(['adb']))
            self.assertEqual(call.call_args.args[0],
                             ['adb','shell','pm','list','packages','--user','0'])
        with patch.object(live, 'run', return_value='package:com.aurora.store.debug\npackage:com.aurora.r3c06.fixture'):
            self.assertTrue(live.fixture_present(['adb']))

    def test_unexpected_absent_inventory_is_not_evidence_of_package_absence(self):
        for listing in ('', 'package:android', 'Error: command failed',
                        'package:com.aurora.store.debug\npermission denied',
                        'package:com.aurora.store.debug\npackage:com.aurora.store.debug'):
            with self.subTest(listing=listing), patch.object(live, 'run', return_value=listing):
                with self.assertRaises(live.Refused): live.fixture_present(['adb'])

    def test_prefix_collision_does_not_qualify_fixture_as_installed(self):
        listed = 'package:com.aurora.store.debug\npackage:com.aurora.r3c06.fixture.other'
        with patch.object(live, 'run', return_value=listed):
            self.assertFalse(live.fixture_present(['adb']))

    def test_adb_failure_during_cleanup_is_not_interpreted_as_absence(self):
        # Both preflight and finally call this guard. Neither can return False
        # for a failed ADB query, which would silently skip test APK cleanup.
        with patch.object(live, 'run', side_effect=live.Refused('transport offline')):
            for _ in range(2):
                with self.assertRaises(live.Refused): live.fixture_present(['adb'])

    def test_foreign_app_cannot_supply_installer_identity(self):
        xml = ("<hierarchy><node package='evil.app' text='Aurora R3C06 Fixture' />"
               "<node package='com.android.packageinstaller' text='Install' "
               "enabled='true' clickable='true' bounds='[0,0][100,100]' />"
               "</hierarchy>")
        with patch.object(live, 'run', side_effect=['', xml]) as mocked:
            self.assertIsNone(live.ui_action(['adb'],'accept'))
            self.assertEqual(mocked.call_count,2)

    def test_real_installer_dialog_can_be_selected_once(self):
        xml = ("<hierarchy><node package='com.android.packageinstaller' "
               "text='Aurora R3C06 Fixture' />"
               "<node package='com.android.packageinstaller' text='Install' "
               "enabled='true' clickable='true' bounds='[0,0][100,100]' />"
               "</hierarchy>")
        with patch.object(live, 'run', side_effect=['', xml, '']) as mocked:
            proof = live.ui_action(['adb'],'accept')
            self.assertEqual(proof['installer_button'],'accept')
            self.assertIn('tap', mocked.call_args_list[-1].args[0])

    def instrument_output(self, method, key, value):
        return ('INSTRUMENTATION_STATUS: class=' + live.TEST_CLASS + '\n'
                'INSTRUMENTATION_STATUS: test=' + method + '\n'
                'INSTRUMENTATION_STATUS: ' + key + '=' + value + '\n'
                'INSTRUMENTATION_STATUS_CODE: 0\nTime: 0.1\n'
                'OK (1 test)\nINSTRUMENTATION_CODE: -1\n')

    def test_app_owned_fixture_stage_verifies_sha_and_exact_one_test(self):
        import hashlib, subprocess
        with tempfile.TemporaryDirectory() as td:
            work=Path(td);fixture=work/'test-signed.apk'
            fixture.write_bytes(b'isolated-synthetic-apk-123')
            digest=hashlib.sha256(fixture.read_bytes()).hexdigest()
            result=self.instrument_output('seedSignedFixtureIntoPrivateCache',
                                          'r3c06_fixture_stage_sha256',digest)
            with patch.object(live.subprocess,'run',return_value=subprocess.CompletedProcess([],0,result.encode())) as command:
                self.assertEqual(live.stage_fixture(['adb'],'HiltRunner',fixture,work),digest)
                argv=command.call_args.args[0]
                self.assertIn('seedSignedFixtureIntoPrivateCache',' '.join(argv))
                self.assertIn('r3c06_fixture_base64',argv)
                self.assertIn(digest,argv)
                self.assertNotIn('run-as',argv)
                self.assertIn('r3c06_fixture_stage_sha256='+digest,(work/'fixture-private-stage.txt').read_text())

    def test_app_owned_fixture_cleanup_verifies_receipt(self):
        import subprocess
        with tempfile.TemporaryDirectory() as td:
            work=Path(td);digest='f'*64
            result=self.instrument_output('removeSignedFixtureFromPrivateCache',
                                          'r3c06_fixture_cleanup_sha256',digest)
            with patch.object(live.subprocess,'run',return_value=subprocess.CompletedProcess([],0,result.encode())) as command:
                live.cleanup_fixture(['adb'],'HiltRunner',digest,work)
                argv=command.call_args.args[0]
                self.assertIn('removeSignedFixtureFromPrivateCache',' '.join(argv))
                self.assertNotIn('run-as',argv)
                self.assertTrue((work/'fixture-private-cleanup.txt').is_file())

    def test_missing_or_forged_app_owned_fixture_receipt_fails_closed(self):
        method='seedSignedFixtureIntoPrivateCache';key='r3c06_fixture_stage_sha256'
        digest='a'*64
        valid=self.instrument_output(method,key,digest)
        self.assertTrue(live.check_single_instrumentation_result(valid,method,key,digest))
        for output in ('', 'OK (1 test)',
                       'R3C06_FIXTURE_PRIVATE_STAGE_PASS sha256='+digest+'\nOK (1 test)',
                       valid.replace('INSTRUMENTATION_CODE: -1',''),
                       valid.replace('INSTRUMENTATION_STATUS: '+key+'='+digest+'\n',''),
                       valid.replace(key+'='+digest,key+'='+'b'*64),
                       valid.replace('OK (1 test)','OK (2 tests)'),
                       valid.replace('INSTRUMENTATION_STATUS: test='+method,
                                     'INSTRUMENTATION_STATUS: test=unrelated'),
                       valid+'INSTRUMENTATION_STATUS: '+key+'='+digest+'\n',
                       valid+'INSTRUMENTATION_CODE: -1\n',
                       valid+'FAILURES!!!\n',
                       valid+'INSTRUMENTATION_STATUS_CODE: -2\n',
                       valid.replace('INSTRUMENTATION_STATUS: class='+live.TEST_CLASS,
                                     'INSTRUMENTATION_STATUS: class=evil.Test')):
            with self.subTest(output=output[-100:]):
                with self.assertRaises(live.Refused):
                    live.check_single_instrumentation_result(output,method,key,digest)

    def test_structured_status_cannot_cross_test_scope(self):
        output=self.instrument_output('seedSignedFixtureIntoPrivateCache',
                                      'r3c06_fixture_stage_sha256','a'*64)
        with self.assertRaises(live.Refused):
            live.check_single_instrumentation_result(output,
                'removeSignedFixtureFromPrivateCache','r3c06_fixture_stage_sha256','a'*64)
        os_output=self.instrument_output('androidInstallerActuallyAcceptsOrRejectsFixture',
                                         'r3c06_os_result','ACCEPT')
        self.assertTrue(live.check_single_instrumentation_result(
            os_output,'androidInstallerActuallyAcceptsOrRejectsFixture','r3c06_os_result','ACCEPT'))
        with self.assertRaises(live.Refused):
            live.check_single_instrumentation_result(
                os_output,'androidInstallerActuallyAcceptsOrRejectsFixture','r3c06_os_result','DENY')

    def test_instrumentation_nonzero_retains_failure_log(self):
        import subprocess
        with tempfile.TemporaryDirectory() as td:
            log=Path(td)/'aurora-r3c03-c02'/'r3c06-live-install'/'test.txt'
            secret='sensitivebase64'
            with patch.object(live.subprocess,'run',return_value=subprocess.CompletedProcess([],2,
                    ('Android instrumentation failed '+secret).encode())):
                with self.assertRaisesRegex(live.Refused,'command failed rc=2'):
                    live.run_fixture_instrumentation(
                        ['adb','shell','am','instrument'],log,'seedSignedFixtureIntoPrivateCache',
                        'r3c06_fixture_stage_sha256','a'*64,redact=(secret,))
            self.assertIn('Android instrumentation failed',log.read_text())
            self.assertIn('[REDACTED_FIXTURE_BYTES]',log.read_text())
            self.assertNotIn(secret,log.read_text())

    def test_instrumentation_timeout_retains_failure_log(self):
        import subprocess
        with tempfile.TemporaryDirectory() as td:
            log=Path(td)/'diagnostic.txt'
            timeout=subprocess.TimeoutExpired(['adb'],180,output=b'instrumentation timed out')
            with patch.object(live.subprocess,'run',side_effect=timeout):
                with self.assertRaisesRegex(live.Refused,'timed out'):
                    live.run_fixture_instrumentation(
                        ['adb'],log,'seedSignedFixtureIntoPrivateCache',
                        'r3c06_fixture_stage_sha256','a'*64)
            self.assertIn('instrumentation timed out',log.read_text())

    def test_no_fixture_ipc_arguments_in_diagnostic_artifact(self):
        code=(HERE/'r3c06_api36_live_install.py').read_text()
        self.assertIn('r3c06-live-install',code)
        self.assertIn('redact=(encoded,)',code)
        self.assertIn('run_fixture_instrumentation(',code)
        self.assertIn('primary_error',code)
        self.assertIn('cleanup_errors',code)
        self.assertIn('original acceptance failure:',code)

    def test_fixture_ipc_bounded_and_invalid_cleanup_digest_refused(self):
        with tempfile.TemporaryDirectory() as td:
            work=Path(td); apk=work/'large.apk'
            apk.write_bytes(b'x'*(live.MAX_FIXTURE_BYTES+1))
            with patch.object(live.subprocess,'run') as command:
                with self.assertRaises(live.Refused):
                    live.stage_fixture(['adb'],'HiltRunner',apk,work)
                command.assert_not_called()
                with self.assertRaises(live.Refused):
                    live.cleanup_fixture(['adb'],'HiltRunner','invalid-sha',work)
                command.assert_not_called()

    def test_device_fixture_source_has_bounded_hash_and_app_cache(self):
        source=(HERE.parent.parent / 'app/src/androidTest/java/com/aurora/store/data/artifact/'
                'ArtifactActualInstallAcceptanceDeviceTest.kt').read_text()
        for token in ('context.cacheDir', 'requiredFixtureDigest()',
                      'maxFixtureBytes = 64 * 1024',
                      'seedSignedFixtureIntoPrivateCache()',
                      'removeSignedFixtureFromPrivateCache()',
                      'sendStatus(0, status)',
                      'r3c06_fixture_stage_sha256',
                      'r3c06_fixture_cleanup_sha256',
                      'r3c06_os_result'):
            self.assertIn(token,source)

    def test_foreground_receipt_is_required_once(self):
        marker='INSTRUMENTATION_STATUS: r3c06_foreground_activity=VISIBLE'
        for data in ('',marker+'\n'+marker,marker.replace('VISIBLE','NOT_VISIBLE')):
            with self.subTest(data=data),self.assertRaises(live.Refused):
                live.require_foreground_receipt(data)
        live.require_foreground_receipt(marker)

    def test_unknown_sources_provision_must_verify_app_op(self):
        with patch.object(live,'fixture_present',return_value=False):
            with patch.object(live,'run',side_effect=['','REQUEST_INSTALL_PACKAGES: allow']):
                self.assertTrue(live.provision_hosted_unknown_sources(['adb']))
            for output in ('', 'REQUEST_INSTALL_PACKAGES: ignore', 'permission denied',
                           'REQUEST_INSTALL_PACKAGES: default'):
                with patch.object(live,'run',side_effect=['',output]):
                    with self.assertRaises(live.Refused):
                        live.provision_hosted_unknown_sources(['adb'])
        with patch.object(live,'fixture_present',return_value=True):
            with patch.object(live,'run') as runner:
                with self.assertRaises(live.Refused):
                    live.provision_hosted_unknown_sources(['adb'])
                runner.assert_not_called()

    def test_ui_diagnostics_do_not_copy_secrets_or_unbounded_text(self):
        xml=("<hierarchy><node package='com.google.android.packageinstaller' "
             "class='android.widget.TextView' text='Aurora R3C06 Fixture' />"
             "<node package='unrelated.app' class='android.view.View' "
             "text='private token do not publish' /></hierarchy>")
        import subprocess
        with tempfile.TemporaryDirectory() as td:
            work=Path(td)
            with patch.object(live,'run',side_effect=['',xml]):
                with patch.object(live.subprocess,'run',return_value=subprocess.CompletedProcess([],1,b'')):
                    live.capture_ui_failure_diagnostics(['adb'],work,'deny')
            content=(work/'ui-deny.txt').read_text()
            self.assertIn('Aurora R3C06 Fixture',content)
            self.assertNotIn('private token',content)

    def test_signing_key_not_saved_inside_uploaded_evidence_tree(self):
        driver=(HERE/'r3c06_api36_live_install.py').read_text()
        self.assertIn("work=Path(tempfile.mkdtemp(prefix='aurora-r3c06-private-',dir=tmp))",driver)
        self.assertIn("evidence=Path(tempfile.mkdtemp(prefix='attempt-',dir=logs_parent))",driver)
        self.assertIn('shutil.rmtree(work)',driver)
        self.assertIn('stage_fixture(adb, runner, fixture, evidence)',driver)
        self.assertIn('cleanup_fixture(adb,runner,fixture_digest,evidence)',driver)

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(AcceptanceRegressions)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful(): raise SystemExit(1)
    print('R3C06_P4_PYTHON_NEGATIVE_TESTS_PASS='+str(result.testsRun))
