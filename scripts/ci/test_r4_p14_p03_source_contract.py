#!/usr/bin/env python3
"""P14-P03 source negative mutations to prevent fake installer/Android qualifications."""
from pathlib import Path
import json,sys,re,os,subprocess,tempfile,types,importlib.util,struct
sys.path.insert(0,str(Path(__file__).resolve().parent))
import r4_p14_p03_source_contract as g
ROOT=Path(__file__).resolve().parents[2]
def reject(fn,code):
 try:fn()
 except g.Refused as e:assert code in str(e),str(e)
 else:raise AssertionError('P14P03_NEGATIVE_UNCAUGHT_'+code)
def exercise_real_bash_result_gate(r):
 """Actually execute extracted production run_class with fake instrumentation I/O.

 No adb, emulator, network, installed package, or background Gradle involved.
 """
 match=re.search(r'(?ms)^run_class\(\) \{\n.*?^\}',r)
 assert match,'P14P03_RUN_CLASS_NOT_FOUND'
 body=match.group(0)
 samples=(
  (1,'OK (1 test)',True),
  (4,'OK (4 tests)',True),
  (9,'OK (9 tests)',True),
  (1,'OK (1 tests)',False),
  (9,'OK (9 test)',False),
  (1,'OK (1 test)',False,'missing-instrumentation-code'),
  (1,'OK (1 test)',False,'failure-marker'),
 )
 with tempfile.TemporaryDirectory(prefix='p14p03-hf02-fake-android-') as work:
  root=Path(work)
  for i,sample in enumerate(samples):
   count,line,ok,*variants=sample
   variant=variants[0] if variants else ''
   output='\n'.join((
    'INSTRUMENTATION_STATUS: test=syntheticSingleMethod',
    line,
    'INSTRUMENTATION_CODE: -1' if variant!='missing-instrumentation-code' else '',
    'FAILURES!!!' if variant=='failure-marker' else '',
   ))+'\n'
   fake=root/f'fake-{i}.txt';fake.write_text(output)
   cmd=f"""set -euo pipefail
OUT='{root}/out{i}'; RUNNER=fake-runner; FAKE_LOG='{fake}'
mkdir -p "$OUT/logs/full"
collect_failed() {{ :; }}
timeout() {{ cat "$FAKE_LOG"; }}
{body}
run_class full light test Fake.Class {count}
"""
   p=subprocess.run(['bash','-c',cmd],capture_output=True,text=True,timeout=20)
   assert (p.returncode==0)==ok,(i,p.returncode,p.stdout,p.stderr)
 print('P14P03_HF02_BASH_EXIT_CONTRACT_PASS',len(samples))

def exercise_widget_audit_gate(root):
    """Execute the production widget policy; never mask CRC or blank evidence."""
    original=sys.modules.get('r4_p05_screenshot_audit')
    module=types.ModuleType('r4_p05_screenshot_audit')
    current={'failure':None}
    def parser(path):
        if current['failure'] is not None:raise ValueError(current['failure'])
        return {'width':720,'height':1600,'sha256':'0'*64,
                'non_background_samples':52,'sampled_colors':14}
    module.load_pixels=parser
    sys.modules['r4_p05_screenshot_audit']=module
    try:
        spec=importlib.util.spec_from_file_location(
            'p14p03_hf03_real_audit',root/g.AUDIT)
        assert spec and spec.loader
        audit=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audit)
        assert audit.widget_sample_policy(12,8)
        assert audit.widget_sample_policy(35,15)
        assert not audit.widget_sample_policy(0,15)
        assert not audit.widget_sample_policy(11,15)
        assert not audit.widget_sample_policy(35,7)
        with tempfile.TemporaryDirectory(prefix='p14p03-hf03-pixel-') as t:
            path=Path(t)/'light'/'r4_p14p03_queued.png'
            path.parent.mkdir()
            b=bytearray(2100);b[:8]=b'\x89PNG\r\n\x1a\n'
            struct.pack_into('>II',b,16,720,1600)
            path.write_bytes(b)
            current['failure']=None
            assert audit.load_widget_png(path)['non_background_samples']==52
            current['failure']='R4_P06_REFUSED_BLANK_SCREENSHOT_light_r4_p14p03_queued.png_changed=35_colors=15'
            parsed=audit.load_widget_png(path)
            assert parsed['visual_gate']=='isolated_widget_nonblank'
            assert parsed['non_background_samples']==35
            current['failure']='R4_P06_REFUSED_BLANK_SCREENSHOT_light_r4_p14p03_queued.png_changed=0_colors=15'
            try:audit.load_widget_png(path)
            except ValueError as err: assert 'SPARSE_WIDGET_CONTENT_' in str(err)
            else:raise AssertionError('HF03_BLANK_FRAME_ACCEPTED')
            current['failure']='R4_P06_REFUSED_PNG_CRC_r4_p14p03_queued.png'
            try:audit.load_widget_png(path)
            except ValueError as err: assert 'PNG_CRC' in str(err)
            else:raise AssertionError('HF03_BAD_CRC_MASKED')
            current['failure']='R4_P06_REFUSED_BLANK_SCREENSHOT_dark_r4_p14p03_queued.png_changed=35_colors=15'
            try:audit.load_widget_png(path)
            except ValueError as err: assert 'SPARSE_WIDGET_CONTEXT_' in str(err)
            else:raise AssertionError('HF03_THEME_CONTEXT_MASKED')
    finally:
        if original is None:sys.modules.pop('r4_p05_screenshot_audit',None)
        else:sys.modules['r4_p05_screenshot_audit']=original
    print('P14P03_HF03_ISOLATED_PIXEL_AUDIT_PASS',8)

