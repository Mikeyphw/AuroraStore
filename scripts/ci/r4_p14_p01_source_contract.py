#!/usr/bin/env python3
"""P14-P01/P02 consolidated, fail-closed source/receipt/CI contract."""
from __future__ import annotations
import argparse,hashlib,json,re,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import r4_p13b_visual_signoff as p13
P13='47c360e9cb553f73fb6858cd364ea19835bada6e'
P12='3ea10b6f4b0fed5a8913e4edef3536cfc93fc52f'
BRANCH='feature/aurora-r4-p14-p01-offline-nav3-journeys-20261114'
TEST='app/src/androidTest/java/com/aurora/store/compose/ui/r4/R4P14OfflineNav3JourneyDeviceTest.kt'
RUN='scripts/ci/r4_p14_p01_emulator_acceptance.sh'
AUDIT='scripts/ci/r4_p14_p01_screenshot_audit.py'
GATE='scripts/ci/r4_p14_p01_source_contract.py'
UNIT='scripts/ci/test_r4_p14_p01_source_contract.py'
GATEWAY='app/src/main/java/com/aurora/store/data/catalog/CatalogJourneyGateway.kt'
HILT='app/src/androidTest/java/com/aurora/store/compose/ui/r4/P14HermeticCatalogModule.kt'
PATCHES='docs/r4/R4_P14_P02_PRODUCTION_PATCHES.json'
WF='.github/workflows/aurora-r4-p14-p01-journeys.yml'
DOC='docs/r4/R4_P14_P01_OFFLINE_NAV3_JOURNEYS.md'
RECEIPT='docs/r4/evidence/P13B02_HOSTED_RECEIPT_43650748680.json'
REVIEW='docs/r4/evidence/P13B02_MANUAL_REVIEW_43650748680.json'
SIGNOFF='docs/r4/evidence/P13B02_LIMITED_SIGNOFF_43650748680.json'
PRODUCTION_PATHS=(
 'app/src/main/java/com/aurora/store/viewmodel/search/SearchViewModel.kt',
 'app/src/main/java/com/aurora/store/viewmodel/details/AppDetailsViewModel.kt',
 'app/src/main/java/com/aurora/store/compose/ui/details/AppDetailsScreen.kt',
)
FILES={TEST,RUN,AUDIT,GATE,UNIT,WF,DOC,RECEIPT,REVIEW,SIGNOFF,GATEWAY,HILT,PATCHES} | set(PRODUCTION_PATHS)
SHOTS=('r4_p14_search_route.png','r4_p14_downloads_route.png',
       'r4_p14_settings_route.png','r4_p14_preferences_route.png',
       'r4_p14_games_tab.png','r4_p14_updates_tab.png',
       'r4_p14_populated_search.png','r4_p14_details_identity.png',
       'r4_p14_details_carousel.png','r4_p14_details_reviews.png')
class Refused(Exception):pass
def need(x,s):
 if not x:raise Refused('P14_P01_REFUSED_'+s)
def git(root,*args):
 p=subprocess.run(['git',*args],cwd=root,capture_output=True,text=True)
 need(p.returncode==0,'GIT_'+args[0]+'_'+p.stderr[-180:])
 return p.stdout.strip()
def check_test(s):
 need(s.count('    @Test\n')==4,'FOUR_REAL_TESTS')
 for marker in ('@HiltAndroidTest','HiltAndroidRule(this)','createEmptyComposeRule()',
  'ComposeActivity::class.java','Screen.Main(initialTab = 0)',
  'fun realMainSearchBackThenDownloadsBack()',
  'fun realMainSettingsPreferencesAndReverseBackstack()',
  'fun realMainGamesUpdatesAppsRoundTripNoInstaller()',
  'fun realSearchToFullDetailsHeaderArtworkAndReviews()',
  'P14HermeticCatalogGateway.searchCount',
  'P14HermeticCatalogGateway.detailsCount',
  'P14HermeticCatalogGateway.reviewCount',
  'aurora-details-screenshots','aurora-details-reviews',
  'onNodeWithContentDescription(context.getString(R.string.title_download_manager))',
  'onNodeWithContentDescription(context.getString(R.string.action_back))',
  '"Import and verify APKs"','SemanticsProperties.Selected',
  'hasClickAction()', 'R4ScreenshotEvidence.capture(',
  'P14_REFUSED_STALE_BODY_FRAME', 'primeVisualBaseline()',
  'previousBodySignature = sample',
  'val rows = 160', 'val columns = 160',
  '6 * rows + 88 * row', '5 * columns + 90 * column',
  'if (observed >= 12)', 'for (attempt in 1..12)',
  'P14_FRAME_READBACK', *SHOTS):
  need(marker in s,'TEST_MARKER_'+marker)
 for forbidden in ('HttpURLConnection(', 'OkHttpClient(', 'PackageInstaller(',
                   'su -c', 'Runtime.getRuntime()', 'https://', 'http://',
                   'import androidx.compose.ui.test.assertExists\n'):
  need(forbidden not in s,'TEST_UNSAFE_'+forbidden)
 need('it.config.getOrElse(SemanticsProperties.Selected) { false }' in s,
      'COMPOSE_SELECTED_MEMBER_ACCESS')
 need('it.config.getOrNull(SemanticsProperties.Selected)' not in s,
      'COMPOSE_SELECTED_EXTENSION_NOT_IMPORTED')
 need('IntArray(14 * 27)' not in s and '13 + 5 * row' not in s,
      'SPARSE_SIGNATURE_REINTRODUCED')
 # Reject screenshot acceptance without an observable UI pixel difference.
 need('if (observed >= 12)' in s and 'for (attempt in 1..12)' in s,
      'UNBOUNDED_OR_BYPASSED_FRESHNESS')
 return True
