#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""P03 offline source/negative proof. Never connects to adb or installs APKs."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import unittest
import tempfile

ROOT=Path(__file__).resolve().parents[2]
CI=ROOT/'scripts/ci'
sys.path.insert(0,str(CI))
from r3d_p03_fixture import PACKAGE, verify, manifest
from r3d_p03_disposable import execute, SERIAL, Refused, parse_device_inventory, Android, fixture_present

class FakeAndroid:
    def __init__(self, *, initial=None, cancel_changes=False, bad_upgrade_data=False,
                 bad_downgrade_data=False, wrong_signer_accepted=False,
                 no_downgrade_accepted=False, debug_downgrade_refused=False, cleanup_fails=False,
                 guard_fails=False):
        self.current=initial;self.original_canary=None;self.guard_fails=guard_fails
        self.cancel_changes=cancel_changes;self.bad_upgrade_data=bad_upgrade_data
        self.bad_downgrade_data=bad_downgrade_data
        self.wrong_signer_accepted=wrong_signer_accepted
        self.no_downgrade_accepted=no_downgrade_accepted
        self.debug_downgrade_refused=debug_downgrade_refused
        self.cleanup_fails=cleanup_fails;self.uninstalls=0;self.installs=0
    def guard(self):
        if self.guard_fails:raise RuntimeError('fake physical-device guard refused')
    def installed(self):return self.current is not None
    def version(self):return self.current
    def canary(self,operation,value=None):
        if operation=='WRITE':self.original_canary=value
        return hashlib.sha256((self.original_canary or '').encode()).hexdigest()
    def cancel_populated_session(self,path):
        if self.cancel_changes:self.current=2
    def install(self,path,*flags,allow_failure=False):
        self.installs+=1
        name=Path(path).stem
        if name=='v3_wrong_signer':
            if self.wrong_signer_accepted:self.current=3;return 0,'Success'
            return 1,'INSTALL_FAILED_UPDATE_INCOMPATIBLE: mismatched signatures'
        if name=='v1' and self.current==2:
            if '-d' not in flags:
                if self.no_downgrade_accepted:self.current=1;return 0,'Success'
                return 1,'INSTALL_FAILED_VERSION_DOWNGRADE'
            if self.debug_downgrade_refused:return 1,'INSTALL_FAILED_VERSION_DOWNGRADE'
            self.current=1
            if self.bad_downgrade_data:self.original_canary=None
            return 0,'Success'
        self.current=1 if name=='v1' else 2
        if self.current==2 and self.bad_upgrade_data:self.original_canary=None
        return 0,'Success'
    def uninstall(self):
        self.uninstalls+=1
        if self.cleanup_fails:raise RuntimeError('cannot uninstall fixture')
        self.current=None

def fixtures():
    return {'_folder':'/nonexistent','apks':{key:{'file':key+'.apk',
        'version_code':v,'sha256':'f'*64,'signing_certificate_sha256':('a' if key!='v3_wrong_signer' else 'b')*64}
        for key,v in (('v1',1),('v2',2),('v3_wrong_signer',3))}}

class AndroidInventoryFormatContract(unittest.TestCase):
    def test_realistic_space_and_tab_separated_online_emulator(self):
        for separator in ('\t','    ', ' '):
            for line_end in ('\n', '\r\n'):
                raw='List of devices attached'+line_end+'emulator-5554'+separator+'device product:sdk_gphone'+line_end
                self.assertEqual(parse_device_inventory(raw),[('emulator-5554','device')])

    def test_extra_physical_offline_unauthorized_and_duplicate_refused(self):
        cases=(
            'emulator-5554 device\nR5CT12345 device\n',
            'emulator-5554 device\nR5CT12345 offline\n',
            'emulator-5554 device\nemulator-5554 device\n',
            'emulator-5554 offline\n',
            'emulator-5554 unauthorized\n',
            'R5CT12345 device\n',
            'emulator-5556 device\n',
            'emulator-5554\n',
            'emulator-5554 device\nADB unknown diagnostic\n',
            '',
        )
        for item in cases:
            with self.subTest(inventory=item),self.assertRaises(Refused):
                parse_device_inventory('List of devices attached\n'+item)

    def test_missing_header_and_unbounded_output_refused(self):
        for sample in ('emulator-5554 device\n',
                       'List of devices attached\n'+(' '*16400)):
            with self.assertRaises(Refused): parse_device_inventory(sample)

