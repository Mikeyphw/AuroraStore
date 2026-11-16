#!/usr/bin/env python3
"""Independent P13-B upstream PR113 review gate. CI never auto-approves visuals.

An honest limited review can attest reviewed screenshots. A FINAL upstream visual
signoff is refused while any comparison is a synthetic component fixture or
no full-route catalog/account/search evidence exists. Cannot publish releases.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

REQUIRED = ('for_you','home_actions','top_charts','categories','details',
            'search','settings','customization')
ACK='I_REVIEWED_P13B_PNGS_AGAINST_AUTHOR_PR113'

class Refused(ValueError):pass

def need(cond,code):
 if not cond:raise Refused('P13B_VISUAL_SIGNOFF_REFUSED_'+code)

def read(path):return json.loads(Path(path).read_text())

def validate(receipt, references, review):
 need(receipt.get('schema')==2 and
      receipt.get('result')=='P13B_HOSTED_NAV3_20_TESTS_48_PNGS_PASS' and
      receipt.get('tests_executed')==20 and receipt.get('screenshots_count')==48,
      'RECEIPT_NOT_COMPLETE')
 need(receipt.get('manual_visual_approved') is False and
      receipt.get('full_upstream_visual_signoff') is False and
      receipt.get('release_qualified') is False,'AUTOMATIC_APPROVAL_PRESENT')
 need(references.get('schema')==1 and
      references.get('upstream_pull_request')=='https://github.com/whyorean/AuroraStore/pull/113' and
      tuple(references.get('comparisons',{}))==REQUIRED,
      'UNPINNED_UPSTREAM_REFERENCE_SET')
 for name,info in references['comparisons'].items():
  need(bool(re.fullmatch('[a-f0-9]{40}',info.get('git_blob_sha1',''))),
       'UPSTREAM_BLOB_'+name)
  need(info.get('comparability') in ('isolated_offline_fixture','production_navigation3_offline'),
       'BAD_COMPARABILITY_'+name)
  for profile in ('full','compact'):
   for mode in ('light','dark'):
    key=f'{profile}/{mode}/{info["actual"]}'
    need(key in receipt['screenshots'] and
         re.fullmatch('[a-f0-9]{64}',receipt['screenshots'][key]['sha256']) is not None,
         'MISSING_ACTUAL_SCREENSHOT_'+key)
 need(review.get('schema')==1 and review.get('source_sha')==receipt['source_sha'] and
      str(review.get('run_id'))==str(receipt['run_id']), 'REVIEW_SOURCE_OR_RUN_DRIFT')
 need(review.get('acknowledgement')==ACK,'EXPLICIT_REVIEW_ACK_REQUIRED')
 need(isinstance(review.get('reviewer'),str) and len(review['reviewer'].strip())>=2,
      'REVIEWER_REQUIRED')
 decisions=review.get('comparisons')
 need(isinstance(decisions,dict) and tuple(decisions)==REQUIRED,'REVIEW_INVENTORY')
 accepted=[]
 for name in REQUIRED:
  item=decisions[name]
  need(isinstance(item,dict),'INVALID_REVIEW_ITEM_'+name)
  need(item.get('source_blob')==references['comparisons'][name]['git_blob_sha1'],
       'REVIEW_REFERENCE_DRIFT_'+name)
  need(item.get('decision') in ('match','intentional_deviation','mismatch','not_comparable'),
       'REVIEW_DECISION_'+name)
  need(isinstance(item.get('notes'),str) and len(item['notes'].strip())>=12,
       'MISSING_EXPLANATION_'+name)
  if item['decision'] in ('match','intentional_deviation'):
   need(re.search(r'\b(?:pending|todo|not reviewed|placeholder)\b',item['notes'],re.I) is None,
        'UNREVIEWED_COMPARISON_'+name)
  accepted.append(item['decision'])
 need(review.get('release_approval') is False,'RELEASE_APPROVAL_NOT_ALLOWED')
 limited_ok=all(x in ('match','intentional_deviation') for x in accepted)
 final_requested=review.get('request_final_upstream_signoff') is True
 if final_requested:
  # The current offline fixture does not represent real populated Navigation3
  # data routes. An independent full-app comparison phase is prerequisite.
  need(all(info['comparability']=='production_navigation3_full_catalog'
           for info in references['comparisons'].values()) and
       receipt.get('populated_live_catalog_qualified') is True and
       receipt.get('full_search_viewmodel_qualified') is True and
       limited_ok, 'FULL_UPSTREAM_PARITY_UNSUPPORTED_BY_P13B_FIXTURES')
 return {
  'schema':1,'source_sha':receipt['source_sha'],'run_id':receipt['run_id'],
  'reviewer':review['reviewer'],'upstream_pr':'whyorean/AuroraStore#113',
  'reviewed_screens':list(REQUIRED),
  'limited_p13b_visual_review_approved':limited_ok,
  'full_upstream_visual_signoff':False,
  'reason':'offline fixture comparisons and unqualified full catalog routes',
  'release_qualified':False,
 }

def template(receipt,references):
 result={'schema':1,'source_sha':receipt['source_sha'],
  'run_id':receipt['run_id'],'reviewer':'',
  'acknowledgement':'', 'release_approval':False,
  'request_final_upstream_signoff':False,
  'comparisons':{}}
 for name,info in references['comparisons'].items():
  result['comparisons'][name]={
   'source_blob':info['git_blob_sha1'],
   'decision':'not_comparable',
   'notes':'PENDING: compare all 4 real capture variants to original PR113 references.'}
 return result

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--receipt',required=True,type=Path)
 ap.add_argument('--references',type=Path,default=Path(__file__).resolve().parents[2]/'docs/r4/R4_P13B_UPSTREAM_PR113_REFERENCES.json')
 ap.add_argument('--template',type=Path)
 ap.add_argument('--review',type=Path)
 ap.add_argument('--out',type=Path)
 args=ap.parse_args()
 receipt,refs=read(args.receipt),read(args.references)
 if args.template:
  args.template.write_text(json.dumps(template(receipt,refs),indent=2)+'\n')
  print('P13B_VISUAL_REVIEW_TEMPLATE_CREATED_APPROVAL_PENDING')
  return
 need(args.review is not None and args.out is not None,'REVIEW_AND_OUT_REQUIRED')
 result=validate(receipt,refs,read(args.review))
 args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
 print('P13B_LIMITED_VISUAL_REVIEW_COMPLETE',result['limited_p13b_visual_review_approved'])
 print('P13B_FINAL_UPSTREAM_VISUAL_SIGNOFF_PENDING_FULL_NAVIGATION_CATALOG_EVIDENCE')

if __name__=='__main__':
 try:main()
 except (ValueError,OSError,KeyError,TypeError) as exc:
  print(str(exc),file=sys.stderr)
  sys.exit(2)
