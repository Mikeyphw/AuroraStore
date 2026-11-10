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
        with patch.object(live, 'run', return_value=''):
            self.assertFalse(live.fixture_present(['adb']))
        with patch.object(live, 'run', return_value='package:/data/app/test/base.apk'):
            self.assertTrue(live.fixture_present(['adb']))

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

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(AcceptanceRegressions)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful(): raise SystemExit(1)
    print('R3C06_P4_PYTHON_NEGATIVE_TESTS_PASS='+str(result.testsRun))