class DisposablePackageInventoryContract(unittest.TestCase):
    """Mock only the two unprivileged shell outputs; test the REAL guard."""
    def inspect(self,path_rc,path_out,list_rc,list_out):
        android=Android()
        calls=[]
        def stub(*args,allow_failure=False):
            calls.append((args,allow_failure))
            if args==('pm','path',PACKAGE):return path_rc,path_out
            if args==('pm','list','packages','--user','0',PACKAGE):
                return list_rc,list_out
            raise AssertionError('unexpected shell call '+repr(args))
        android.shell=stub
        try:return android.installed()
        finally:
            self.assertEqual(calls,[
                (('pm','path',PACKAGE),True),
                (('pm','list','packages','--user','0',PACKAGE),True)])

    def test_real_api36_empty_output_nonzero_path_means_absent_only_if_list_clean(self):
        self.assertFalse(self.inspect(1,'',0,''))
        self.assertFalse(self.inspect(0,'',0,''))
        self.assertFalse(self.inspect(1,'Error: package not found',0,''))
        self.assertFalse(self.inspect(1,'unable to find package',0,''))

    def test_real_installed_and_split_package_paths(self):
        for path_output in ('package:/data/app/base.apk',
                            'package:/data/app/base.apk\npackage:/data/app/split.apk'):
            self.assertTrue(self.inspect(0,path_output,0,'package:'+PACKAGE))

    def test_path_and_inventory_contradictions_refused(self):
        cases=(
            (1,'',0,'package:'+PACKAGE),
            (0,'',0,'package:'+PACKAGE),
            (0,'Error: package not found',0,'package:'+PACKAGE),
            (0,'package:/data/app/base.apk',0,''),
            (1,'package:/data/app/base.apk',0,'package:'+PACKAGE),
            (0,'package:/data/app/base.apk',0,'package:com.other.app'),
            (0,'package:/data/app/base.apk\nError: partial failure',0,'package:'+PACKAGE),
        )
        for case in cases:
            with self.subTest(case=case),self.assertRaises(Refused):self.inspect(*case)

    def test_missing_or_malformed_package_inventory_refused(self):
        cases=(
            (1,'',1,''),(1,'',1,'permission denied'),
            (1,'',0,'package:com.other.app'),
            (1,'',0,'package:'+PACKAGE+'\npackage:'+PACKAGE),
            (1,'',0,'package:'+PACKAGE+'.clone'),
            (1,'',0,'garbled output'),
            (0,'package:',0,'package:'+PACKAGE),
            (0,'package:relative/path',0,'package:'+PACKAGE),
            (1,'permission denied',0,''),
            (127,'unknown package service',0,''),
            (0,'warning: package manager unavailable',0,''),
        )
        for case in cases:
            with self.subTest(case=case),self.assertRaises(Refused):self.inspect(*case)

    def test_parser_rejects_unbounded_and_wrong_types(self):
        for case in ((1,'',0,'X'*20000), (1,'X'*20000,0,''),
                     ('1','',0,''), (1,b'',0,''), (1,'',None,'')):
            with self.subTest(case=str(case)[:80]),self.assertRaises(Refused):
                fixture_present(*case)

class FixtureContract(unittest.TestCase):
    def test_honest_manifest_packages(self):
        for version in (1,2,3):
            text=manifest(version)
            self.assertIn(f'android:versionCode="{version}"',text)
            self.assertIn('android:allowBackup="false"',text)
            self.assertIn(PACKAGE,text)
            self.assertIn('android:debuggable="true"',text)
    def test_source_assets_and_manual_workflow(self):
        workflow=(ROOT/'.github/workflows/aurora-r3d-p03-disposable.yml').read_text()
        self.assertIn('workflow_dispatch:',workflow)
        self.assertNotRegex(workflow,r'(?m)^  (pull_request|push|schedule):')
        self.assertIn('default: DO_NOT_RUN',workflow)
        self.assertIn('build-tools;35.0.0',workflow)
        self.assertIn("inputs.authorization == 'I_AUTHORIZE_DISPOSABLE_API36_EMULATOR_INSTALLS'",workflow)
        self.assertIn('force-avd-creation: true',workflow)
        self.assertIn('R3D_P03_ACTUAL_DISPOSABLE_RECEIPT.json',workflow)
        self.assertIn('test_r3d_p03_source.py', (ROOT/'.github/workflows/aurora-targeted.yml').read_text())
        src=(CI/'r3d_p03_disposable.py').read_text()
        self.assertIn("marker.strip()=='1'",src)
        self.assertIn("sdk.strip()=='36'",src)
        self.assertIn("need(not android.installed()",src)
        self.assertNotIn('su -c',src)
        self.assertNotIn('pm clear',src)
        self.assertNotIn('install-existing',src)
    def test_fixture_invalid_bytes_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            payload=fixtures()
            aps=payload['apks']
            for key,entry in aps.items():
                f=folder/entry['file'];f.write_bytes(b'garbage')
                entry.update(package=PACKAGE,bytes=7)
            (folder/'fixtures.json').write_text(json.dumps({
                'schema':1,'package':PACKAGE,'fixture_scope':'DISPOSABLE_ONLY',
                'production_signature':False,'android_api':36,'build_tools':'35.0.0','apks':aps}))
            with self.assertRaises(RuntimeError):verify(folder)
    def test_signed_fixture_source_no_user_data_access(self):
        src=(CI/'fixtures/r3d_p03/CanaryReceiver.java').read_text()
        self.assertIn('MODE_PRIVATE',src)
        self.assertIn('getSharedPreferences',src)
        self.assertIn('setResultData',src)
        self.assertNotIn('READ_EXTERNAL_STORAGE',src)
        self.assertNotIn('WRITE_EXTERNAL_STORAGE',src)
        self.assertNotRegex(src,r'(?m)^\s*(?:Runtime\.getRuntime|ProcessBuilder|exec\s*\()')

