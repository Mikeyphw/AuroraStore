#!/usr/bin/env python3
"""P14-P03 additive source guard: lock PR4, original P13 approval and real API36 tests."""
from __future__ import annotations
import argparse,json,re,subprocess,sys
from pathlib import Path

BASE='6e9418baaefadd4afcf4320b4a4b193546e66ec7'
BRANCH='feature/aurora-r4-p14-p03-hosted-lifecycle-20261115'
TEST='app/src/androidTest/java/com/aurora/store/data/installer/R4P14P03LifecycleDeviceTest.kt'
RUN='scripts/ci/r4_p14_p03_emulator_acceptance.sh'
AUDIT='scripts/ci/r4_p14_p03_evidence_audit.py'
CONTRACT='scripts/ci/r4_p14_p03_source_contract.py'
UNIT='scripts/ci/test_r4_p14_p03_source_contract.py'
DOC='docs/r4/R4_P14_P03_HOSTED_LIFECYCLE.md'
WF='.github/workflows/aurora-r4-p14-p03-lifecycle.yml'
UI_TEST='app/src/androidTest/java/com/aurora/store/compose/ui/r4/R4P14P03DownloadUiDeviceTest.kt'
PATHS={TEST,UI_TEST,RUN,AUDIT,CONTRACT,UNIT,DOC,WF}
PINS_FILE='docs/r4/R4_P14_P03_SOURCE_PINS.json'
PATHS.add(PINS_FILE)
TEST_CASES=('activeUpdateCancelBlocksLateProgressAndCompletion',
 'verifyStageCancellationCannotBecomeInstallerHandoff',
 'failedUpdateRetryGetsFreshAttemptAndDropsOldWorker',
 'newerUpdateVersionRejectsOldCancellationAndInstallerResult',
 'installerUserDeclineWithCachedApkRemainsPendingNotInstalled',
 'installerUserDeclineWithoutCachedApkFailsThenAllowsRetry',
 'interruptedInstallRecoveryWithCachedApkRestoresPendingState',
 'missingSessionAndApkCannotRemainInstallingForever')
class Refused(ValueError):pass
def need(ok,code):
 if not ok:raise Refused('P14P03_SOURCE_REFUSED_'+code)
def git(root,*args):
 p=subprocess.run(['git',*args],cwd=root,capture_output=True,text=True)
 need(p.returncode==0,'GIT_'+args[0]+'_'+p.stderr[-250:])
 return p.stdout.strip()
def check_test(s):
 need(s.count('    @Test\n')==8,'EIGHT_REAL_ANDROID_TESTS')
 for marker in (*TEST_CASES,'@RunWith(AndroidJUnit4::class)',
    'Room.inMemoryDatabaseBuilder','AuroraDatabase::class.java',
    'InstallResultPolicy.next(', 'InstallRecoveryPolicy.resolve(',
    'dao.cancelActiveDownload(', 'dao.retryWithNewAttempt(',
    'dao.transitionInstallAttempt(', 'dao.reconcileInstallStatus(',
    'DownloadUiPolicy.canRetry(', 'DownloadStatus.AWAITING_INSTALL',
    'DownloadStatus.CANCELLED', 'DownloadStatus.FAILED',
    'hasCachedApks = true', 'hasCachedApks = false',
    'assertThat(declined).isNull()','assertThat(dao.getDownload(PACKAGE).status)'):
  need(marker in s,'TEST_MARKER_'+marker)
 for denied in ('PackageInstaller(', 'installPackage(', 'createSession(',
                'HttpURLConnection(', 'OkHttpClient(', 'Runtime.getRuntime(',
                'su -c','http://','https://'):
  need(denied not in s,'TEST_FORBIDDEN_'+denied)
 return True
