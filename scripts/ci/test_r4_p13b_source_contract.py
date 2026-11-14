#!/usr/bin/env python3
"""P13-B consolidated local source and adversarial CI mutation selftests."""
from pathlib import Path
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
  (lambda:g.check_test(test.replace('Screenshots(screenshots = inputArt)','Screenshots(screenshots = emptyList())')),'INTEGRATED_MARKER_'),
  (lambda:g.check_test(test+'\n// PackageInstaller('),'INTEGRATED_UNSAFE_'),
  (lambda:g.check_nav(nav.replace('    @Test\n','',1)),'NAV3_TWO_TESTS'),
  (lambda:g.check_nav(nav.replace('ComposeActivity::class.java','FakeNavigator::class.java')),'NAV3_MARKER_'),
  (lambda:g.check_nav(nav+'\n// OkHttpClient('),'NAV3_UNSAFE_'),
  (lambda:g.check_runner(run.replace('for profile in full compact; do','for profile in full; do')),'RUNNER_MARKER_'),
  (lambda:g.check_runner(run.replace('trap restore_display EXIT','echo ignore')),'RUNNER_MARKER_'),
  (lambda:g.check_runner(run.replace('timeout 840 adb shell am instrument','adb shell am instrument')),'RUNNER_MARKER_'),
  (lambda:g.check_audit(audit.replace("'screenshots_count':48","'screenshots_count':16")),'AUDIT_MARKER_'),
  (lambda:g.check_audit(audit.replace("'manual_visual_approved':False","'manual_visual_approved':True")),'AUDIT_MARKER_'),
  (lambda:g.check_workflow(wf.replace('  contents: read','  contents: write')),'WORKFLOW_MARKER_'),
  (lambda:g.check_workflow(wf.replace('  contents: read','  contents: read\n  actions: write')),'WORKFLOW_WRITE_PERMISSION'),
  (lambda:g.check_signoff(sign.replace("'full_upstream_visual_signoff':False","'full_upstream_visual_signoff':True")),'SIGNOFF_MARKER_'),
  (lambda:g.check_references({**ref,'comparisons':{**ref['comparisons'],'for_you':{**ref['comparisons']['for_you'],'git_blob_sha1':'0'*40}}}),'REFERENCE_BLOB_'),
 ]
 for fn,code in negatives:refuses(fn,code)
 print(f'P13B_CONSOLIDATED_SOURCE_CONTRACT_PASS positive=7 mutations={len(negatives)}')

if __name__=='__main__':main()
