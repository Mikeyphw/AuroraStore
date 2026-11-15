#!/usr/bin/env python3
"""P14-P03 source negative mutations to prevent fake installer/Android qualifications."""
from pathlib import Path
import json,sys,re,os,subprocess,tempfile
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

def main():
 assert g.source_only(ROOT)
 u=(ROOT/g.UI_TEST).read_text()
 t=(ROOT/g.TEST).read_text();r=(ROOT/g.RUN).read_text()
 a=(ROOT/g.AUDIT).read_text();w=(ROOT/g.WF).read_text()
 changes=[
 (lambda:g.check_ui_test(u.replace('    @Test\n','',1)),'FOUR_REAL_COMPOSE_TESTS'),
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
 (lambda:g.check_audit(a.replace('len(images)==20','len(images)==1')),'AUDIT_MARKER_'),
 (lambda:g.check_audit(a.replace("'release_qualified':False","'release_qualified':True")),'AUDIT_MARKER_'),
 (lambda:g.check_audit(a.replace("'real_installer_qualified':False","'real_installer_qualified':True")),'AUDIT_MARKER_'),
 (lambda:g.check_audit(a.replace("'physical_arm64_qualified':False","'physical_arm64_qualified':True")),'AUDIT_MARKER_'),
 (lambda:g.check_audit(a.replace("'installed_apk_prompt_decline_qualified':False","'installed_apk_prompt_decline_qualified':True")),'AUDIT_MARKER_'),
 (lambda:g.check_workflow(w.replace('  contents: read','  contents: write')),'WORKFLOW_MARKER_'),
 (lambda:g.check_workflow(w.replace('persist-credentials: false','persist-credentials: true')),'WORKFLOW_MARKER_'),
 (lambda:g.check_workflow(w.replace('api-level: 36','api-level: 34')),'WORKFLOW_MARKER_'),
 ]
 for fn,code in changes:reject(fn,code)
 exercise_real_bash_result_gate(r)
 print('P14P03_SOURCE_NEGATIVES_PASS',len(changes))
if __name__=='__main__':main()
