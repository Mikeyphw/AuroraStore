#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""No-device P04 adversarial policy/source harness. Never calls adb/Gradle."""
from __future__ import annotations
import copy, hashlib, os
from pathlib import Path
import unittest
from r3d_p04_recovery import execute, RecoveryAndroid, Refused, PACKAGE, PARTIAL_DEVICE_PATH
from r3d_p04_signoff import assess, SignoffRefused, EXPECTED, validate_adb_trace

SHA='a'*40
RUN='987654321'

def sample():
    a={'v1':('1'*64,'4'*64,1),'v2':('2'*64,'4'*64,2),
       'v3_wrong_signer':('3'*64,'5'*64,3)}
    return {'schema':1,'package':PACKAGE,'fixture_scope':'DISPOSABLE_ONLY',
            'production_signature':False,'android_api':36,'build_tools':'35.0.0',
            '_folder':'/synthetic-unused',
            'apks':{key: {'file':key+'.apk','version_code':v,'sha256':h,
                          'signing_certificate_sha256':cert,'package':PACKAGE,'bytes':100}
                    for key,(h,cert,v) in a.items()}}

def synthetic_adb_transcript(r):
    """Mock *independent output* for unit tests; never OS qualification."""
    entries=[]
    def event(args,out='',rc=0):
        entries.append({'seq':len(entries)+1,'args':list(args),'exit_code':rc,'output':out})
    absent='ls: No such file or directory'
    event(['devices','-l'],'List of devices attached\nemulator-5554\tdevice product:sdk_gphone\n')
    event(['shell','getprop','ro.kernel.qemu'],'1')
    event(['shell','getprop','ro.build.version.sdk'],'36')
    event(['shell','getprop','ro.secure'],'1')
    event(['shell','id','-u'],'2000')
    event(['shell','ls','-ld','/data/local/tmp/r3d_p04_owned_partial.apk'],absent,1)
    event(['install','/tmp/v1.apk'],'Success')
    event(['shell','am','broadcast','--es','operation','WRITE'],'Broadcast completed: result=-1 data="sha256:'+r['canary_sha256']+'"')
    for sid in (81,82):
        event(['shell','pm','install-create','-r','-S','200'],'Success: created install session ['+str(sid)+']')
        event(['shell','pm','install-write','-S',('60' if sid == 81 else '200'),str(sid),'base.apk','/data/local/tmp/r3d_p04_owned_partial.apk'],'Success')
        if sid == 82:event(['shell','am','force-stop',PACKAGE])
        event(['shell','pm','install-abandon',str(sid)],'Success')
        event(['shell','ls','-ld','/data/local/tmp/r3d_p04_owned_partial.apk'],absent,1)
        event(['shell','am','broadcast','--es','operation','READ'],'Broadcast completed: result=-1 data="sha256:'+r['canary_sha256']+'"')
    event(['install','-r','/tmp/v2.apk'],'Success')
    event(['shell','am','broadcast','--es','operation','READ'],'Broadcast completed: result=-1 data="sha256:'+r['canary_sha256']+'"')
    event(['shell','am','force-stop',PACKAGE])
    event(['shell','am','broadcast','--es','operation','READ'],'Broadcast completed: result=-1 data="sha256:'+r['canary_sha256']+'"')
    event(['install','-r','/tmp/v3_wrong_signer.apk'],'INSTALL_FAILED_UPDATE_INCOMPATIBLE signature',1)
    event(['shell','am','broadcast','--es','operation','READ'],'Broadcast completed: result=-1 data="sha256:'+r['canary_sha256']+'"')
    event(['install','-r','/tmp/v1.apk'],'INSTALL_FAILED_VERSION_DOWNGRADE',1)
    event(['shell','am','broadcast','--es','operation','READ'],'Broadcast completed: result=-1 data="sha256:'+r['canary_sha256']+'"')
    event(['install','-r','-d','/tmp/v1.apk'],'Success')
    event(['shell','am','broadcast','--es','operation','READ'],'Broadcast completed: result=-1 data="sha256:'+r['canary_sha256']+'"')
    event(['install','-r','/tmp/v2.apk'],'Success')
    event(['shell','am','broadcast','--es','operation','READ'],'Broadcast completed: result=-1 data="sha256:'+r['canary_sha256']+'"')
    event(['uninstall',PACKAGE],'Success')
    event(['shell','pm','path',PACKAGE],'Error: package not found',1)
    event(['shell','pm','list','packages','--user','0',PACKAGE],'')
    event(['shell','ls','-ld','/data/local/tmp/r3d_p04_owned_partial.apk'],absent,1)
    return {'schema':1,'source_sha':SHA,'run_id':RUN,
            'device_serial':'emulator-5554','commands':entries}

