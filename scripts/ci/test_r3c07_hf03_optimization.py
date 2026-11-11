#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Executable offline negative/positive tests for HF03 CI provenance and AVD isolation."""
from __future__ import annotations
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import r3c07_hf03_apk_pair as ci

ROOT=Path(__file__).resolve().parents[2]

class SourceShape(unittest.TestCase):
    def test_targeted_artifact_is_later_than_schema_guard(self):
        s=(ROOT/'.github/workflows/aurora-targeted.yml').read_text()
        self.assertIn('python3 -B scripts/ci/test_r3c07_hf03_optimization.py',s)
        self.assertIn('python3 -B scripts/ci/r3c07_hf03_apk_pair.py publish',s)
        self.assertIn('aurora-targeted-apks-${{ needs.scope.outputs.head_sha }}-${{ github.run_id }}-${{ github.run_attempt }}',s)
        self.assertIn('compression-level: 0',s)
        self.assertLess(s.index('git diff --exit-code -- app/schemas/'),s.index('r3c07_hf03_apk_pair.py publish'))
    def test_r1d_stays_fail_closed(self):
        s=(ROOT/'.github/workflows/aurora-r1d-emulator.yml').read_text()
        self.assertIn('python3 -B scripts/ci/test_r3c07_hf02_receipt.py',s)
        self.assertIn('python3 -B scripts/ci/test_r3c07_hf03_optimization.py',s)
        self.assertIn('actions: read',s)
        self.assertIn("if: steps.apk_reuse.outputs.reused != 'true'",s)
        self.assertIn('r3c07_hf03_apk_pair.py consume',s)
        self.assertIn('r3c07_hf03_apk_pair.py finalize',s)
        self.assertIn('r3c06_live_install:',s)
        self.assertIn('r3c06_bundletool_matrix:',s)
        self.assertIn('r3c06_feature_matrix:',s)
        self.assertIn('bash scripts/ci/r1d2_emulator_ci.sh',s)
        self.assertIn('force-avd-creation: false',s)
        self.assertIn('-no-snapshot-save -no-window',s)
        self.assertIn('if: steps.avd-cache.outputs.cache-hit != \'true\'',s)
        self.assertIn('AVD_SNAPSHOT_CACHE_V2',s)
        self.assertEqual(s.count('uses: actions/cache/restore@'),1)
        self.assertEqual(s.count('uses: actions/cache/save@'),1)
        self.assertLess(s.index('uses: actions/cache/save@'),s.index('name: Execute 40 R1D through R1G Android device tests'))
        self.assertIn('script: bash scripts/ci/r1d2_emulator_ci.sh',s)
        device_script=(ROOT/'scripts/ci/r1d2_emulator_ci.sh').read_text()
        self.assertIn('R3C07_HF03_AVD_REFUSED_STALE_AURORA_PREINSTALL',device_script)
        self.assertNotIn('save-snapshot-after-device-tests',s)
    def test_unsigned_release_parallel_but_all_full_gates_retained(self):
        s=(ROOT/'.github/workflows/aurora-foundation.yml').read_text()
        self.assertIn('unsigned-release:',s)
        self.assertIn('needs: source-contract',s.split('  unsigned-release:',1)[1].split('steps:',1)[0])
        for job in ['source-contract:', 'kotlin-format:', 'root-gradle-format:', 'android-lint:', 'android:', 'unsigned-release:']:
            self.assertIn(job,s)
        self.assertIn('R1G_UNSIGNED_RELEASE_RECEIPT.json',s)