def check_run(s):
 for marker in ('set -euo pipefail','for profile in full compact;do',
  'for mode in light dark;do','size=1080x2400;density=420',
  'size=720x1600;density=320','trap restore_display EXIT',
  'grep -Fxq \'OK (4 tests)\'',
  'R4P14OfflineNav3JourneyDeviceTest',
  'timeout 840 adb shell am instrument','adb exec-out run-as "$TARGET"',
  'r4_p14_p01_screenshot_audit.py',
  'adb logcat -d -v time -t 2500', 'P14_FAILURE_EVIDENCE_DIR',
  'debug="$OUT/debug/$profile/$mode"', *SHOTS):
  need(marker in s,'RUNNER_MARKER_'+marker)
 need(s.count('timeout 840 adb shell am instrument')==1,'UNBOUNDED_TEST')
 return True
def check_audit(s):
 for marker in ("'tests_executed':16","'screenshots_count':40",'p12.load_pixels(',
  "'full_upstream_visual_signoff':False", "'release_qualified':False",
  "'real_account_qualified':False", "'real_installer_qualified':False",*SHOTS):
  need(marker in s,'AUDIT_MARKER_'+marker)
 return True
def check_workflow(s):
 for marker in (BRANCH,'permissions:\n  contents: read',
  'persist-credentials: false','api-level: 36',
  'app:assembleVanillaDebugAndroidTest','r4_p14_p01_emulator_acceptance.sh',
  'r4_p14_p01_source_contract.py','test_r4_p14_p01_source_contract.py',
  'if: always()','actions/upload-artifact@'):
  need(marker in s,'WORKFLOW_MARKER_'+marker)
 need(not re.search(r'^\s*(?:actions|contents|pull-requests): write\b',s,re.M),
  'WRITE_WORKFLOW_PERMISSION')
 return True

def check_gateway(text):
 for marker in ('interface CatalogJourneyGateway',
  'class LiveCatalogJourneyGateway @Inject constructor()',
  '@InstallIn(SingletonComponent::class)',
  'fun searchResults(query: String): List<App>? = null',
  'fun appDetails(packageName: String): App? = null',
  'val isHermetic: Boolean get() = false'):
  need(marker in text,'GATEWAY_'+marker)
 need('HttpURLConnection(' not in text and 'OkHttpClient(' not in text,'GATEWAY_REMOTE_CALL')
 return True

def check_hilt(text):
 for marker in ('@TestInstallIn(', 'replaces = [CatalogJourneyGatewayModule::class]',
   'class P14HermeticCatalogGateway @Inject constructor(',
   'invalid.aurora.p14.fixture','AppPreviewProvider().values.first()',
   'fun searchResults(query: String)', 'fun appDetails(packageName: String)',
   'fun featuredReviews(packageName: String)', 'AtomicInteger()',
   'File(context.filesDir', 'Bitmap.createBitmap', 'class P14HermeticCatalogModule',
   'override val isHermetic: Boolean = true'):
  need(marker in text,'HILT_'+marker)
 for forbidden in ('HttpURLConnection(', 'OkHttpClient(', 'PackageInstaller(', 'Runtime.getRuntime(', 'su -c'):
  need(forbidden not in text,'HILT_FORBIDDEN_'+forbidden)
 return True

def check_patches(document):
 need(set(document)==set(PRODUCTION_PATHS),'PATCH_INVENTORY')
 for path in PRODUCTION_PATHS:
  entry=document[path]
  need(re.fullmatch(r'[0-9a-f]{40}',entry['sha']) is not None,'PATCH_BASE_SHA_'+path)
  repl=entry['replacements']
  need(len(repl)>=3 and all(len(x)==2 and x[0] and x[1] and x[0]!=x[1] for x in repl),
       'PATCH_INVALID_'+path)
  need(len({a for a,b in repl})==len(repl),'PATCH_DUPLICATE_ANCHOR_'+path)
 combined='\n'.join(new for entry in document.values() for old,new in entry['replacements'])
 for needle in ('CatalogJourneyGateway', '_apps.value = PagingData.from(offline)',
    'catalogJourneyGateway.appDetails(packageName)',
    'catalogJourneyGateway.featuredReviews(packageName)',
    'aurora-details-main-list', 'aurora-details-screenshots',
    'aurora-details-reviews'):
  need(needle in combined,'PATCH_REQUIRED_'+needle)
 return True