def check_ui_test(s):
 need(s.count('    @Test\n')==8,'EIGHT_REAL_COMPOSE_TESTS')
 for marker in ('class R4P14P03DownloadUiDeviceTest : IsolatedTest()',
  'automation.takeScreenshot()', 'DownloadListItem(', 'DownloadActionsSheet(',
  'queuedStatusHasNoInventedProgressOrSpeed',
  'activeTransferDisplaysActualProgressWithoutFakeSpeed',
  'failedTransferDisplaysCorrectFailureStatus',
  'failedTransferRetryActionInvokesProductionCallback',
  'r4_p14p03_queued.png','r4_p14p03_downloading.png','r4_p14p03_failed.png',
  'r1g_awaiting_retry.png','r1g_cancelled.png',
  'verifyingDownloadStillAllowsCancellation',
  'missingCachedApkShowsRetryWithoutInstallation',
  'installingDoesNotExposeCancelOrRetry',
  'cancelledShowsAccurateStatusWithoutFakeTransferStats'):

  need(marker in s,'UI_TEST_MARKER_'+marker)
 for marker in ('contentSamples >= 12', 'delta >= 52',
  'frame.width >= 320 && frame.height >= 480',
  'for (attempt in 1..10)', 'SystemClock.sleep(300)',
  'P14P03_REFUSED_BLANK_WIDGET_SCREENSHOT',
  'Bitmap.CompressFormat.PNG', 'file.length() > 2048L',
  'frame.recycle()', 'image.recycle()'):
  need(marker in s,'WIDGET_SCREENSHOT_GUARD_'+marker)
 need('R4ScreenshotEvidence.capture(' not in s,'WHOLE_SCREEN_HEURISTIC_ON_ISOLATED_WIDGET')
 need('captureToImage(' not in s,'FLAKY_OLD_SCREENSHOT_CAPTURE')
 need('contentSamples >= 0' not in s,'BLANK_SCREEN_ACCEPTED')
 return True

def check_run(s):
 for marker in ('set -euo pipefail',
  'for profile in full compact;do','for mode in light dark;do',
  'size=1080x2400;density=420','size=720x1600;density=320',
  'trap restore_display EXIT', 'timeout 840 adb shell am instrument',
  "run_class \"$profile\" \"$mode\" lifecycle \"$LIFECYCLE\" 8",
  'run_class "$profile" "$mode" download-ui "$DOWNLOAD_UI" 8',
  'run_class "$profile" "$mode" baseline-dao "$DAO" 9',
  'truncatedResponseRetriesThenResumesSameAttemptExactly',
  'shaMismatchRejectsPayloadWithoutInstallHandoff',
  'cancelledAttemptIsNotResurrectedOrDownloaded',
  'collect_failed "$profile" "$mode"',
  'adb logcat -d -t 1500',
  'r4_p14_p03_evidence_audit.py',
  'P14P03_HOSTED_76_TESTS_20_PNGS_PASS'):
  need(marker in s,'RUN_MARKER_'+marker)
 # AndroidJUnitRunner emits "OK (1 test)" for one method, "OK (N tests)" otherwise.
 # Fail closed on missing instrumentation exit, not on grammatical plurality.
 for marker in ('local expected="OK ($count tests)"',
                "if (( count == 1 )); then expected='OK (1 test)'; fi",
                '! grep -Fxq "$expected" "$log"',
                "! grep -Fxq 'INSTRUMENTATION_CODE: -1' \"$log\""):
  need(marker in s,'RUN_RESULT_CONTRACT_'+marker)
 need('! grep -Fxq "OK ($count tests)" "$log"' not in s,
      'RUN_OLD_PLURAL_ONLY_GUARD')
 need('run_class "$profile" "$mode" final-ui' not in s and
      "FINAL_UI='com.aurora.store.compose.ui.downloads.DownloadFinalUiDeviceTest'" not in s,
      'LEGACY_BLANK_SCREENSHOT_PRODUCER')
 need(s.count('timeout 840 adb shell am instrument')==1,'RUNNER_UNBOUNDED')
 need('adb -s localhost:5555' not in s,'PHYSICAL_ADB')
 return True