class HistoricalR1DGraphContract(unittest.TestCase):
    # Execute the *exact* HF05 block from the historical P5 source contract,
    # avoiding a mocked duplicate of the assertion that previously failed.
    @staticmethod
    def evaluate(actual_workflow: str) -> None:
        legacy=(ROOT/'scripts/ci/test_r3c06_p5_source_contract.py').read_text(encoding='utf-8')
        start='# HF05: one clean-snapshot bootstrap, one historical qualification runner.'
        end="assert 'R3C06_ALLOW_LIVE_INSTALL' not in R1D.split('name: Build vanillaDebug application and instrumentation APKs')[0]"
        assert legacy.count(start)==1, 'HF05 historical invariant absent'
        assert legacy.count(end)==1, 'historical opt-in invariant dropped'
        fragment=start+legacy.split(start,1)[1].split(end,1)[0]
        compile(fragment,'HF05_p5_emulator_graph_fragment.py','exec')
        exec(fragment,{'R1D':actual_workflow})

    def test_exactly_one_warmup_and_one_qualification(self):
        workflow=(ROOT/'.github/workflows/aurora-r1d-emulator.yml').read_text(encoding='utf-8')
        self.evaluate(workflow)
        self.assertEqual(workflow.count('uses: ReactiveCircus/android-emulator-runner@'),2)
        self.assertEqual(workflow.count('bash scripts/ci/r1d2_emulator_ci.sh'),1)

    def test_legacy_r1d2_entrypoint_preserved_and_preinstall_guard_ordered(self):
        # Preserve historical R1D2/R1E/R1F/R1G contract text exactly, instead
        # of relaxing several source gates to accept a new qualification form.
        source=(ROOT/'scripts/ci/check_r1d2.py').read_text(encoding='utf-8')
        workflow=(ROOT/'.github/workflows/aurora-r1d-emulator.yml').read_text(encoding='utf-8')
        script=(ROOT/'scripts/ci/r1d2_emulator_ci.sh').read_text(encoding='utf-8')
        self.assertIn("'script: bash scripts/ci/r1d2_emulator_ci.sh' in flow",source)
        self.assertEqual(workflow.count('script: bash scripts/ci/r1d2_emulator_ci.sh'),1)
        self.assertIn('script: bash scripts/ci/r1d2_emulator_ci.sh',workflow)
        def require_ordered_clean_snapshot_guard(candidate:str):
            anchor='bash scripts/ci/r1d_emulator_ci.sh'
            required=('R3C07_PREINSTALL_PACKAGE_INVENTORY',
                      'pm list packages --user 0',
                      'R3C07_HF05_AVD_REFUSED_NOT_API36',
                      'R3C07_HF05_AVD_REFUSED_EMPTY_PACKAGE_INVENTORY',
                      'R3C07_HF03_AVD_REFUSED_STALE_AURORA_PREINSTALL')
            return (all(candidate.count(token)>=1 for token in required)
                    and candidate.count(anchor)==1
                    and all(candidate.index(token)<candidate.index(anchor) for token in required))
        self.assertTrue(require_ordered_clean_snapshot_guard(script))
        negative={
            'no API check':script.replace('R3C07_HF05_AVD_REFUSED_NOT_API36','NO_API_GUARD'),
            'no package listing':script.replace('pm list packages --user 0','pm list disabled'),
            'missing empty inventory guard':script.replace('R3C07_HF05_AVD_REFUSED_EMPTY_PACKAGE_INVENTORY','NO_EMPTY_INVENTORY_CHECK'),
            'missing stale package refusal':script.replace('R3C07_HF03_AVD_REFUSED_STALE_AURORA_PREINSTALL','NO_STALE_PACKAGE_CHECK'),
            'guard moved after APK installation':script.replace('bash scripts/ci/r1d_emulator_ci.sh','echo unsafe',1).replace('R3C07_HF03_AVD_REFUSED_STALE_AURORA_PREINSTALL', 'NO_STALE_PACKAGE_CHECK')+'\nbash scripts/ci/r1d_emulator_ci.sh\n',
            'extra install invocation':script+'\nbash scripts/ci/r1d_emulator_ci.sh\n',
        }
        for label,mutant in negative.items():
            with self.subTest(case=label):
                self.assertFalse(require_ordered_clean_snapshot_guard(mutant),label)

    def test_preinstall_android_shell_refuses_stale_or_unknown_inventory(self):
        # Execute the actual before-install shell prefix with a fake adb binary.
        # No Android emulator, APK installation, or live OS state is mutated.
        shell=(ROOT/'scripts/ci/r1d2_emulator_ci.sh').read_text(encoding='utf-8')
        boundary='# Retain the previously qualified 14-case R1D gate in the same hosted emulator.'
        self.assertEqual(shell.count(boundary),1)
        prefix=shell.split(boundary,1)[0]+'\necho R3C07_HF05_CLEAN_PREINSTALL_PASS\n'
        with tempfile.TemporaryDirectory(prefix='r3c07-hf05-adb-') as td:
            tmp=Path(td)
            adb=tmp/'adb'
            adb.write_text('''#!/usr/bin/env bash
set -euo pipefail
if [[ "$*" == 'shell getprop ro.build.version.sdk' ]]; then
  if [[ "${HF05_CASE:-}" == bad_api ]]; then echo 35; else echo 36; fi
elif [[ "$*" == 'shell pm list packages --user 0' ]]; then
  case "${HF05_CASE:-}" in
    clean) printf 'package:android\npackage:com.android.settings\n' ;;
    main) printf 'package:android\npackage:com.aurora.store.debug\n' ;;
    test) printf 'package:android\npackage:com.aurora.store.debug.test\n' ;;
    empty) printf '' ;;
    broken) exit 1 ;;
    bad_api) printf 'package:android\n' ;;
    *) exit 2 ;;
  esac
else exit 3
fi
''')
            adb.chmod(0o755)
            for name,ok in [('clean',True),('main',False),('test',False),
                            ('empty',False),('broken',False),('bad_api',False)]:
                with self.subTest(case=name):
                    env={**os.environ,'RUNNER_TEMP':td,'HF05_CASE':name,
                         'PATH':td+os.pathsep+os.environ.get('PATH','')}
                    proc=subprocess.run(['bash','-c',prefix],cwd=ROOT,env=env,
                                         text=True,capture_output=True,timeout=8)
                    self.assertEqual(proc.returncode==0,ok,proc.stderr+' '+proc.stdout)
                    if ok:
                        self.assertIn('R3C07_HF05_CLEAN_PREINSTALL_PASS',proc.stdout)
                    else:
                        self.assertNotIn('R3C07_HF05_CLEAN_PREINSTALL_PASS',proc.stdout)

    def test_unsafe_duplicate_or_mutated_graph_is_rejected(self):
        workflow=(ROOT/'.github/workflows/aurora-r1d-emulator.yml').read_text(encoding='utf-8')
        action='uses: ReactiveCircus/android-emulator-runner@a421e43855164a8197daf9d8d40fe71c6996bb0d'
        bootstrap='Generate pre-install AVD snapshot only on cache miss'
        cases={
            'third runner inserted':workflow+'\n      - '+action+'\n',
            'warmup runner missing':workflow.replace(action,'uses: REVOKED/action@invalid',1),
            'qualification runner missing':workflow[::-1].replace(action[::-1],'uses: REVOKED/action@invalid'[::-1],1)[::-1],
            'cache-miss conditional bypassed':workflow.replace("if: steps.avd-cache.outputs.cache-hit != 'true'",'if: always()',1),
            'snapshot save omitted':workflow.replace('uses: actions/cache/save@8b402f58fbc84540c8b491a91e594a4576fec3d7','uses: DISABLED/cache-save@invalid',1),
            'warmup runs qualification tests':workflow.replace('echo R3C07_HF03_PREINSTALL_AVD_SNAPSHOT_INITIALIZED', 'bash scripts/ci/r1d2_emulator_ci.sh',1),
            'qualification snapshot saved':workflow.replace('-no-snapshot-save -no-window','-no-window',1),
            'qualification duplicated in shell':workflow.replace('bash scripts/ci/r1d2_emulator_ci.sh','bash scripts/ci/r1d2_emulator_ci.sh\n            bash scripts/ci/r1d2_emulator_ci.sh',1),
            'bootstrap marker lost':workflow.replace(bootstrap,'Create arbitrary emulator',1),
            'pinned emulator action changed':workflow.replace(action,action.replace('a421e4','000000'),1),
        }
        for name,mutated in cases.items():
            with self.subTest(case=name):
                self.assertNotEqual(mutated,workflow)
                with self.assertRaises(AssertionError):
                    self.evaluate(mutated)