class FakeAndroid:
    def __init__(self, *, preexisting=False, root=False, fail_cleanup=False,
                 disallow_debug_downgrade=False, corrupt=False, fail_interrupt=False):
        self.ver=2 if preexisting else None
        self.root=root
        self.canary_hash=None
        self.fail_cleanup=fail_cleanup
        self.disallow_debug_downgrade=disallow_debug_downgrade
        self.corrupt=corrupt
        self.fail_interrupt=fail_interrupt
        self.events=[]
    def guard(self):
        if self.root:raise Refused('unprivileged UID required, root refused')
    def installed(self):return self.ver is not None
    def version(self):return self.ver
    def canary(self,operation,value=None):
        if operation=='WRITE':self.canary_hash=hashlib.sha256(value.encode('ascii')).hexdigest()
        return ('f'*64 if self.corrupt and operation=='READ' else self.canary_hash)
    def abandon_interrupted(self,apk,*,partial):
        self.events.append('partial' if partial else 'process_stop')
        if self.fail_interrupt:raise Refused('abandon failed')
        return 'ABANDONED_PARTIAL_BYTES' if partial else 'ABANDONED_AFTER_FIXTURE_PROCESS_STOP'
    def install(self,apk,*args,allow_failure=False):
        name=Path(apk).stem
        self.events.append('install_'+name+'_'.join(args))
        if name=='v3_wrong_signer':return 1,'INSTALL_FAILED_UPDATE_INCOMPATIBLE signature mismatch'
        if name=='v1' and self.ver==2 and '-d' not in args:
            return 1,'INSTALL_FAILED_VERSION_DOWNGRADE'
        if name=='v1' and self.ver==2 and self.disallow_debug_downgrade:
            return 1,'INSTALL_FAILED_VERSION_DOWNGRADE'
        self.ver=1 if name=='v1' else 2
        return 0,'Success'
    def shell(self,*args,allow_failure=False):
        if args[:2] != ('am','force-stop'):
            raise AssertionError('unexpected privileged/shell command '+repr(args))
        return 0,''
    def uninstall(self):
        if self.fail_cleanup:raise Refused('cannot uninstall disposable test package')
        self.ver=None

