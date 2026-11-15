#!/usr/bin/env python3
"""Adversarial mutations: no fake signoff, skip tests, dropped screenshots, source drift."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import r4_p14_p01_source_contract as g
ROOT=Path(__file__).resolve().parents[2]
def refused(fn,fragment):
 try:fn()
 except g.Refused as e:assert fragment in str(e),str(e)
 else:raise AssertionError('P14_P01_MUTATION_NOT_REFUSED_'+fragment)
def run():
 t=(ROOT/g.TEST).read_text();r=(ROOT/g.RUN).read_text();a=(ROOT/g.AUDIT).read_text();w=(ROOT/g.WF).read_text()
 assert g.source_checks(ROOT)
 gateway=(ROOT/g.GATEWAY).read_text()
 hilt=(ROOT/g.HILT).read_text()
 patches=json.loads((ROOT/g.PATCHES).read_text())
 mutations=[
  (lambda:g.check_test(t.replace('    @Test\n','',1)),'FOUR_REAL_TESTS'),
  (lambda:g.check_test(t.replace('ComposeActivity::class.java','OtherActivity::class.java')),'TEST_MARKER_'),
  (lambda:g.check_test(t.replace('HiltAndroidRule(this)','OtherRule(this)')),'TEST_MARKER_'),
  (lambda:g.check_test(t.replace('SemanticsProperties.Selected','true')),'TEST_MARKER_'),
  (lambda:g.check_test(t.replace(
      'it.config.getOrElse(SemanticsProperties.Selected) { false }',
      'it.config.getOrNull(SemanticsProperties.Selected)')),
   'COMPOSE_SELECTED_MEMBER_ACCESS'),
  (lambda:g.check_test(t.replace(
      'it.config.getOrElse(SemanticsProperties.Selected) { false }',
      'it.config.getOrElse(SemanticsProperties.Selected) { true }')),
   'COMPOSE_SELECTED_MEMBER_ACCESS'),
  (lambda:g.check_test(t.replace('"Import and verify APKs"','"Ignored"')),'TEST_MARKER_'),
  (lambda:g.check_test(t.replace('r4_p14_updates_tab.png','r4_p14_missing.png')),'TEST_MARKER_'),
  (lambda:g.check_test(t.replace('P14_REFUSED_STALE_BODY_FRAME','P14_ALLOW_STALE_BODY_FRAME')),'TEST_MARKER_'),
  (lambda:g.check_test(t.replace('primeVisualBaseline()','ignoreBaseline()')),'TEST_MARKER_'),
  (lambda:g.check_test(t+'\n// PackageInstaller('),'TEST_UNSAFE_'),
  (lambda:g.check_test(t+'\n// su -c'),'TEST_UNSAFE_'),
  (lambda:g.check_run(r.replace('for mode in light dark;do','for mode in light;do')),'RUNNER_MARKER_'),
  (lambda:g.check_run(r.replace('for profile in full compact;do','for profile in full;do')),'RUNNER_MARKER_'),
  (lambda:g.check_run(r.replace('trap restore_display EXIT','true')),'RUNNER_MARKER_'),
  (lambda:g.check_run(r.replace('timeout 840 adb shell am instrument','adb shell am instrument')),'RUNNER_MARKER_'),
  (lambda:g.check_audit(a.replace("'screenshots_count':40","'screenshots_count':12")),'AUDIT_MARKER_'),
  (lambda:g.check_audit(a.replace("'release_qualified':False","'release_qualified':True")),'AUDIT_MARKER_'),
  (lambda:g.check_workflow(w.replace('  contents: read','  contents: write')),'WORKFLOW_MARKER_'),
  (lambda:g.check_workflow(w.replace('persist-credentials: false','persist-credentials: true')),'WORKFLOW_MARKER_'),
  (lambda:g.check_test(t.replace('fun realSearchToFullDetailsHeaderArtworkAndReviews()', 'fun fakeDetails()')),'TEST_MARKER_'),
  (lambda:g.check_test(t.replace('r4_p14_details_reviews.png','r4_p14_fake.png')),'TEST_MARKER_'),
  (lambda:g.check_gateway(gateway.replace('class LiveCatalogJourneyGateway @Inject constructor()','class LiveCatalogJourneyGateway')),'GATEWAY_'),
  (lambda:g.check_hilt(hilt.replace('replaces = [CatalogJourneyGatewayModule::class]','replaces = []')),'HILT_'),
  (lambda:g.check_hilt(hilt+'\n// PackageInstaller('),'HILT_FORBIDDEN_'),
  (lambda:g.check_patches({k:v for k,v in patches.items() if k!=g.PRODUCTION_PATHS[0]}),'PATCH_INVENTORY'),
  (lambda:g.check_patches({**patches,g.PRODUCTION_PATHS[0]:{**patches[g.PRODUCTION_PATHS[0]],'replacements':[]}}),'PATCH_INVALID_'),
 ]
 for fn,code in mutations:refused(fn,code)
 print(f'P14_P01_SOURCE_MUTATIONS_PASS positive=6 negatives={len(mutations)}')
if __name__=='__main__':run()