class PairNegative(unittest.TestCase):
    def setUp(self):
        self.d=tempfile.TemporaryDirectory(prefix='r3c07-ci-opt-')
        self.addCleanup(self.d.cleanup)
        self.root=Path(self.d.name)
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        subprocess.run(['git','-C',str(self.root),'config','user.name','Test'],check=True)
        subprocess.run(['git','-C',str(self.root),'config','user.email','test@example.invalid'],check=True)
        (self.root/'README').write_text('fixture\n')
        subprocess.run(['git','-C',str(self.root),'add','README'],check=True)
        subprocess.run(['git','-C',str(self.root),'commit','-qm','test'],check=True)
        self.sha=subprocess.check_output(['git','-C',str(self.root),'rev-parse','HEAD'],text=True).strip()
        self.env=mock.patch.dict(os.environ,{'GITHUB_REPOSITORY':ci.REPO,
            'GITHUB_EVENT_NAME':'pull_request','GITHUB_RUN_ID':'12345',
            'GITHUB_RUN_ATTEMPT':'1'},clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        for role,rel in ci.ROLE_PATHS.items():
            path=self.root/rel
            path.mkdir(parents=True,exist_ok=True)
            (path/f'{role}.apk').write_bytes(b'PK fixture '+role.encode())
        # A deterministic fake Android build-tools shim, NOT used for real qualification.
        tool=self.root/'fake-android-tool'
        tool.write_text('''#!/usr/bin/env python3
import sys
if 'verify' in sys.argv:
 print('Verified using v2 scheme: true\nNumber of signers: 1\nV2 Signer: certificate SHA-256 digest: ' + 'a1'*32 + '\nV3.0 Signer: certificate SHA-256 digest: ' + 'a1'*32)
elif 'badging' in sys.argv:
 role='androidTest' if 'androidTest' in sys.argv[-1] else 'app'
 print("package: name='com.aurora.store.debug" + (".test" if role=='androidTest' else '') + "'")
elif 'xmltree' in sys.argv:
 print('E: instrumentation android:targetPackage="com.aurora.store.debug" android:name="HiltInstrumentationTestRunner"')
''')
        tool.chmod(0o755)
        self.mocktool=mock.patch.object(ci,'find_tool',return_value=str(tool))
        self.mocktool.start()
        self.addCleanup(self.mocktool.stop)
        real_run=ci.run
        def simulated_android_cli(argv, *, binary=False, timeout=120):
            if argv and argv[0]==str(tool):
                if 'verify' in argv:
                    return ('Verified using v2 scheme: true\nNumber of signers: 1\n'
                            'V2 Signer: certificate SHA-256 digest: ' + 'a1'*32 + '\n'
                            'V3.0 Signer: certificate SHA-256 digest: ' + 'a1'*32)
                if 'badging' in argv:
                    role='androidTest' if 'androidTest' in argv[-1] else 'app'
                    return "package: name='com.aurora.store.debug" + ('.test' if role=='androidTest' else '') + "'"
                if 'xmltree' in argv:
                    return 'E: instrumentation android:targetPackage="com.aurora.store.debug" android:name="HiltInstrumentationTestRunner"'
                raise AssertionError('unexpected simulated Android CLI command: '+repr(argv))
            return real_run(argv,binary=binary,timeout=timeout)
        fake_run=mock.patch.object(ci,'run',side_effect=simulated_android_cli)
        fake_run.start()
        self.addCleanup(fake_run.stop)

    # HF06: actual SDK37 uses per-scheme certificate lines. The old mock only
    # covered SDK36 and missed the hosted regression. Both formats remain
    # supported, but v2/v3 verified cryptographic evidence is mandatory.
    @staticmethod
    def _sdk37(scheme_v2=True, scheme_v3=True, digest_a='a1', digest_b='a1'):
        lines=['Verified using v2 scheme: '+str(scheme_v2).lower(),
               'Verified using v3 scheme: '+str(scheme_v3).lower(),
               'Number of signers: 1',
               'V2 Signer: certificate SHA-256 digest: '+digest_a*32,
               'V3.0 Signer: certificate SHA-256 digest: '+digest_b*32]
        return '\n'.join(lines)

    def _with_signature(self, output):
        original=ci.run
        def fake(argv, *, binary=False, timeout=120):
            if len(argv)>1 and argv[1]=='verify':
                return output
            return original(argv,binary=binary,timeout=timeout)
        return mock.patch.object(ci,'run',side_effect=fake)

    def test_hf06_sdk37_v2_v3_single_signer_accepted(self):
        with self._with_signature(self._sdk37()):
            cert=ci.check_apk(self.root/ci.ROLE_PATHS['app']/'app.apk','app')
        self.assertEqual(cert['signer_sha256'],'a1'*32)

    def test_hf06_legacy_signer_output_with_verified_scheme_accepted(self):
        out=('Verified using v2 scheme: true\nNumber of signers: 1\n'
             'Signer #1 certificate SHA-256 digest: '+'a1'*32)
        with self._with_signature(out):
            cert=ci.check_apk(self.root/ci.ROLE_PATHS['app']/'app.apk','app')
        self.assertEqual(cert['signer_sha256'],'a1'*32)

    def test_hf06_signer_mismatches_and_unsafe_evidence_refused(self):
        good=self._sdk37()
        samples={
            'different_certs_across_schemes':self._sdk37(digest_b='b2'),
            'all_schemes_unverified':self._sdk37(False,False),
            'duplicate_v2_label':good+'\nV2 Signer: certificate SHA-256 digest: '+'a1'*32,
            'multiple_signer_count':good.replace('Number of signers: 1','Number of signers: 2'),
            'explicit_second_signer':good+'\nV2 Signer #2: certificate SHA-256 digest: '+'a1'*32,
            'malformed_label':good.replace('V2 Signer:','Totally trusted Signer:'),
            'digest_without_label':good.replace('V2 Signer: certificate','certificate'),
            'no_certificate': 'Verified using v2 scheme: true\nNumber of signers: 1',
            'duplicate_scheme_status':'Verified using v2 scheme: true\n'+good,
        }
        path=self.root/ci.ROLE_PATHS['app']/'app.apk'
        for name,out in samples.items():
            with self.subTest(name=name), self._with_signature(out):
                with self.assertRaises(ci.Refused):
                    ci.check_apk(path,'app')

    def test_hf06_android36_scoped_verification_invocation(self):
        original=ci.run
        seen=[]
        def capture(argv, *, binary=False, timeout=120):
            if len(argv)>1 and argv[1]=='verify':
                seen.append(list(argv))
            return original(argv,binary=binary,timeout=timeout)
        with mock.patch.object(ci,'run',side_effect=capture):
            ci.check_apk(self.root/ci.ROLE_PATHS['app']/'app.apk','app')
        self.assertEqual(len(seen),1)
        args=seen[0]
        self.assertEqual(args[1:4],['verify','--verbose','--print-certs'])
        self.assertEqual(args[4:8],['--min-sdk-version','36','--max-sdk-version','36'])

    def test_publish_signs_exact_run_and_file_bytes(self):
        out=self.root/'pair'
        ci.publish(self.root,out,self.sha)
        data=json.loads((out/'manifest.json').read_text())
        self.assertEqual(data['source_sha'],self.sha)
        self.assertEqual(data['targeted_run_id'],'12345')
        self.assertFalse(data['release_qualified'])
        self.assertEqual(data['files']['app']['package'],ci.APP_PKG)
        self.assertTrue(ci.validate_pair(out/'app.apk',out/'androidTest.apk'))

    def test_changed_source_refused(self):
        with self.assertRaises(ci.Refused):
            ci.publish(self.root,self.root/'pair','f'*40)

    def test_mismatched_apk_refused(self):
        out=self.root/'pair'
        ci.publish(self.root,out,self.sha)
        records={n:(out/n).read_bytes() for n in ('app.apk','androidTest.apk','manifest.json')}
        doc=json.loads(records['manifest.json'])
        ci.verify_doc(doc,self.sha,12345,records)
        records['app.apk']+=b'source tamper'
        with self.assertRaises(ci.Refused):
            ci.verify_doc(doc,self.sha,12345,records)
        records['app.apk']=(out/'app.apk').read_bytes()
        doc['source_sha']='b'*40
        with self.assertRaises(ci.Refused):
            ci.verify_doc(doc,self.sha,12345,records)

    def test_broken_run_jobs_refused(self):
        good={'id':12345,'path':ci.WORKFLOW,'head_sha':self.sha,'head_branch':ci.BRANCH,
              'event':'pull_request','status':'completed','conclusion':'success',
              'repository':{'full_name':ci.REPO}}
        self.assertTrue(ci.qualifies_run(good,self.sha))
        for change in [{'status':'queued'},{'conclusion':'failure'},{'head_sha':'f'*40},
                       {'event':'workflow_dispatch'},{'path':'other.yml'},
                       {'repository':{'full_name':'other/repository'}}]:
            self.assertFalse(ci.qualifies_run({**good,**change},self.sha))

    def test_selected_run_rejects_skipped_or_wrong_source_jobs(self):
        runmeta={'id':12345,'path':ci.WORKFLOW,'head_sha':self.sha,
                 'head_branch':ci.BRANCH,'event':'pull_request','status':'completed',
                 'conclusion':'success','repository':{'full_name':ci.REPO}}
        source={'total_count':1,'workflow_runs':[runmeta]}
        jobs=[{'name':name,'head_sha':self.sha,'conclusion':'success','status':'completed'}
              for name in sorted(ci.TEST_JOBS)]
        def fake_api(path):
            if '/jobs?' in path:return {'total_count':3,'jobs':jobs}
            return source
        with mock.patch.object(ci,'api',side_effect=fake_api):
            self.assertEqual(ci.selected_run(self.sha)['id'],12345)
            jobs[1]['conclusion']='skipped'
            self.assertIsNone(ci.selected_run(self.sha))
            jobs[1]['conclusion']='success'
            jobs[2]['head_sha']='0'*40
            self.assertIsNone(ci.selected_run(self.sha))

    def test_old_uninstrumented_run_falls_back_to_build(self):
        for role,rel in ci.ROLE_PATHS.items():
            for p in (self.root/rel).glob('*.apk'): p.unlink()
        with mock.patch.object(ci,'selected_run',return_value=None):
            output=self.root/'$GITHUB_OUTPUT'
            with mock.patch.dict(os.environ,{'GITHUB_EVENT_NAME':'workflow_dispatch'},clear=False):
                ci.consume(self.root,self.root/'tmp',self.sha,output)
            self.assertEqual(output.read_text(),'reused=false\n')

    def test_reuse_consumes_exact_artifact_and_seals_signed_bytes(self):
        out=self.root/'pair'
        ci.publish(self.root,out,self.sha)
        records={p.name:p.read_bytes() for p in out.iterdir()}
        for role,rel in ci.ROLE_PATHS.items():
            for p in (self.root/rel).glob('*.apk'):p.unlink()
        runmeta={'id':12345,'run_attempt':1}
        artifact={'id':555,'name':f'aurora-targeted-apks-{self.sha}-12345-1'}
        with mock.patch.dict(os.environ,{'GITHUB_EVENT_NAME':'workflow_dispatch',
                                         'GITHUB_RUN_ID':'98765'},clear=False), \
             mock.patch.object(ci,'selected_run',return_value=runmeta), \
             mock.patch.object(ci,'matching_artifact',return_value=artifact), \
             mock.patch.object(ci,'download_artifact',return_value=records):
            output=self.root/'gh-output'
            scratch=self.root/'reused'
            ci.consume(self.root,scratch,self.sha,output)
            self.assertEqual(output.read_text(),'reused=true\n')
            evidence=self.root/'as-run.json'
            ci.finalize(self.root,scratch,self.sha,evidence,True)
            receipt=json.loads(evidence.read_text())
            self.assertEqual(receipt['mode'],'EXACT_TARGETED_ARTIFACT')
            self.assertEqual(receipt['targeted_run_id'],'12345')
            self.assertEqual(receipt['run_id'],'98765')
            self.assertEqual(receipt['source_sha'],self.sha)
            self.assertFalse(receipt['installation_qualified'])

    def test_tampered_targeted_artifact_never_falls_back(self):
        out=self.root/'pair'
        ci.publish(self.root,out,self.sha)
        records={p.name:p.read_bytes() for p in out.iterdir()}
        records['androidTest.apk']+=b'silent tamper'
        for role,rel in ci.ROLE_PATHS.items():
            for p in (self.root/rel).glob('*.apk'):p.unlink()
        with mock.patch.dict(os.environ,{'GITHUB_EVENT_NAME':'workflow_dispatch'},clear=False), \
             mock.patch.object(ci,'selected_run',return_value={'id':12345,'run_attempt':1}), \
             mock.patch.object(ci,'matching_artifact',return_value={'id':555}), \
             mock.patch.object(ci,'download_artifact',return_value=records):
            with self.assertRaises(ci.Refused):
                ci.consume(self.root,self.root/'reused',self.sha,self.root/'gh-output')
        self.assertFalse((self.root/'gh-output').exists())
        self.assertFalse(any(any((self.root/rel).glob('*.apk')) for rel in ci.ROLE_PATHS.values()))

    def test_unknown_source_fails_without_network(self):
        with mock.patch.dict(os.environ,{'GITHUB_REPOSITORY':'invalid/other'},clear=False):
            with self.assertRaises(ci.Refused):ci.exact_head(self.root,self.sha)

if __name__=='__main__':
    unittest.main(verbosity=2)
