#!/usr/bin/env python3
"""P13-B consolidated local source and adversarial CI mutation selftests."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import r4_p13b_source_contract as g

ROOT=Path(__file__).resolve().parents[2]
def refuses(fn,code):
 try:fn()
 except g.Refused as e:assert code in str(e),(code,str(e))
 else:raise AssertionError('P13B_MUTATION_NOT_REFUSED_'+code)

def main():
 test=(ROOT/g.TEST).read_text()
 nav=(ROOT/g.NAV_TEST).read_text()
 run=(ROOT/g.RUNNER).read_text()
 audit=(ROOT/g.AUDIT).read_text()
 wf=(ROOT/g.WORKFLOW).read_text()
 sign=(ROOT/g.SIGNOFF).read_text()
 ref=__import__('json').loads((ROOT/g.REFERENCES).read_text())
 for call,args in ((g.check_test,(test,)),(g.check_nav,(nav,)),
                   (g.check_runner,(run,)),(g.check_audit,(audit,)),
                   (g.check_signoff,(sign,)),(g.check_workflow,(wf,)),
                   (g.check_references,(ref,))): assert call(*args)
 negatives=[
  (lambda:g.check_test(test.replace('    @Test\n','',1)),'INTEGRATED_THREE_TESTS'),
  # HF03 emulator regression: one-cluster carousel has no header;
  # synthetic category state must be checked via the back control + cards.
  (lambda:g.check_test(test.replace(
   'composeTestRule.onNodeWithText("P13 Back to categories").assertExists()',
   'composeTestRule.onNodeWithText("P13 Selected Art").assertExists()',1)),
   'CATEGORY_SINGLE_CLUSTER_FALSE_HEADER'),
  (lambda:g.check_test(test.replace(
   'composeTestRule.onNodeWithText("P13 Back to categories").performClick()',
   'composeTestRule.onNodeWithText("P13 Back to categories").assertExists()',1)),
   'CATEGORY_BACK_ROUTE_'),
  (lambda:g.check_test(test.replace(
   'composeTestRule.onNodeWithText("P13 Back to categories").assertDoesNotExist()',
   'composeTestRule.onNodeWithText("P13 Back to categories").assertExists()',1)),
   'CATEGORY_BACK_ROUTE_'),
  (lambda:g.check_test(test.replace(
   'composeTestRule.onNodeWithText("P13 Back to categories").performClick()\n        composeTestRule.onNodeWithText("P13 Art").assertExists()',
   'composeTestRule.onNodeWithText("P13 Back to categories").performClick()\n        composeTestRule.onNodeWithText("P13 Business").assertExists()',1)),
   'CATEGORY_RETURN_TO_BROWSER'),
  (lambda:g.check_test(test.replace('Screenshots(screenshots = inputArt)','Screenshots(screenshots = emptyList())')),'INTEGRATED_MARKER_'),
  (lambda:g.check_test(test+'\n// PackageInstaller('),'INTEGRATED_UNSAFE_'),
  (lambda:g.check_test('import androidx.compose.ui.test.assertExists\n'+test),
   'INVALID_COMPOSE_TEST_IMPORT'),
  (lambda:g.check_test('import androidx.compose.ui.test.assertDoesNotExist\n'+test),
   'INVALID_COMPOSE_TEST_IMPORT'),
  (lambda:g.check_test(test.replace('                                    onClick = {})',
                                    '                                    onClick = {})'.replace('onClick = {}',''),1)),
   'DETAILS_PORTAL_REQUIRED_ONCLICK'),
  (lambda:g.check_nav(nav.replace('    @Test\n','',1)),'NAV3_TWO_TESTS'),
  (lambda:g.check_nav(nav.replace('ComposeActivity::class.java','FakeNavigator::class.java')),'NAV3_MARKER_'),
  (lambda:g.check_nav(nav+'\n// OkHttpClient('),'NAV3_UNSAFE_'),
  (lambda:g.check_nav('import androidx.compose.ui.test.assertExists\n'+nav),
   'INVALID_COMPOSE_TEST_IMPORT'),
  (lambda:g.check_runner(run.replace('for profile in full compact; do','for profile in full; do')),'RUNNER_MARKER_'),
  (lambda:g.check_runner(run.replace('trap restore_display EXIT','echo ignore')),'RUNNER_MARKER_'),
  (lambda:g.check_runner(run.replace('verify_display "$profile" "${width}x${height}" "$density"', 'true')),'RUNNER_MARKER_'),
  (lambda:g.check_runner(run.replace('P13B_DISPLAY_PROBE_PASS', 'P13B_DISPLAY_PROBE_UNCHECKED')),'RUNNER_MARKER_'),
  (lambda:g.check_runner(run.replace('timeout 840 adb shell am instrument','adb shell am instrument')),'RUNNER_MARKER_'),
  (lambda:g.check_audit(audit.replace("'screenshots_count':48","'screenshots_count':16")),'AUDIT_MARKER_'),
  (lambda:g.check_audit(audit.replace("'manual_visual_approved':False","'manual_visual_approved':True")),'AUDIT_MARKER_'),
  (lambda:g.check_workflow(wf.replace('  contents: read','  contents: write')),'WORKFLOW_MARKER_'),
  (lambda:g.check_workflow(wf.replace('  contents: read','  contents: read\n  actions: write')),'WORKFLOW_WRITE_PERMISSION'),
  (lambda:g.check_signoff(sign.replace("'full_upstream_visual_signoff':False","'full_upstream_visual_signoff':True")),'SIGNOFF_MARKER_'),
  (lambda:g.check_references({**ref,'comparisons':{**ref['comparisons'],'for_you':{**ref['comparisons']['for_you'],'git_blob_sha1':'0'*40}}}),'REFERENCE_BLOB_'),
 ]
 for fn,code in negatives:refuses(fn,code)
 # Execute the exact Bash readback functions with fake adb outputs.
 # No actual ADB/device required; it tests executable behavior, not substrings.
 block = run.split('effective_wm_value() {',1)[1].split('run_class() {',1)[0]
 functions = 'effective_wm_value() {' + block
 assert functions.count('verify_display() {') == 1
 cases = (
   ('native-full', 'full', '1080x2400', '420',
       'Physical size: 1080x2400\r\n', 'Physical density: 420\r\n', True),
   ('override-full', 'full', '1080x2400', '420',
       'Physical size: 1080x2400\nOverride size: 1080x2400\n',
       'Physical density: 420\nOverride density: 420\n', True),
   ('override-compact', 'compact', '720x1600', '320',
       'Physical size: 1080x2400\nOverride size: 720x1600\n',
       'Physical density: 420\nOverride density: 320\n', True),
   ('wrong-size', 'compact', '720x1600', '320',
       'Physical size: 1080x2400\nOverride size: 900x1600\n',
       'Physical density: 420\nOverride density: 320\n', False),
   ('wrong-density', 'compact', '720x1600', '320',
       'Physical size: 1080x2400\nOverride size: 720x1600\n',
       'Physical density: 420\nOverride density: 240\n', False),
   ('stale-override', 'full', '1080x2400', '420',
       'Physical size: 1080x2400\nOverride size: 720x1600\n',
       'Physical density: 420\nOverride density: 320\n', False),
   ('unknown-readback', 'full', '1080x2400', '420',
       'wm service unavailable\n', 'Physical density: 420\n', False),
 )
 with tempfile.TemporaryDirectory(prefix='p13b-hf02-readback-') as temp:
  for tag,profile,size,density,raw_size,raw_density,should_pass in cases:
   code = functions + """
