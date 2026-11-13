#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""P08 negative cases must fail without GitHub API or Android device access."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import r4_p08_retained_decisions as m

ROOT=Path(__file__).resolve().parents[2]


def reject(fn,needle):
    try:fn()
    except m.Refused as e: assert needle in str(e),(needle,str(e))
    else:raise AssertionError('R4_P08_UNSAFE_CASE_PASSED_'+needle)

def main():
    ledger=json.loads((ROOT/m.LEDGER).read_text())
    records=m.validate_ledger(ledger)
    assert len(records)==19
    assert len(m.BEHAVIOR_FOLLOWUPS)==2
    cases=0
    def tweak(fn,marker):
        nonlocal cases
        v=copy.deepcopy(ledger);fn(v)
        reject(lambda:m.validate_ledger(v),marker);cases+=1
    tweak(lambda v:v['decisions'].pop(),'RETAINED_COUNT_NOT_19')
    tweak(lambda v:v['decisions'].__setitem__(0,v['decisions'][1]),'RETAINED_PATH_SET_DRIFT')
    tweak(lambda v:v.__setitem__('review_head','0'*40),'LEDGER_IDENTITY_review_head')
    tweak(lambda v:v.__setitem__('source_diff_review_only',False),'LEDGER_IDENTITY_source_diff_review_only')
    tweak(lambda v:v.__setitem__('manual_upstream_visual_parity_approved',True),'UNQUALIFIED_FLAG_manual_upstream_visual_parity_approved')
    tweak(lambda v:v.__setitem__('physical_arm64_qualified',True),'UNQUALIFIED_FLAG_physical_arm64_qualified')
    tweak(lambda v:v.__setitem__('release_qualified',True),'UNQUALIFIED_FLAG_release_qualified')
    tweak(lambda v:v['decisions'][0].__setitem__('reason',''), 'MISSING_DIFF_RATIONALE')
    tweak(lambda v:v['decisions'][0].__setitem__('required_source_anchor',''), 'MISSING_SOURCE_ANCHOR')
    tweak(lambda v:v['decisions'][0].__setitem__('manual_behavior_qualified',True), 'BEHAVIOR_QUALIFICATION_FABRICATED')
    follow=m.BEHAVIOR_FOLLOWUPS
    tweak(lambda v:next(z for z in v['decisions'] if z['path'] in follow).__setitem__('source_diff_disposition','source_retention'),'BEHAVIOR_FOLLOWUP_DOWNGRADED')
    tweak(lambda v:v['decisions'][0].__setitem__('category','not-reviewed'),'UNREVIEWED_CATEGORY')
    tweak(lambda v:v['decisions'][0].__setitem__('extra_authorized','yes'),'UNREVIEWED_FIELDS')
    base={x:'0'*40 for x in records};author={x:'1'*40 for x in records};head=base.copy()
    body={x:records[x]['required_source_anchor']+' test fixture' for x in records}
    m.verify_retained_blobs(records,base,author,head,lambda x:body[x])
    p=next(iter(records))
    head[p]='2'*40
    reject(lambda:m.verify_retained_blobs(records,base,author,head,lambda x:body[x]),
           'REVIEWED_BASE_BLOB_DRIFT')
    head[p]=base[p];body[p]='not the required original source'
    reject(lambda:m.verify_retained_blobs(records,base,author,head,lambda x:body[x]),
           'RETAINED_BEHAVIOR_ANCHOR_DRIFT')
    author[p]=base[p]
    reject(lambda:m.verify_retained_blobs(records,base,author,head,lambda x:records[x]['required_source_anchor']),
           'UPSTREAM_WAS_NOT_CHANGED')
    assert cases==13,cases
    # Verify the new source checks are run by the hosted workflow. It must
    # still execute P07 parity and real 43/25 emulator gates.
    wf=(ROOT/'.github/workflows/aurora-r4-p05-device-ux.yml').read_text()
    assert wf.count('python3 -B scripts/ci/test_r4_p08_retained_decisions.py')==1
    assert wf.count('python3 -B scripts/ci/r4_p08_retained_decisions.py --repo .')==1
    assert wf.count('python3 -B scripts/ci/r4_p07_source_parity.py --repo .')==1
    assert 'bash scripts/ci/r4_p05_emulator_acceptance.sh' in wf
    assert 'actions: read' in wf and 'GH_TOKEN: ${{ github.token }}' in wf
    print('R4_P08_LEDGER_19_DIFFERENCES_13_NEGATIVES_THREE_BLOB_DRIFTS_PASS')
    print('R4_P08_HOSTED_SOURCE_AND_REAL_EMULATOR_GATES_RETAINED_PASS')

if __name__=='__main__':main()