class P04AdversarialTests(unittest.TestCase):
    def good(self):
        f=sample();r=execute(FakeAndroid(),f,SHA,RUN)
        self.assertEqual(r['overall'],'PASS_P04_DISPOSABLE_RECOVERY_ONLY')
        return r,f
    def test_01_actual_simulated_success_flow(self):
        r,_=self.good();self.assertEqual(r['steps'],EXPECTED)
    def test_02_no_automatic_root(self):
        r=execute(FakeAndroid(root=True),sample(),SHA,RUN)
        self.assertEqual(r['overall'],'REFUSED_UNQUALIFIED');self.assertEqual(r['cleanup'],'NO_INSTALL_ATTEMPTED')
    def test_03_preexisting_fixture_refused(self):
        r=execute(FakeAndroid(preexisting=True),sample(),SHA,RUN)
        self.assertEqual(r['cleanup'],'NO_INSTALL_ATTEMPTED')
    def test_04_cleanup_failure_overrides_os_success(self):
        r=execute(FakeAndroid(fail_cleanup=True),sample(),SHA,RUN)
        self.assertEqual(r['overall'],'REFUSED_CLEANUP_FAILED')
    def test_05_downgrade_denied_is_not_success(self):
        r=execute(FakeAndroid(disallow_debug_downgrade=True),sample(),SHA,RUN)
        self.assertEqual(r['overall'],'PARTIAL_TEST_ONLY_DOWNGRADE_NOT_SUPPORTED')
    def test_06_private_canary_corruption_fails(self):
        r=execute(FakeAndroid(corrupt=True),sample(),SHA,RUN)
        self.assertEqual(r['overall'],'REFUSED_UNQUALIFIED')
    def test_07_abandoned_session_failure_fails(self):
        r=execute(FakeAndroid(fail_interrupt=True),sample(),SHA,RUN)
        self.assertEqual(r['overall'],'REFUSED_UNQUALIFIED')
    def test_08_signoff_limited_and_manual(self):
        r,f=self.good();s=assess(r,f,SHA,RUN)
        self.assertTrue(s['manual_aurora_ui_denial_acceptance'] is False)
        self.assertTrue(s['final_security_signoff'] is False)
        self.assertEqual(s['os_steps_verified'],7)
    def test_09_wrong_source_run_refused(self):
        r,f=self.good()
        for bad in [('b'*40,RUN),(SHA,'123'),('b',RUN),(SHA,'0')]:
            with self.subTest(bad=bad),self.assertRaises(SignoffRefused): assess(r,f,*bad)
    def test_10_receipt_adversarial_field_mutations(self):
        r,f=self.good()
        mutations=[('overall','PASS_RELEASE'),('cleanup','FAILED'),
             ('canary_sha256','short'),('source_sha','b'*40),('run_id','123'),
             ('milestone','P03'),('package','com.actual.user.app'),('schema',2),
             ('disposable_fixture_only',False),('hosted_api36_emulator_only',False),
             ('production_package_tested',True),('aurora_ui_install_qualified',True),
             ('android_rollback_manager_qualified',True),('root_used',True),
             ('system_privileges_used',True),('physical_device_qualified',True),
             ('release_qualified',True),('final_security_signoff',True),
             ('manual_signoff_pending',False),('data_preservation_for_arbitrary_apps',True),
             ('actual_os_installation',False),('finished_at_utc','')]
        for field,value in mutations:
            tampered=copy.deepcopy(r);tampered[field]=value
            with self.subTest(field=field),self.assertRaises(SignoffRefused):
                assess(tampered,f,SHA,RUN)
    def test_11_all_required_steps_veto(self):
        r,f=self.good()
        for key in EXPECTED:
            for mutation in ('REMOVE','NOT_RUN','FAKED'):
                o=copy.deepcopy(r)
                if mutation=='REMOVE':del o['steps'][key]
                else:o['steps'][key]=mutation
                with self.subTest(step=key,mutation=mutation),self.assertRaises(SignoffRefused):
                    assess(o,f,SHA,RUN)
    def test_12_signer_receipt_veto(self):
        r,f=self.good()
        for key in f['apks']:
            c=copy.deepcopy(r);c['fixture_apks'][key]['signing_certificate_sha256']='f'*64
            with self.subTest(key=key),self.assertRaises(SignoffRefused): assess(c,f,SHA,RUN)
    def test_13_fixture_manifest_veto(self):
        r,f=self.good()
        for field,val in [('package','com.other'),('fixture_scope','PRODUCTION'),
                          ('production_signature',True),('android_api',35)]:
            c=copy.deepcopy(f);c[field]=val
            with self.subTest(field=field),self.assertRaises(SignoffRefused): assess(r,c,SHA,RUN)
    def test_14_wrong_signer_not_accepted(self):
        r,f=self.good();c=copy.deepcopy(f)
        c['apks']['v3_wrong_signer']['signing_certificate_sha256']=c['apks']['v2']['signing_certificate_sha256']
        c2=copy.deepcopy(r)
        c2['fixture_apks']['v3_wrong_signer']['signing_certificate_sha256']=c['apks']['v2']['signing_certificate_sha256']
        with self.assertRaises(SignoffRefused):assess(c2,c,SHA,RUN)
    def test_23_source_only_receipt_never_claims_android_signoff(self):
        r,f=self.good()
        self.assertEqual(assess(r,f,SHA,RUN)['overall'],
                         'STRUCTURAL_RECEIPT_ONLY_NOT_OS_QUALIFIED')

    def test_24_independent_raw_adb_trace_required_for_limited_signoff(self):
        r,f=self.good()
        trace=synthetic_adb_transcript(r)
        r['adb_trace_commands']=len(trace['commands'])
        result=assess(r,f,SHA,RUN,trace)
        self.assertEqual(result['overall'],
                         'LIMITED_DISPOSABLE_OS_RECOVERY_PASS_MANUAL_SIGNOFF_PENDING')
        self.assertEqual(result['adb_evidence']['abandoned_sessions_verified'],2)

    def test_25_synthetic_adb_trace_negative_mutations(self):
        r,f=self.good()
        trace=synthetic_adb_transcript(r)
        r['adb_trace_commands']=len(trace['commands'])
        mutations=[]
        def replace(needle,mutator):
            for i,event in enumerate(trace['commands']):
                if needle(event):
                    changed=copy.deepcopy(trace)
                    mutator(changed['commands'][i])
                    return changed
            raise AssertionError('synthetic evidence missing target '+repr(needle))
        mutations.append(replace(lambda e:e['args']==['shell','id','-u'],
                                 lambda e:e.update(output='0')))
        mutations.append(replace(lambda e:e['args'][0]=='uninstall',
                                 lambda e:e.update(exit_code=1)))
        mutations.append(replace(lambda e:e['args'][0]=='install' and
                                 e['args'][-1].endswith('v3_wrong_signer.apk'),
                                 lambda e:e.update(exit_code=0)))
        mutations.append(replace(lambda e:e['args'][:3]==['shell','pm','install-abandon'],
                                 lambda e:e.update(output='Permission denied')))
        mutations.append(replace(lambda e:e['args'][:3]==['shell','am','broadcast'],
                                 lambda e:e.update(output='Broadcast completed: result=0')))
        mutations.append(replace(lambda e:e['args'][:3]==['shell','pm','install-write'],
                                 lambda e:e.update(exit_code=1)))
        mutations.append(replace(lambda e:e['args'][:2]==['shell','ls'],
                                 lambda e:e.update(output='existing file',exit_code=0)))
        mutations.append(replace(lambda e:e['args'][:3]==['shell','pm','path'] and
                                 'not found' in e['output'],
                                 lambda e:e.update(output='package:/data/app/still-installed.apk',exit_code=0)))
        mutations.append(replace(lambda e:e['args'][:3]==['shell','pm','list'] and
                                 'packages' in e['args'],
                                 lambda e:e.update(output='package:'+PACKAGE)))
        mutations.append(replace(lambda e:e['args'][0]=='install' and
                                 e['args'][-1].endswith('v1.apk') and len(e['args'])==2,
                                 lambda e:e.update(args=['install','/tmp/personal.apk'])))
        reordered=copy.deepcopy(trace)
        reordered['commands'][1]['seq']=1
        mutations.append(reordered)
        missing=copy.deepcopy(trace)
        missing['commands']=missing['commands'][:-1]
        mutations.append(missing)
        for i,mutated in enumerate(mutations):
            with self.subTest(case=i), self.assertRaises(SignoffRefused):
                validate_adb_trace(mutated,r,SHA,RUN)

    def test_28_adb_inventory_whitespace_is_strict_and_format_independent(self):
        report,fixture=self.good()
        trace=synthetic_adb_transcript(report)
        report['adb_trace_commands']=len(trace['commands'])
        for separator in ('\t','   '):
            good=copy.deepcopy(trace)
            good['commands'][0]['output']=('List of devices attached\n'
                'emulator-5554'+separator+'device product:sdk_gphone\n')
            validate_adb_trace(good,report,SHA,RUN)
        for mutation in (
            'emulator-5554 device\nR5CT12345 device\n',
            'emulator-5554 device\nemulator-5556 offline\n',
            'emulator-5554 unauthorized\n',
            'R5CT12345 device\n',
            'emulator-5554 device\nemulator-5554 device\n',
        ):
            bad=copy.deepcopy(trace)
            bad['commands'][0]['output']='List of devices attached\n'+mutation
            with self.subTest(mutation=mutation),self.assertRaises(SignoffRefused):
                validate_adb_trace(bad,report,SHA,RUN)

    def test_29_post_cleanup_independent_empty_inventory_accepts_silent_pm_path_failure(self):
        report,fixture=self.good()
        trace=synthetic_adb_transcript(report)
        report['adb_trace_commands']=len(trace['commands'])
        original=next(e for e in trace['commands'] if
            e['args']==['shell','pm','path',PACKAGE])
        self.assertEqual(original['exit_code'],1)
        good=copy.deepcopy(trace)
        next(e for e in good['commands'] if e['args']==['shell','pm','path',PACKAGE]).update(
            exit_code=1,output='')
        validate_adb_trace(good,report,SHA,RUN)
        for rc in (0,1,127):
            allowed=copy.deepcopy(good)
            next(e for e in allowed['commands'] if e['args']==['shell','pm','path',PACKAGE]).update(
                exit_code=rc,output='')
            validate_adb_trace(allowed,report,SHA,RUN)

    def test_30_post_cleanup_contradictions_and_list_failure_veto_signoff(self):
        report,fixture=self.good()
        trace=synthetic_adb_transcript(report)
        report['adb_trace_commands']=len(trace['commands'])
        for which,output,rc in (
            ('path','package:/data/app/still-installed.apk',0),
            ('path','permission denied',1),
            ('path','unrelated command output',0),
            ('list','package:'+PACKAGE,0),
            ('list','package:com.other.app',0),
            ('list','',1),
            ('list','permission denied',1),
        ):
            mutant=copy.deepcopy(trace)
            args=(['shell','pm','path',PACKAGE] if which=='path' else
                  ['shell','pm','list','packages','--user','0',PACKAGE])
            next(e for e in mutant['commands'] if e['args']==args).update(
                exit_code=rc,output=output)
            with self.subTest(which=which,output=output),self.assertRaises(SignoffRefused):
                validate_adb_trace(mutant,report,SHA,RUN)

    def test_26_p04_workflow_requires_transcript_on_both_write_and_signoff(self):
        path=Path(__file__).parents[2]/'.github/workflows/aurora-r3d-p04-recovery.yml'
        workflow=path.read_text()
        self.assertEqual(workflow.count('--trace "$RUNNER_TEMP/R3D_P04_AS_RUN_ADB_TRANSCRIPT.json"'),2)
        self.assertIn('${{ runner.temp }}/R3D_P04_AS_RUN_ADB_TRANSCRIPT.json',workflow)
        signoff=(Path(__file__).parent/'r3d_p04_signoff.py').read_text()
        self.assertIn("for flag in ('receipt','fixture','sha','run-id','out','trace')",signoff)

    def test_27_fixture_partial_cleanup_and_session_ownership_required(self):
        runner=(Path(__file__).parent/'r3d_p04_recovery.py').read_text()
        self.assertIn('self.unabandoned_sessions.add(owned)',runner)
        self.assertIn('self.unabandoned_sessions.remove(owned)',runner)
        self.assertIn('android.assert_no_owned_leaks()',runner)
        self.assertIn('self.assert_owned_temp_absent()',runner)
        p03=(Path(__file__).parent/'r3d_p03_disposable.py').read_text()
        self.assertIn('self.assert_owned_temp_absent()',p03)
        self.assertIn("report['cleanup']='PASS_DISPOSABLE_FIXTURE_AND_TEMP_ABSENT'",p03)
        self.assertIn('emergency session abandonment FAILED',p03)
        fixture=(Path(__file__).parent/'r3d_p03_fixture.py').read_text()
        self.assertIn('actual APK signature no longer matches signed fixture manifest',fixture)
        self.assertIn('actual APK signed manifest package/version changed',fixture)

    def test_15_no_production_shell_controls_in_live_script(self):
        source=(Path(__file__).parent/'r3d_p04_recovery.py').read_text()
        for forbidden in ("'su'",'adb root','--user 10','install-existing',
                          'pm clear','pm uninstall --user','reboot bootloader'):
            with self.subTest(forbidden=forbidden):self.assertNotIn(forbidden,source)
    def test_16_workflow_manual_and_no_reuse(self):
        path=Path(__file__).parents[2]/'.github/workflows/aurora-r3d-p04-recovery.yml'
        data=path.read_text()
        self.assertIn('default: DO_NOT_RUN',data)
        self.assertIn('force-avd-creation: true',data)
        self.assertIn("cancel-in-progress: false",data)
        self.assertNotIn('pull_request:',data)
        self.assertNotIn('    push:',data)
    def test_17_readonly_device_tests_do_not_install(self):
        path=Path(__file__).parents[2]/'app/src/androidTest/java/com/aurora/store/data/artifact/ArtifactR3DRecoveryDeviceTest.kt'
        data=path.read_text()
        self.assertEqual(data.count('@Test fun '),4)
        self.assertNotIn('createSession(',data)
        self.assertNotIn('session.commit(',data)
        self.assertIn('racingSuccessAndRejectionCannotOverwriteTerminalReceipt',data)
    def test_18_callback_serialization_in_post_source(self):
        path=Path(__file__).parents[2]/'app/src/main/java/com/aurora/store/data/artifact/ArtifactInstallSession.kt'
        if not path.exists(): self.skipTest('run this check on source-rehearsed full postimage')
        data=path.read_text()
        self.assertIn('@Synchronized\n    fun recordStatus(',data)
        self.assertIn('@Synchronized\n    fun recordPresentationFailure(',data)
    def test_19_readonly_device_runner_count(self):
        path=Path(__file__).parents[2]/'scripts/ci/r3c03_c02_emulator_ci.sh'
        if not path.exists():self.skipTest('requires full postimage')
        data=path.read_text()
        self.assertIn('ArtifactR3DRecoveryDeviceTest',data)
        self.assertIn('R3D_P04_READONLY_RACE_DEVICE_RECEIPT.json',data)
    def test_20_partial_path_fixed_and_no_app_escalation(self):
        self.assertEqual(PARTIAL_DEVICE_PATH,'/data/local/tmp/r3d_p04_owned_partial.apk')
        self.assertTrue(PACKAGE.startswith('com.aurora.r3d.fixture.'))
    def test_21_mutated_cleanup_absence_refused(self):
        r,f=self.good();o=copy.deepcopy(r);o.pop('cleanup')
        with self.assertRaises(SignoffRefused):assess(o,f,SHA,RUN)
    def test_22_fake_finished_at_refused(self):
        r,f=self.good();o=copy.deepcopy(r);o.pop('finished_at_utc')
        with self.assertRaises(SignoffRefused):assess(o,f,SHA,RUN)

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(P04AdversarialTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():raise SystemExit(1)
    print('R3D_P04_OFFLINE_SECURITY_AND_ADVERSARIAL_TESTS_PASS tests='+str(result.testsRun))