def check_audit(s):
 for marker in ('total==76','len(images)==20',"'release_qualified':False",
  "'real_installer_qualified':False", "'physical_arm64_qualified':False",
  "'installed_apk_prompt_decline_qualified':False",
  "'production_downloads_external_network_qualified':False",
  'P14P03_HOSTED_76_TESTS_20_PNGS_PASS','png.load_pixels(path)', 'COMPOSITOR_DIMENSIONS_',
  'r4_p14p03_queued.png','r4_p14p03_downloading.png','r4_p14p03_failed.png',
  'widget_sample_policy(', 'load_widget_png(path)',
  '12 <= changed < 42 and colors >= 8',
  'R4_P06_REFUSED_BLANK_SCREENSHOT_',
  'SPARSE_WIDGET_CONTENT_',
  "'visual_gate':'isolated_widget_nonblank'",
  'r1g_awaiting_retry.png','r1g_cancelled.png'):
  need(marker in s,'AUDIT_MARKER_'+marker)
 return True
def check_workflow(s):
 for marker in (BRANCH,'permissions:\n  contents: read',
  'persist-credentials: false', 'api-level: 36',
  ':app:assembleVanillaDebugAndroidTest',
  'r4_p14_p03_emulator_acceptance.sh',
  'r4_p14_p03_source_contract.py',
  'test_r4_p14_p03_source_contract.py',
  'if: always()', 'actions/upload-artifact@',
  'P14P03_AGP_RESOLUTION_RETRY',
  'P14P03_NON_TRANSIENT_GRADLE_FAILURE',
  'P14P03_AGP_UNAVAILABLE_AFTER_BOUNDED_RETRIES',
  'if ! grep -Fq "Plugin [id:',
  '[[ "$build_ok" == true ]] || exit 1'):
  need(marker in s,'WORKFLOW_MARKER_'+marker)
 need(not re.search(r'^\s*(?:contents|actions|pull-requests): write\b',s,re.M),
      'WORKFLOW_WRITE_ACCESS')
 return True
def source_only(root):
 for p in PATHS:need((root/p).is_file(),'FILE_MISSING_'+p)
 check_test((root/TEST).read_text())
 check_ui_test((root/UI_TEST).read_text())
 check_run((root/RUN).read_text())
 check_audit((root/AUDIT).read_text())
 check_workflow((root/WF).read_text())
 pins=json.loads((root/PINS_FILE).read_text())
 need(pins.get('schema')==1 and pins.get('base_sha')==BASE,'PINS_SOURCE')
 need(len(pins.get('blobs',{}))>=14,'INSUFFICIENT_PROTECTED_PINS')
 need(all(re.fullmatch('[a-f0-9]{40}',v) for v in pins['blobs'].values()),'BAD_PROTECTED_PINS')
 doc=(root/DOC).read_text()
 for marker in ('P14-P03','hosted-only','P15','not tested','installer decline','76','20'):
  need(marker in doc,'DOCUMENT_SCOPE_'+marker)
 return True
def verify(root):
 source_only(root)
 need(git(root,'merge-base',BASE,'HEAD')==BASE,'BASE_NOT_ANCESTOR')
 need(git(root,'status','--porcelain')=='','DIRTY_WORKTREE')
 changed=set(git(root,'diff','--name-only',BASE,'HEAD').splitlines())
 need(changed==PATHS,'ADDITIVE_SCOPE_'+repr(sorted(changed^PATHS)))
 pins=json.loads((root/PINS_FILE).read_text())['blobs']
 for path,blob in pins.items():
  need(git(root,'rev-parse',BASE+':'+path)==blob,'BASE_PIN_DRIFT_'+path)
  need(git(root,'rev-parse','HEAD:'+path)==blob,'IMMUTABLE_P14_DRIFT_'+path)
 return git(root,'rev-parse','HEAD')
if __name__=='__main__':
 try:
  p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'))
  p.add_argument('--source-only',action='store_true');args=p.parse_args()
  result=source_only(args.root.resolve()) if args.source_only else verify(args.root.resolve())
  print('P14P03_SOURCE_PASS',result)
 except (Refused,OSError,ValueError,KeyError,TypeError) as e:
  print(str(e),file=sys.stderr);raise SystemExit(2)