def exact_patch(before, replacements):
 result=before
 for old,new in replacements:
  need(result.count(old)==1,'PATCH_ANCHOR_NOT_EXACTLY_ONCE')
  result=result.replace(old,new,1)
 return result

def check_production_postimage(root, document):
 for path in PRODUCTION_PATHS:
  entry=document[path]
  need(git(root,'rev-parse',P13+':'+path)==entry['sha'],'PATCH_BASE_DRIFT_'+path)
  raw=subprocess.run(['git','show',P13+':'+path],cwd=root,capture_output=True)
  need(raw.returncode==0,'PATCH_SHOW_FAILED_'+path)
  original=raw.stdout.decode('utf-8')
  expected=exact_patch(original,entry['replacements'])
  need((root/path).read_text()==expected,'PRODUCTION_POSTIMAGE_'+path)
 return True

def check_human(root):
 receipt=json.loads((root/RECEIPT).read_text())
 review=json.loads((root/REVIEW).read_text())
 limited=json.loads((root/SIGNOFF).read_text())
 refs=json.loads((root/'docs/r4/R4_P13B_UPSTREAM_PR113_REFERENCES.json').read_text())
 need(receipt.get('source_sha')==P13 and str(receipt.get('run_id'))=='43650748680',
      'REVIEW_WRONG_HOSTED_SOURCE')
 expected=p13.validate(receipt,refs,review)
 need(expected==limited,'REVIEW_NOT_VALIDATED')
 need(limited['limited_p13b_visual_review_approved'] is True and
      limited['full_upstream_visual_signoff'] is False and
      limited['release_qualified'] is False,'SIGNOFF_ESCALATED')
 return True
def source_checks(root):
 check_test((root/TEST).read_text())
 check_run((root/RUN).read_text())
 check_audit((root/AUDIT).read_text())
 check_workflow((root/WF).read_text())
 check_gateway((root/GATEWAY).read_text())
 check_hilt((root/HILT).read_text())
 document=json.loads((root/PATCHES).read_text())
 check_patches(document)
 if all((root/x).exists() for x in PRODUCTION_PATHS):
  for path in PRODUCTION_PATHS:
   code=(root/path).read_text()
   need(all(new in code for old,new in document[path]['replacements']),
        'PRODUCTION_PATCH_MARKER_'+path)
 need('details_top' in (root/DOC).read_text(),'DETAILS_GAP_ERASED')
 check_human(root)
 return True
def verify(root):
 root=root.resolve(strict=True)
 head=git(root,'rev-parse','HEAD')
 need(re.fullmatch(r'[0-9a-f]{40}',head) is not None,'BAD_HEAD')
 need(git(root,'merge-base',P13,'HEAD')==P13,'P13_NOT_ANCESTOR')
 need(not git(root,'status','--porcelain'),'DIRTY')
 changed=set(git(root,'diff','--name-only',P13,'HEAD').splitlines())
 need(changed==FILES,'UNEXPECTED_PATHS_'+repr(sorted(changed^FILES)))
 for file in ('app/src/androidTest/java/com/aurora/store/compose/ui/r4/R4P13BIntegratedVisualDeviceTest.kt',
              'scripts/ci/r4_p13b_emulator_acceptance.sh',
              'scripts/ci/r4_p13b_screenshot_audit.py',
              'scripts/ci/r4_p13b_visual_signoff.py',
              'app/src/androidTest/java/com/aurora/store/compose/ui/r4/R4PopulatedCatalogDeviceTest.kt'):
  need(git(root,'rev-parse',f'{P13}:{file}')==git(root,'rev-parse',f'HEAD:{file}'),
       'QUALIFIED_SOURCE_DRIFT_'+file)
 source_checks(root)
 check_production_postimage(root,json.loads((root/PATCHES).read_text()))
 return head
if __name__=='__main__':
 try:
  p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'))
  p.add_argument('--source-only',action='store_true');p.add_argument('--integration',action='store_true');a=p.parse_args()
  if a.integration:
   from check_aur_int01 import verify as integration_verify
   integration_verify(a.root,'p14');raise SystemExit(0)
  root=a.root.resolve()
  print('P14_P01_SOURCE_PASS', 'SOURCE_ONLY' if a.source_only else verify(root)) if not a.source_only else print('P14_P01_SOURCE_PASS_SOURCE_ONLY',source_checks(root))
 except (Refused,OSError,ValueError,KeyError,TypeError) as e:
  print(str(e),file=sys.stderr);raise SystemExit(2)