OUT="$TEST_OUT"
adb() {
 case "$*" in
   'shell wm size') printf '%s' "$TEST_SIZE_RAW" ;;
   'shell wm density') printf '%s' "$TEST_DENSITY_RAW" ;;
   *) echo MOCK_UNEXPECTED_ADB_CALL >&2; return 3 ;;
 esac
}
verify_display "$TEST_PROFILE" "$TEST_SIZE" "$TEST_DENSITY"
"""
   env=os.environ.copy()
   env.update(TEST_OUT=temp, TEST_PROFILE=profile, TEST_SIZE=size,
              TEST_DENSITY=density, TEST_SIZE_RAW=raw_size,
              TEST_DENSITY_RAW=raw_density, P13B_DISPLAY_PROBE_ATTEMPTS='1')
   p=subprocess.run(['bash','-euo','pipefail','-c',code],cwd=ROOT,env=env,
                    capture_output=True,text=True,timeout=10)
   assert (p.returncode==0)==should_pass, (tag,p.returncode,p.stdout,p.stderr)
   recorded=(Path(temp)/'metadata'/(profile+'-display-readback.log')).read_text()
   assert 'attempt=1' in recorded and 'effective=' in recorded,tag
   if should_pass: assert 'P13B_DISPLAY_PROBE_PASS' in p.stdout,tag
   else: assert 'P13B_REFUSED_DISPLAY_READBACK' in p.stderr,tag
 print('P13B_HF02_EFFECTIVE_DISPLAY_READBACK_POSITIVE_3_NEGATIVE_4_PASS')

 print(f'P13B_CONSOLIDATED_SOURCE_CONTRACT_PASS positive=7 mutations={len(negatives)}')

if __name__=='__main__':main()
