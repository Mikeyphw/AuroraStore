#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fail-closed, source-scoped PR113/R3D retained-file decisions.

This is a review ledger, NOT material visual signoff or device qualification.
It pins 19 author-changed Compose paths retained from R3D to their genuine Git
objects and named compatibility/safety reasons. An unreviewed change to these
paths must not silently inherit the prior analysis. Zero network/Gradle access.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

import r4_p07_source_parity as parity

LEDGER = Path('docs/r4/R4_P08_RETAINED_DECISIONS.json')
REVIEW_HEAD = 'de3a9441eff1524b53fb8560385cdf9a4f7e0b9e'
P11_SOURCE_CHECKPOINT = '9632c29bc19248bb905d1aaa257469118576312d'
EXPECTED = frozenset(parity.BASE_RETAINED_REVIEW)
BEHAVIOR_FOLLOWUPS = frozenset({
    parity.PREFIX + 'ui/accounts/GoogleLoginScreen.kt',
    parity.PREFIX + 'ui/spoof/SpoofScreen.kt',
})
DISPOSITIONS = frozenset({'source_retention','behavior_followup'})
CATEGORIES = frozenset({
    'gplayapi_v4', 'api23_permission_safety', 'api23_resources',
    'download_state_safety','session_api_v4','session_restart_behavior',
    'compatible_comparator','resources_compat','installer_safety','history_safety',
})
FLAGS = (
    'manual_upstream_visual_parity_approved','physical_arm64_qualified',
    'live_google_play_qualified','real_installer_qualified',
    'release_qualified','automatic_merge_allowed',
)

class Refused(RuntimeError): pass

def need(condition:bool, reason:str):
    if not condition: raise Refused('R4_P08_REFUSED_'+reason)

def command(root:Path, *args:str) -> str:
    p=subprocess.run(['git',*args],cwd=root,capture_output=True)
    need(p.returncode==0, 'GIT_'+args[0]+'_'+p.stderr.decode('utf-8','replace')[-220:])
    return p.stdout.decode('utf-8').strip()

def validate_ledger(doc:dict) -> dict[str,dict]:
    need(isinstance(doc,dict),'LEDGER_NOT_OBJECT')
    for key,value in (
        ('schema',1),('kind','aurora-r4-pr113-r3d-retained-source-decision-ledger'),
        ('repository',parity.REPO),('review_head',REVIEW_HEAD),
        ('r3d_base',parity.BASE),('upstream_author',parity.AUTHOR),
        ('genuine_merge',parity.MERGE),('author_changed_compose_paths',100),
        ('retained_r3d_paths',19),('source_diff_review_only',True),
    ):
        need(doc.get(key)==value,'LEDGER_IDENTITY_'+key)
    for key in FLAGS: need(doc.get(key) is False,'UNQUALIFIED_FLAG_'+key)
    recs=doc.get('decisions')
    need(isinstance(recs,list) and len(recs)==19,'RETAINED_COUNT_NOT_19')
    paths=[d.get('path') if isinstance(d,dict) else None for d in recs]
    need(len(set(paths))==19 and set(paths)==EXPECTED,'RETAINED_PATH_SET_DRIFT')
    results={}
    for d in recs:
        path=d['path']
        need(path.startswith(parity.PREFIX) and path.endswith('.kt') and
             not any(x in path for x in ('..','\\','\x00')),
             'UNSAFE_PATH_'+str(path))
        need(isinstance(d.get('category'),str) and d['category'] in CATEGORIES,
             'UNREVIEWED_CATEGORY_'+path)
        disposition=d.get('source_diff_disposition')
        need(disposition in DISPOSITIONS,'UNREVIEWED_DISPOSITION_'+path)
        want=('behavior_followup' if path in BEHAVIOR_FOLLOWUPS else 'source_retention')
        need(disposition==want,'BEHAVIOR_FOLLOWUP_DOWNGRADED_'+path)
        need(isinstance(d.get('reason'),str) and len(d['reason'])>=45,
             'MISSING_DIFF_RATIONALE_'+path)
        anchor=d.get('required_source_anchor')
        need(isinstance(anchor,str) and len(anchor)>=10 and '\n' not in anchor,
             'MISSING_SOURCE_ANCHOR_'+path)
        need(d.get('manual_behavior_qualified') is False,
             'BEHAVIOR_QUALIFICATION_FABRICATED_'+path)
        need(set(d)=={'path','category','source_diff_disposition','reason',
                      'required_source_anchor','manual_behavior_qualified'},
             'UNREVIEWED_FIELDS_'+path)
        results[path]=d
    return results

