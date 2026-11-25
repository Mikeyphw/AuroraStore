#!/usr/bin/env python3
"""Only synthetic selftest receipts, never production visual approval."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import r4_p13b_visual_signoff as g

ROOT=Path(__file__).resolve().parents[2]
REF=json.loads((ROOT/'docs/r4/R4_P13B_UPSTREAM_PR113_REFERENCES.json').read_text())
SHA='a'*40
RUN='12345'
def receipt():
 return {'schema':2,'result':'P13B_HOSTED_NAV3_20_TESTS_48_PNGS_PASS',
  'source_sha':SHA,'run_id':RUN,'tests_executed':20,'screenshots_count':48,
  'manual_visual_approved':False,'full_upstream_visual_signoff':False,
  'release_qualified':False,
  'screenshots':{f'{profile}/{mode}/{i["actual"]}':{'sha256':'f'*64}
    for profile in ('full','compact') for mode in ('light','dark')
    for i in REF['comparisons'].values()},
  'populated_live_catalog_qualified':False,'full_search_viewmodel_qualified':False}

def must_refuse(r,rev,why):
 try:g.validate(r,REF,rev)
 except g.Refused as e:assert why in str(e),(why,str(e))
 else:raise AssertionError('SIGNOFF_MUTATION_NOT_REFUSED_'+why)

def main():
 r=receipt();v=g.template(r,REF)
 assert all(x['decision']=='not_comparable' for x in v['comparisons'].values())
 must_refuse(r,v,'EXPLICIT_REVIEW_ACK_REQUIRED')
 v['acknowledgement']=g.ACK
 v['reviewer']='Independent reviewer'
 z=g.validate(r,REF,v)
 assert not z['limited_p13b_visual_review_approved']
 assert z['full_upstream_visual_signoff'] is False
 assert z['release_qualified'] is False
 for k in g.REQUIRED:
  v['comparisons'][k]['decision']='match'
  v['comparisons'][k]['notes']='Reviewed all four variant images against the original PR113.'
 z=g.validate(r,REF,v)
 assert z['limited_p13b_visual_review_approved'] is True
 assert z['full_upstream_visual_signoff'] is False
 v['request_final_upstream_signoff']=True
 must_refuse(r,v,'FULL_UPSTREAM_PARITY_UNSUPPORTED_BY_P13B_FIXTURES')
 v['request_final_upstream_signoff']=False
 v['release_approval']=True
 must_refuse(r,v,'RELEASE_APPROVAL_NOT_ALLOWED')
 v['release_approval']=False
 v['source_sha']='b'*40
 must_refuse(r,v,'REVIEW_SOURCE_OR_RUN_DRIFT')
 v['source_sha']=SHA
 v['comparisons']['search']['source_blob']='c'*40
 must_refuse(r,v,'REVIEW_REFERENCE_DRIFT_search')
 v['comparisons']['search']['source_blob']=REF['comparisons']['search']['git_blob_sha1']
 v['comparisons']['details']['decision']='bypass'
 must_refuse(r,v,'REVIEW_DECISION_details')
 v['comparisons']['details']['decision']='match'
 v['comparisons']['details']['notes']='PENDING: compare later.'
 must_refuse(r,v,'UNREVIEWED_COMPARISON_details')
 print('P13B_VISUAL_SIGNOFF_SELFTEST_PASS limited_manual_only; final/release REFUSED')

if __name__=='__main__':main()