def main():
 assert g.source_only(ROOT)
 u=(ROOT/g.UI_TEST).read_text()
 t=(ROOT/g.TEST).read_text();r=(ROOT/g.RUN).read_text()
 a=(ROOT/g.AUDIT).read_text();w=(ROOT/g.WF).read_text()
 changes=[
 (lambda:g.check_ui_test(u.replace('    @Test\n','',1)),'EIGHT_REAL_COMPOSE_TESTS'),
 (lambda:g.check_ui_test(u.replace('automation.takeScreenshot()','null')),'UI_TEST_MARKER_'),
 (lambda:g.check_ui_test(u.replace('contentSamples >= 12','contentSamples >= 0')),'WIDGET_SCREENSHOT_GUARD_'),
 (lambda:g.check_ui_test(u.replace('delta >= 52','delta >= 0')),'WIDGET_SCREENSHOT_GUARD_'),
 (lambda:g.check_ui_test(u.replace('for (attempt in 1..10)','for (attempt in 1..1000)')),'WIDGET_SCREENSHOT_GUARD_'),
 (lambda:g.check_ui_test(u.replace('SystemClock.sleep(300)','SystemClock.sleep(0)')),'WIDGET_SCREENSHOT_GUARD_'),
 (lambda:g.check_ui_test(u.replace('file.length() > 2048L','file.length() > 0L')),'WIDGET_SCREENSHOT_GUARD_'),
 (lambda:g.check_ui_test(u.replace('P14P03_REFUSED_BLANK_WIDGET_SCREENSHOT','ALLOW_BLANK')),'WIDGET_SCREENSHOT_GUARD_'),
 (lambda:g.check_ui_test(u.replace('Bitmap.CompressFormat.PNG','Bitmap.CompressFormat.JPEG')),'WIDGET_SCREENSHOT_GUARD_'),
 (lambda:g.check_ui_test(u.replace('frame.width >= 320 && frame.height >= 480','true')),'WIDGET_SCREENSHOT_GUARD_'),
 (lambda:g.check_ui_test(u.replace('frame.recycle()','// frame kept')),'WIDGET_SCREENSHOT_GUARD_'),
 (lambda:g.check_ui_test(u.replace('image.recycle()','// accepted kept')),'WIDGET_SCREENSHOT_GUARD_'),
 (lambda:g.check_ui_test(u.replace('automation.takeScreenshot()','R4ScreenshotEvidence.capture(')),'UI_TEST_MARKER_'),
 (lambda:g.check_ui_test(u+'\n// captureToImage('),'FLAKY_OLD_SCREENSHOT_CAPTURE'),
 (lambda:g.check_test(t.replace('    @Test\n','',1)),'EIGHT_REAL_ANDROID_TESTS'),
 (lambda:g.check_test(t.replace('Room.inMemoryDatabaseBuilder','Room.fakeDatabaseBuilder')),'TEST_MARKER_'),
 (lambda:g.check_test(t.replace('activeUpdateCancelBlocksLateProgressAndCompletion','skipCancel')),'TEST_MARKER_'),
 (lambda:g.check_test(t.replace('installerUserDeclineWithCachedApkRemainsPendingNotInstalled','fakeDecline')),'TEST_MARKER_'),
 (lambda:g.check_test(t.replace('missingSessionAndApkCannotRemainInstallingForever','skipRecovery')),'TEST_MARKER_'),
 (lambda:g.check_test(t.replace('InstallResultPolicy.next(','FakePolicy.next(')),'TEST_MARKER_'),
 (lambda:g.check_test(t.replace('dao.transitionInstallAttempt(','dummy.transition(')),'TEST_MARKER_'),
 (lambda:g.check_test(t.replace('hasCachedApks = true','hasCachedApks = null')),'TEST_MARKER_'),
 (lambda:g.check_test(t+'\n// PackageInstaller('),'TEST_FORBIDDEN_'),
 (lambda:g.check_test(t+'\n// createSession('),'TEST_FORBIDDEN_'),
 (lambda:g.check_test(t+'\n// su -c'),'TEST_FORBIDDEN_'),
 (lambda:g.check_run(r.replace('for profile in full compact;do','for profile in full;do')),'RUN_MARKER_'),
 (lambda:g.check_run(r.replace('for mode in light dark;do','for mode in dark;do')),'RUN_MARKER_'),
 (lambda:g.check_run(r.replace('run_class "$profile" "$mode" download-ui "$DOWNLOAD_UI" 8',
                               'run_class "$profile" "$mode" download-ui "$DOWNLOAD_UI" 4')),
  'RUN_MARKER_'),
 (lambda:g.check_run(r + '\n# run_class "$profile" "$mode" final-ui "$FINAL_UI" 4'),
  'LEGACY_BLANK_SCREENSHOT_PRODUCER'),
 (lambda:g.check_ui_test(u.replace('r1g_cancelled.png','hidden.png')),'UI_TEST_MARKER_'),
 (lambda:g.check_ui_test(u.replace('missingCachedApkShowsRetryWithoutInstallation',
                              'fakePendingInstall')),'UI_TEST_MARKER_'),
 (lambda:g.check_ui_test(u.replace('cancelledShowsAccurateStatusWithoutFakeTransferStats',
                              'fakeCancelled')),'UI_TEST_MARKER_'),
 (lambda:g.check_run(r.replace('trap restore_display EXIT','true')),'RUN_MARKER_'),
 (lambda:g.check_run(r.replace('timeout 840 adb shell am instrument','adb shell am instrument')),'RUN_MARKER_'),
 (lambda:g.check_run(r.replace('r4_p14_p03_evidence_audit.py','echo PASSED')),'RUN_MARKER_'),
 (lambda:g.check_run(r.replace('adb logcat -d -t 1500','echo empty')),'RUN_MARKER_'),
 (lambda:g.check_run(r+'\nadb -s localhost:5555 shell id'),'PHYSICAL_ADB'),
 (lambda:g.check_run(r.replace("if (( count == 1 )); then expected='OK (1 test)'; fi",'true')),
   'RUN_RESULT_CONTRACT_'),
 (lambda:g.check_run(r.replace('local expected="OK ($count tests)"',
                              'local expected="OK ($count test)"')),'RUN_RESULT_CONTRACT_'),
 (lambda:g.check_run(r.replace('! grep -Fxq "$expected" "$log"',
                              '! grep -Fxq "OK ($count tests)" "$log"')),
   'RUN_RESULT_CONTRACT_'),
 (lambda:g.check_run(r.replace("! grep -Fxq 'INSTRUMENTATION_CODE: -1' \"$log\"",'false')),
   'RUN_RESULT_CONTRACT_'),
 (lambda:g.check_run(r.replace('if (( count == 1 )); then expected=\'OK (1 test)\'; fi',
                              'if (( count == 1 )); then expected=\'OK (1 tests)\'; fi')),
   'RUN_RESULT_CONTRACT_'),
 (lambda:g.check_audit(a.replace('total==76','total==4')),'AUDIT_MARKER_'),
 (lambda:g.check_audit(a.replace('12 <= changed < 42 and colors >= 8',
                                 '0 <= changed < 42 and colors >= 8')),'AUDIT_MARKER_'),
 (lambda:g.check_audit(a.replace('load_widget_png(path)','png.load_pixels(path)')),
  'AUDIT_MARKER_'),
 (lambda:g.check_audit(a.replace('SPARSE_WIDGET_CONTENT_','ALLOW_BLANK_WIDGET')),
  'AUDIT_MARKER_'),
 (lambda:g.check_audit(a.replace("'visual_gate':'isolated_widget_nonblank'",
                                 "'visual_gate':'unguarded'")),'AUDIT_MARKER_'),
 (lambda:g.check_audit(a.replace('len(images)==20','len(images)==1')),'AUDIT_MARKER_'),
 (lambda:g.check_audit(a.replace("'release_qualified':False","'release_qualified':True")),'AUDIT_MARKER_'),
 (lambda:g.check_audit(a.replace("'real_installer_qualified':False","'real_installer_qualified':True")),'AUDIT_MARKER_'),
 (lambda:g.check_audit(a.replace("'physical_arm64_qualified':False","'physical_arm64_qualified':True")),'AUDIT_MARKER_'),
 (lambda:g.check_audit(a.replace("'installed_apk_prompt_decline_qualified':False","'installed_apk_prompt_decline_qualified':True")),'AUDIT_MARKER_'),
 (lambda:g.check_workflow(w.replace('  contents: read','  contents: write')),'WORKFLOW_MARKER_'),
 (lambda:g.check_workflow(w.replace('persist-credentials: false','persist-credentials: true')),'WORKFLOW_MARKER_'),
 (lambda:g.check_workflow(w.replace('api-level: 36','api-level: 34')),'WORKFLOW_MARKER_'),
 (lambda:g.check_workflow(w.replace('P14P03_AGP_RESOLUTION_RETRY','DISABLED_RETRY')),'WORKFLOW_MARKER_'),
 (lambda:g.check_workflow(w.replace('P14P03_NON_TRANSIENT_GRADLE_FAILURE','ALLOW_ANY_BUILD_FAILURE')),'WORKFLOW_MARKER_'),
 ]
 for fn,code in changes:reject(fn,code)
 exercise_real_bash_result_gate(r)
 exercise_widget_audit_gate(ROOT)
 print('P14P03_SOURCE_NEGATIVES_PASS',len(changes))
if __name__=='__main__':main()