def verify_retained_blobs(records:dict, baseline:dict, author:dict,
                          head:dict, get_content) -> None:
    for path,d in sorted(records.items()):
        need(path in baseline and path in author and path in head,
             'MISSING_RETAINED_BLOB_'+path)
        need(author[path]!=baseline[path], 'UPSTREAM_WAS_NOT_CHANGED_'+path)
        need(head[path]==baseline[path], 'REVIEWED_BASE_BLOB_DRIFT_'+path)
        body=get_content(path)
        need(isinstance(body,str) and d['required_source_anchor'] in body,
             'RETAINED_BEHAVIOR_ANCHOR_DRIFT_'+path)

def verify(root:Path) -> dict:
    doc=json.loads((root/LEDGER).read_text(encoding='utf-8'))
    records=validate_ledger(doc)
    head=command(root,'rev-parse','HEAD')
    need(re.fullmatch('[a-f0-9]{40}',head) is not None,'INVALID_GIT_HEAD')
    need(subprocess.run(['git','merge-base','--is-ancestor',REVIEW_HEAD,head],
                        cwd=root,capture_output=True).returncode==0,
         'UNREVIEWED_COMMIT_HISTORY')
    # P08 source review is historical. Do not pretend that a later, explicitly
    # isolated P12 contrast fix was covered by the P08 Compose audit.
    need(subprocess.run(['git','merge-base','--is-ancestor',P11_SOURCE_CHECKPOINT,head],
                        cwd=root,capture_output=True).returncode==0,
         'P11_SOURCE_CHECKPOINT_NOT_ANCESTOR')
    changed=command(root,'diff','--name-only',REVIEW_HEAD,P11_SOURCE_CHECKPOINT,'--',parity.PREFIX)
    need(not changed,'UNREVIEWED_COMPOSE_SOURCE_CHANGE_'+changed)
    # P07 validates both genuine merge parents and protected R3D Git blobs.
    current=parity.review(root, at=P11_SOURCE_CHECKPOINT)
    groups=current['classification']
    need(len(groups['author_changed'])==100 and len(groups['exact_author'])==33 and
         len(groups['adapted'])==48 and len(groups['base_retained'])==19,
         'P07_UPSTREAM_PARITY_COUNTS_DRIFT')
    need(set(groups['base_retained'])==set(records),'MISSING_OR_EXTRA_RETAINED_DECISIONS')
    base=parity.tree(root,parity.BASE)
    upstream=parity.tree(root,parity.AUTHOR)
    now=parity.tree(root,P11_SOURCE_CHECKPOINT)
    def content(path):return command(root,'show',P11_SOURCE_CHECKPOINT+':'+path)
    verify_retained_blobs(records,base,upstream,now,content)
    return {
        'kind':'aurora-r4-p08-source-review-receipt','schema':1,
        'reviewed_at_source_sha':REVIEW_HEAD,'audited_head_sha':P11_SOURCE_CHECKPOINT,
        'current_execution_head_sha':head,'historical_p11_review_only':True,
        'author_changed_compose_paths':100,'author_exact':33,'r3d_adapted':48,
        'r3d_retained_reviewed':19,
        'requires_behavior_followup':sorted(BEHAVIOR_FOLLOWUPS),
        'hosted_43_test_25_screenshot_prior_success_sha':REVIEW_HEAD,
        'no_production_compose_modifications_since_review':False,
        'later_p12_compose_changes_require_fresh_hosted_emulator':True,
        'source_ledger_validated':True,
        'source_diff_review_only':True,
        'manual_upstream_visual_parity_approved':False,
        'physical_arm64_qualified':False,'live_google_play_qualified':False,
        'real_installer_qualified':False,'release_qualified':False,
        'automatic_merge_allowed':False,
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path('.'))
    p.add_argument('--out',type=Path)
    a=p.parse_args()
    receipt=verify(a.repo.resolve(strict=True))
    if a.out:
        need(not a.out.exists(),'OUTPUT_ALREADY_EXISTS')
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print('R4_P08_PR113_R3D_NINETEEN_SOURCE_DIFF_DECISIONS_AND_GIT_ANCHORS_PASS')
    print('R4_P08_TWO_SESSION_BEHAVIOR_FOLLOWUPS_REMAIN_UNQUALIFIED')
    print('R4_P08_NO_RELEASE_PHYSICAL_OR_LIVE_PLAY_QUALIFICATION_CLAIMED')

if __name__=='__main__':
    try:main()
    except (Refused,OSError,ValueError,KeyError) as e:
        print(str(e),file=sys.stderr)
        sys.exit(2)
