#!/usr/bin/env python3
"""R4 P13-B source-only stacked scope: production Nav3 + multiview + signoff.

Base P12 64/37 remains preserved. This does not certify a hosted build or release.
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
from pathlib import Path

BASE='3ea10b6f4b0fed5a8913e4edef3536cfc93fc52f'
BRANCH='feature/aurora-r4-p13b-nav3-multisize-20261114'
TEST='app/src/androidTest/java/com/aurora/store/compose/ui/r4/R4P13BIntegratedVisualDeviceTest.kt'
NAV_TEST='app/src/androidTest/java/com/aurora/store/compose/ui/r4/R4P13BProductionNav3DeviceTest.kt'
RUNNER='scripts/ci/r4_p13b_emulator_acceptance.sh'
AUDIT='scripts/ci/r4_p13b_screenshot_audit.py'
GATE='scripts/ci/r4_p13b_source_contract.py'
UNIT='scripts/ci/test_r4_p13b_source_contract.py'
SIGNOFF='scripts/ci/r4_p13b_visual_signoff.py'
SIGNOFF_UNIT='scripts/ci/test_r4_p13b_visual_signoff.py'
WORKFLOW='.github/workflows/aurora-r4-p13b-integrated.yml'
DOC='docs/r4/R4_P13B_HERMETIC_JOURNEYS.md'
REFERENCES='docs/r4/R4_P13B_UPSTREAM_PR113_REFERENCES.json'
FILES={TEST,NAV_TEST,RUNNER,AUDIT,GATE,UNIT,SIGNOFF,SIGNOFF_UNIT,WORKFLOW,DOC,REFERENCES}
P12_PINS={
  'app/src/androidTest/java/com/aurora/store/compose/ui/r4/R4PopulatedCatalogDeviceTest.kt':'397a4c7343121b0fff99837610dec92645c5cfdb',
  'scripts/ci/r4_p05_screenshot_audit.py':'07dd764b05d1105bdd744e87e959f4427f84824d',
  'scripts/ci/r4_p05_emulator_acceptance.sh':'df6002e01eb57afa1923ea880827b5605bfcb584',
}
IMAGES=(
 'r4_p13b_home.png','r4_p13b_charts.png','r4_p13b_categories.png',
 'r4_p13b_search.png','r4_p13b_details_top.png','r4_p13b_details_reviews.png',
 'r4_p13b_category_selection.png','r4_p13b_category_collection.png',
 'r4_p13b_nav_search.png','r4_p13b_nav_return.png',
 'r4_p13b_nav_settings.png','r4_p13b_nav_preferences.png',
)
REF_BLOBS={
 'for_you':'51b4fc2f4ef02ca59f1251bdace98c7b96c2c902',
 'home_actions':'df19e579a302e381088fab1d826387e14a9d1b5d',
 'top_charts':'ecd6928e469495ba680d0356505bce79e4d03852',
 'categories':'61c54268a50a2b04bbae285dd6b132e9358afab1',
 'details':'197cc27b07552b47c1fefa49486d64f83923ad95',
 'search':'c2d0c0f66bc60c819382557b8123926b5b1bf3e5',
 'settings':'9adb0938e893dd494f7cbb205c4a22d55e8620ec',
 'customization':'5093b1f6866e106c9762b9be6ddbad6d2609160e',
}
class Refused(Exception):pass
def need(ok,code):
 if not ok:raise Refused('P13B_SOURCE_REFUSED_'+code)
def git(root,*args):
 p=subprocess.run(['git',*args],cwd=root,capture_output=True,text=True)
 need(p.returncode==0,'GIT_'+args[0]+'_'+p.stderr[-200:])
 return p.stdout.strip()

def check_test(s):
 need(s.count('    @Test\n')==3,'INTEGRATED_THREE_TESTS')
 for marker in ('class R4P13BIntegratedVisualDeviceTest : IsolatedTest()',
   'fun integratedHomeChartsCategoriesHaveSharedTabState()',
   'fun typedOfflineSearchOpensDetailsArtworkAndReview()',
   'fun selectedCategoryShowsLocalAppsWithoutPlayCall()',
   'StreamCarousel(', 'TopChartsBody(', 'CategoriesBody(',
   'SearchResultListItem(', 'Details(app = app)', 'Screenshots(screenshots = inputArt)',
   'RatingAndReviews(', 'onNodeWithTag("p13-query").performTextInput("Atlas")',
   'performScrollToIndex(3)', 'invalid.aurora.p13b.fixture', 'R4ScreenshotEvidence.capture(',
   *IMAGES[:8]):
  need(marker in s,'INTEGRATED_MARKER_'+marker)
 for forbidden in ('HttpURLConnection(', 'OkHttpClient(', 'PackageInstaller(', 'adb install',
                   'Runtime.getRuntime()', 'su -c', 'https://', 'http://'):
  need(forbidden not in s,'INTEGRATED_UNSAFE_'+forbidden)
 # SemanticsNodeInteraction owns assertExists/assertDoesNotExist as members in
 # this Compose test artifact. Importing them as top-level functions fails K2.
 for forbidden_import in ('import androidx.compose.ui.test.assertExists\n',
                          'import androidx.compose.ui.test.assertDoesNotExist\n'):
  need(forbidden_import not in s, 'INVALID_COMPOSE_TEST_IMPORT')
 # DetailsPortalCard requires the onClick lambda: no default exists.
 need(s.count('icon = painterResource(R.drawable.ic_apps),\n'
              '                                    onClick = {})')==1,
      'DETAILS_PORTAL_REQUIRED_ONCLICK')
 need(s.count('onPrimaryAction = { actions++ }')==1,'CALLBACK_ISOLATION')
 return True

def check_nav(s):
 need(s.count('    @Test\n')==2,'NAV3_TWO_TESTS')
 for marker in ('@HiltAndroidTest','ActivityScenario.launch(',
  'Screen.Main(initialTab = 0)', 'ComposeActivity::class.java',
  'HiltAndroidRule(this)', 'createEmptyComposeRule()',
  'onNodeWithContentDescription(context.getString(R.string.action_search))',
  'onNodeWithContentDescription(context.getString(R.string.action_back))',
  'onNodeWithContentDescription(context.getString(R.string.title_more))',
  'fun actualMainSearchButtonNavigatesToSearchAndReturns()',
  'fun actualMainMoreSettingsAndCustomizationRoute()',
  'R4ScreenshotEvidence.capture(',*IMAGES[8:]):
  need(marker in s,'NAV3_MARKER_'+marker)
 need('import androidx.compose.ui.test.assertExists\n' not in s,
      'INVALID_COMPOSE_TEST_IMPORT')
 for forbidden in ('MockNavHost', 'FakeNavigator', 'HttpURLConnection(',
                  'OkHttpClient(', 'PackageInstaller(', 'su -c'):
  need(forbidden not in s,'NAV3_UNSAFE_'+forbidden)
 return True

def check_runner(s):
 need(s.startswith('#!/usr/bin/env bash\n') and 'set -euo pipefail' in s,'SHELL_SETUP')
 for marker in ('for profile in full compact; do','for mode in light dark; do',
   'width=1080; height=2400; density=420',
   'width=720; height=1600; density=320',
   'adb shell wm size','adb shell wm density',
   'trap restore_display EXIT','R4P13BProductionNav3DeviceTest',
   'timeout 840 adb shell am instrument',
   'run_class "$profile" "$mode" p13b-integrated "$INTEGRATED" 3',
   'run_class "$profile" "$mode" p13b-nav3 "$NAVIGATION" 2',
   'adb exec-out run-as "$TARGET"',
   'python3 -B scripts/ci/r4_p13b_screenshot_audit.py',*IMAGES):
  need(marker in s,'RUNNER_MARKER_'+marker)
 need(s.count('timeout 840 adb shell am instrument')==1,'RUNNER_INSTRUMENTATION_BOUND')
 return True

def check_audit(s):
 for marker in ('import r4_p05_screenshot_audit as p12',
  "'full': (1080, 2400, 420)","'compact': (720, 1600, 320)",
  "'tests_executed':20", "'screenshots_count':48",
  "'manual_visual_approved':False",
  "'full_upstream_visual_signoff':False",
  "'release_qualified':False", 'p12.load_pixels(path)',
  'UNDIFFERENTIATED_THEME_', 'PNG_DIMENSIONS_',*IMAGES):
  need(marker in s,'AUDIT_MARKER_'+marker)
 return True

def check_workflow(s):
 for marker in ('feature/aurora-r4-p13b-nav3-multisize-20261114',
  'permissions:\n  contents: read',
  'python3 -B scripts/ci/test_r4_p13b_source_contract.py',
  'python3 -B scripts/ci/test_r4_p13b_visual_signoff.py',
  'python3 -B scripts/ci/r4_p13b_source_contract.py --root .',
  'scripts/ci/r4_p13b_emulator_acceptance.sh',
  'api-level: 36', 'if: always()', 'app:assembleVanillaDebugAndroidTest',
  'actions/upload-artifact@', 'persist-credentials: false'):
  need(marker in s,'WORKFLOW_MARKER_'+marker)
 need(not re.search(r'^\s*(?:contents|actions|pull-requests): write\b',s,re.M),
      'WORKFLOW_WRITE_PERMISSION')
 return True

def check_references(doc):
 need(doc.get('schema')==1 and doc.get('upstream_pull_request')==
  'https://github.com/whyorean/AuroraStore/pull/113','REFERENCE_SOURCE')
 need(list(doc.get('comparisons',{}))==list(REF_BLOBS),'REFERENCE_COUNT_OR_ORDER')
 for name,blob in REF_BLOBS.items():
  need(doc['comparisons'][name].get('git_blob_sha1')==blob,'REFERENCE_BLOB_'+name)
  need(doc['comparisons'][name].get('actual') in IMAGES,'REFERENCE_SCREENSHOT_'+name)
 return True

def check_signoff(s):
 for marker in ('I_REVIEWED_P13B_PNGS_AGAINST_AUTHOR_PR113',
  'FULL_UPSTREAM_PARITY_UNSUPPORTED_BY_P13B_FIXTURES',
  "'full_upstream_visual_signoff':False", "'release_qualified':False",
  'request_final_upstream_signoff', 'P13B_VISUAL_SIGNOFF_REFUSED_'):
  need(marker in s,'SIGNOFF_MARKER_'+marker)
 return True

def verify(root):
 root=root.resolve(strict=True)
 head=git(root,'rev-parse','HEAD')
 need(bool(re.fullmatch('[0-9a-f]{40}',head)),'BAD_HEAD')
 need(git(root,'merge-base',BASE,'HEAD')==BASE,'WRONG_BASE')
 need(not git(root,'status','--porcelain'),'DIRTY_TREE')
 changed=set(git(root,'diff','--name-only',BASE,'HEAD').splitlines())
 need(changed==FILES,'ADD_ONLY_INVENTORY_'+repr(sorted(changed^FILES)))
 for path,pin in P12_PINS.items():
  need(git(root,'rev-parse',f'{BASE}:{path}')==pin,'P12_BASE_'+path)
  need(git(root,'rev-parse',f'HEAD:{path}')==pin,'P12_CHANGED_'+path)
 check_test((root/TEST).read_text())
 check_nav((root/NAV_TEST).read_text())
 check_runner((root/RUNNER).read_text())
 check_audit((root/AUDIT).read_text())
 check_signoff((root/SIGNOFF).read_text())
 check_references(json.loads((root/REFERENCES).read_text()))
 check_workflow((root/WORKFLOW).read_text())
 need('P13B_HOSTED_PENDING' in (root/DOC).read_text(),'MISLEADING_APPROVAL')
 return head

if __name__=='__main__':
 try:
  p=argparse.ArgumentParser();p.add_argument('--root',default=Path('.'),type=Path)
  args=p.parse_args()
  print('P13B_CONSOLIDATED_NAV3_MULTISIZE_SIGNOFF_SOURCE_PASS',verify(args.root))
 except (Refused,OSError,ValueError,KeyError) as e:
  print(str(e))
  raise SystemExit(2)
