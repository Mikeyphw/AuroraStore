#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""P12 regression source/approval negatives: no network or Android access."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import r4_p12_visual_contrast_gate as m
ROOT=Path(__file__).resolve().parents[2]

def must_refuse(fn,needle):
    try: fn()
    except m.Refused as e: assert needle in str(e),(needle,str(e))
    else: raise AssertionError('R4_P12_UNSAFE_MUTATION_ACCEPTED_'+needle)

def main():
    status=json.loads((ROOT/m.STATUS).read_text())
    m.check_status(status)
    cases=0
    for field,bad in (
        ('fresh_p12_hosted_result_qualified',True),
        ('populated_catalog_visuals_qualified',True),
        ('all_upstream_visual_parity_approved',True),
        ('live_google_play_qualified',True),
        ('physical_arm64_qualified',True),
        ('real_installer_qualified',True),
        ('automatic_merge_allowed',True),
        ('release_qualified',True),
    ):
        altered=copy.deepcopy(status);altered[field]=bad
        must_refuse(lambda altered=altered:m.check_status(altered),'FALSE_APPROVAL');cases+=1
    for field,bad in (
        ('p11_parent_sha','0'*40),('old_background_rgb',[255,255,255]),
        ('old_p09_evidence_only_historical',False),('fresh_p12_emulator_required',False),
    ):
        altered=copy.deepcopy(status);altered[field]=bad
        must_refuse(lambda altered=altered:m.check_status(altered),'STATUS_IDENTITY');cases+=1
    preimage='header\n'+m.OLD+'\nfooter'
    m.check_patch(preimage,preimage.replace(m.OLD,m.NEW))
    for changed in (preimage,preimage.replace(m.OLD,m.NEW).replace('footer','hacked'),
                    preimage.replace(m.OLD,m.NEW).replace('onSurface','primary')):
        must_refuse(lambda changed=changed:m.check_patch(preimage,changed),
                    'PRODUCTION_CHANGE_BEYOND_CONTRAST_FIX');cases+=1
    a=(ROOT/m.PIXEL_AUDIT).read_text()
    t=(ROOT/m.PIXEL_TESTS).read_text()
    m.check_pixel_source(a,t)
    # Every piece of the executable counter path must be required. These
    # mutations used to pass when one occurrence of the name was left intact.
    for original, replacement in (
        ('p12_dark_updates_label_bright_samples = 0', 'wrong = 0'),
        ('p12_dark_updates_label_bright_samples += 1', 'wrong += 1'),
        ("'p12_dark_updates_label_bright_samples': p12_dark_updates_label_bright_samples,",
         "'p12_dark_updates_label_bright_samples': wrong,"),
        ("'p12_dark_updates_label_bright_samples', 0) >= 50,",
         "'p12_dark_updates_label_bright_samples', 0) >= 1,"),
        ("    require(pngs['dark/r4_activity_updates.png'].get(",
         "    ignored(pngs['dark/r4_activity_updates.png'].get("),
    ):
        assert original in a, 'R4_P12_TEST_FIXTURE_MISSING_'+original
        must_refuse(lambda original=original,replacement=replacement:
                    m.check_pixel_source(a.replace(original,replacement,1),t),
                    'PIXEL_AUDIT_MISSING')
        cases+=1
    must_refuse(lambda:m.check_pixel_source(a,t.replace('foreground=(0,0,0)','no_regression')),
                'PIXEL_NEGATIVE_NOT_ENFORCED');cases+=1
    fixture=(ROOT/m.POPULATED_TEST).read_text()
    m.check_populated_test(fixture)
    for marker in ('StreamCarousel(', 'SearchResultListItem(', 'Details(app = app)',
                   'TopChartsBody(', 'CategoriesBody(', 'AppUpdateItem('):
        must_refuse(lambda marker=marker:m.check_populated_test(fixture.replace(marker,'REMOVED(')),
                    'POPULATED_MISSING');cases+=1
    wf=(ROOT/m.WORKFLOW).read_text()
    m.check_workflow(wf)
    for old,new,marker in (
        ('python3 -B scripts/ci/test_r4_p12_visual_contrast_gate.py','echo fake','MISSING_WORKFLOW_STEP'),
        ('python3 -B scripts/ci/r4_p12_visual_contrast_gate.py --root .','echo fake','MISSING_WORKFLOW_STEP'),
        ('bash scripts/ci/r4_p05_emulator_acceptance.sh','echo fake','MISSING_WORKFLOW_STEP'),
        ('  contents: read','  contents: write','WORKFLOW_PERMISSION_ESCALATION'),
    ):
        assert old in wf,old
        must_refuse(lambda old=old,new=new:m.check_workflow(wf.replace(old,new,1)),marker);cases+=1
    assert cases==31,cases
    print('R4_P12_HF25_HF01_31_ADVERSARIAL_SOURCE_AND_RELEASE_REFUSALS_PASS')
    print('R4_P12_FRESH_HOSTED_CONTRAST_PIXEL_CHECK_REQUIRED')

if __name__=='__main__':main()
