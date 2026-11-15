#!/usr/bin/env python3
"""P14-P03 source negative mutations to prevent fake installer/Android qualifications."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import r4_p14_p03_source_contract as g
ROOT=Path(__file__).resolve().parents[2]
def reject(fn,code):
 try:fn()
 except g.Refused as e:assert code in str(e),str(e)
 else:raise AssertionError('P14P03_NEGATIVE_UNCAUGHT_'+code)
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
 print('P14P03_SOURCE_NEGATIVES_PASS',len(changes))
if __name__=='__main__':main()
