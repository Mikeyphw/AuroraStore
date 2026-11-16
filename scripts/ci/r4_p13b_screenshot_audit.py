#!/usr/bin/env python3
"""P13-B source/run-bound emulator evidence: 20 executions / 48 real screenshots.

Reuses P12's tested PNG decoder, refuses wrong dimensions, duplicate frames,
missing route logs or manual visual approvals inferred from automated evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import r4_p05_screenshot_audit as p12

PROFILES = {'full': (1080, 2400, 420), 'compact': (720, 1600, 320)}
MODES = ('light', 'dark')
INTEGRATED = (
 'r4_p13b_home.png','r4_p13b_charts.png','r4_p13b_categories.png',
 'r4_p13b_search.png','r4_p13b_details_top.png','r4_p13b_details_reviews.png',
 'r4_p13b_category_selection.png','r4_p13b_category_collection.png',
)
NAV3 = (
 'r4_p13b_nav_search.png','r4_p13b_nav_return.png',
 'r4_p13b_nav_settings.png','r4_p13b_nav_preferences.png',
)
IMAGES = INTEGRATED + NAV3
P12_SHA = '3ea10b6f4b0fed5a8913e4edef3536cfc93fc52f'
P12_RUN = 43612363362

def need(ok, code):
 if not ok: raise ValueError('P13B_REFUSED_'+code)

def validate(root: Path, source: str, run: str) -> dict:
 need(bool(re.fullmatch(r'[0-9a-f]{40}',source)), 'SOURCE_SHA')
 need(bool(re.fullmatch(r'[0-9]+',run)), 'RUN_ID')
 need((root/'metadata/source-sha.txt').read_text().strip()==source, 'SOURCE_MISMATCH')
 need((root/'metadata/run-id.txt').read_text().strip()==run, 'RUN_MISMATCH')
 pngs, seen = {}, {}
 for profile,(width,height,density) in PROFILES.items():
  need((root/'metadata'/(profile+'.txt')).read_text().strip()==
       f'{width}x{height} density={density}', 'DISPLAY_PROFILE_'+profile)
  for mode in MODES:
   for name in IMAGES:
    key=f'{profile}/{mode}/{name}'
    path=root/'screenshots'/profile/mode/name
    evidence=p12.load_pixels(path)
    need((evidence['width'],evidence['height'])==(width,height),
         'PNG_DIMENSIONS_'+key)
    need(evidence['sha256'] not in seen,
         'DUPLICATE_FRAME_'+seen.get(evidence['sha256'],'')+'__'+key)
    seen[evidence['sha256']]=key
    pngs[key]=evidence
   for label,count in (('p13b-integrated',3),('p13b-nav3',2)):
    body=(root/'logs'/profile/(label+'-'+mode+'.txt')).read_text()
    need(f'OK ({count} tests)' in body and 'INSTRUMENTATION_CODE: -1' in body and
         'FAILURES!!!' not in body and 'INSTRUMENTATION_STATUS_CODE: -2' not in body,
         'SUITE_LOG_'+profile+'_'+mode+'_'+label)
 for profile in PROFILES:
  for name in IMAGES:
   need(pngs[f'{profile}/light/{name}']['sha256']!=
        pngs[f'{profile}/dark/{name}']['sha256'],
        'UNDIFFERENTIATED_THEME_'+profile+'_'+name)
 for mode in MODES:
  for name in IMAGES:
   need((pngs[f'full/{mode}/{name}']['width'],pngs[f'compact/{mode}/{name}']['width'])==
        (1080,720), 'UNDIFFERENTIATED_SIZE_'+mode+'_'+name)
 need(len(pngs)==48 and len(seen)==48, 'INVENTORY')
 return {
  'schema':2, 'result':'P13B_HOSTED_NAV3_20_TESTS_48_PNGS_PASS',
  'source_sha':source, 'run_id':run,'android_api':36,'abi':'x86_64',
  'tests_executed':20,'screenshots_count':48,
  'screenshots':pngs,'viewports':PROFILES,'themes':list(MODES),
  'fixture_component_executions':12, 'production_nav3_executions':8,
  'production_navigation3_route_qualified':True,
  'production_navigation3_route_scope':'Main -> Search -> Back; Main -> More -> Settings -> UI preferences',
  'full_search_viewmodel_qualified':False,
  'populated_live_catalog_qualified':False,
  'real_account_qualified':False,'real_installer_qualified':False,
  'physical_arm64_qualified':False,
  'p12_frozen':{'source_sha':P12_SHA,'run_id':P12_RUN,'executions':64,'screenshots':37},
  'manual_visual_approved':False,
  'full_upstream_visual_signoff':False,
  'release_qualified':False,
 }

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--root',required=True,type=Path)
 p.add_argument('--source',required=True)
 p.add_argument('--run',required=True)
 p.add_argument('--out',required=True,type=Path)
 a=p.parse_args()
 a.out.write_text(json.dumps(validate(a.root,a.source,a.run),indent=2,sort_keys=True)+'\n')
 print('P13B_HOSTED_NAV3_20_TESTS_48_PNGS_PASS_VISUAL_REVIEW_PENDING')

if __name__=='__main__':
 try:main()
 except (ValueError,OSError,KeyError,TypeError) as e:
  print(str(e),file=sys.stderr)
  sys.exit(2)