class ActualStateMachine(unittest.TestCase):
    def runFake(self, **kwargs):
        fake=FakeAndroid(**kwargs)
        result=execute(fake,fixtures(),'b'*40,'123')
        return fake,result
    def test_complete_acceptance(self):
        d,r=self.runFake()
        self.assertEqual(r['overall'],'PASS_DISPOSABLE_OS_ONLY')
        self.assertEqual(r['cleanup'],'PASS_DISPOSABLE_FIXTURE_AND_TEMP_ABSENT')
        self.assertEqual(d.current,None)
        self.assertEqual(d.uninstalls,1)
        self.assertEqual(len(r['steps']),7)
    def test_preexisting_package_not_touched(self):
        d,r=self.runFake(initial=1)
        self.assertEqual(d.uninstalls,0)
        self.assertEqual(d.installs,0)
        self.assertEqual(r['cleanup'],'NO_INSTALL_ATTEMPTED')
        self.assertEqual(r['overall'],'REFUSED_UNQUALIFIED')
    def test_emulator_guard(self):
        d,r=self.runFake(guard_fails=True)
        self.assertEqual(d.uninstalls,0)
        self.assertEqual(d.installs,0)
        self.assertEqual(r['overall'],'REFUSED_UNQUALIFIED')
    def test_cancel_session_changed_version_refused(self):
        _,r=self.runFake(cancel_changes=True)
        self.assertEqual(r['overall'],'REFUSED_UNQUALIFIED')
    def test_upgrade_loses_data_refused(self):
        _,r=self.runFake(bad_upgrade_data=True)
        self.assertEqual(r['overall'],'REFUSED_UNQUALIFIED')
    def test_downgrade_loses_data_refused(self):
        _,r=self.runFake(bad_downgrade_data=True)
        self.assertEqual(r['overall'],'REFUSED_UNQUALIFIED')
    def test_signature_mismatch_accepted_refused(self):
        _,r=self.runFake(wrong_signer_accepted=True)
        self.assertEqual(r['overall'],'REFUSED_UNQUALIFIED')
    def test_ordinary_downgrade_accepted_refused(self):
        _,r=self.runFake(no_downgrade_accepted=True)
        self.assertEqual(r['overall'],'REFUSED_UNQUALIFIED')
    def test_debug_downgrade_os_refusal_distinct(self):
        _,r=self.runFake(debug_downgrade_refused=True)
        self.assertEqual(r['overall'],'PARTIAL_OS_REJECTED_DOWNGRADE')
        self.assertIn('ANDROID_REFUSED_NOT_QUALIFIED',r['steps'].values())
    def test_failed_cleanup_never_passes(self):
        _,r=self.runFake(cleanup_fails=True)
        self.assertEqual(r['overall'],'REFUSED_CLEANUP_FAILED')
        self.assertEqual(r['cleanup'],'FAILED_FIXTURE_MAY_REMAIN')
    def test_never_claim_production_ui_or_personal_data(self):
        _,r=self.runFake()
        self.assertFalse(r['production_package_tested'])
        self.assertFalse(r['aurora_ui_packageinstaller_tested'])
        self.assertFalse(r['data_preservation_for_arbitrary_apps'])
        self.assertFalse(r['backup_verified'])

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():sys.exit(1)
    print('R3D_P03_OFFLINE_NEGATIVE_TESTS_PASS',result.testsRun)
