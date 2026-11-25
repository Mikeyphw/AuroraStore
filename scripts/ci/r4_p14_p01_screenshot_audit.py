#!/usr/bin/env python3
"""P14 P01 real API36 screenshot auditor; 4 journeys * 2 themes * 2 sizes.

No human signoff is inferred from automated screenshot results.
"""
from __future__ import annotations
import argparse,json,re,sys
from pathlib import Path
import r4_p05_screenshot_audit as p12
PROFILES={'full':(1080,2400,420),'compact':(720,1600,320)}
MODES=('light','dark')
IMAGES=('r4_p14_search_route.png','r4_p14_downloads_route.png',
        'r4_p14_settings_route.png','r4_p14_preferences_route.png',
        'r4_p14_games_tab.png','r4_p14_updates_tab.png',
        'r4_p14_populated_search.png','r4_p14_details_identity.png',
        'r4_p14_details_carousel.png','r4_p14_details_reviews.png')
P13='47c360e9cb553f73fb6858cd364ea19835bada6e'
P13_RUN=43650748680

def need(ok,code):
 if not ok:raise ValueError('P14_P01_REFUSED_'+code)

def validate(root:Path,source:str,run:str):
 need(re.fullmatch(r'[0-9a-f]{40}',source) is not None,'SOURCE')
 need(re.fullmatch(r'[0-9]+',str(run)) is not None,'RUN')
 need((root/'metadata/source-sha.txt').read_text().strip()==source,'SOURCE_MISMATCH')
 need((root/'metadata/run-id.txt').read_text().strip()==str(run),'RUN_MISMATCH')
 seen={};images={}
 for profile,(width,height,density) in PROFILES.items():
  need((root/'metadata'/(profile+'.txt')).read_text().strip()==f'{width}x{height} density={density}', 'PROFILE_'+profile)
  for mode in MODES:
   log=(root/'logs'/profile/('p14-'+mode+'.txt')).read_text()
   need('OK (4 tests)' in log and 'INSTRUMENTATION_CODE: -1' in log and
        'FAILURES!!!' not in log and 'INSTRUMENTATION_STATUS_CODE: -2' not in log,'TESTS_'+profile+'_'+mode)
   for name in IMAGES:
    key=f'{profile}/{mode}/{name}'
    info=p12.load_pixels(root/'screenshots'/profile/mode/name)
    need((info['width'],info['height'])==(width,height),'DIMENSIONS_'+key)
    need(info['sha256'] not in seen,'DUPLICATE_'+seen.get(info['sha256'],'UNKNOWN')+'_'+key)
    seen[info['sha256']]=key;images[key]=info
 for profile in PROFILES:
  for name in IMAGES:
   need(images[f'{profile}/light/{name}']['sha256']!=images[f'{profile}/dark/{name}']['sha256'],'THEMES_'+profile+'_'+name)
 need(len(seen)==len(images)==40,'INVENTORY')
 return {'schema':1,'result':'P14_P01_P02_HOSTED_16_TESTS_40_PNGS_PASS','source_sha':source,
         'run_id':str(run),'android_api':36,'abi':'x86_64',
         'tests_executed':16,'screenshots_count':40,'screenshots':images,
         'viewport_profiles':PROFILES,'themes':list(MODES),
         'production_navigation3_offline_qualified':True,
         'routes':['Main -> Search -> Back -> Downloads -> Back',
                   'Main -> More -> Settings -> UI Preferences -> Back -> Back',
                   'Main Apps -> Games -> Updates -> Apps',
                   'Main -> Search -> typed results -> Details header/carousel/review (Hilt fixture)'],
         'p13_frozen':{'source_sha':P13,'run_id':P13_RUN,'tests_executed':20,'screenshots_count':48},
         'populated_live_catalog_qualified':False,'full_search_viewmodel_qualified':True,
         'deterministic_search_details_viewmodels_qualified':True,
         'real_account_qualified':False,'real_installer_qualified':False,
         'physical_arm64_qualified':False,'full_upstream_visual_signoff':False,
         'release_qualified':False}

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
 p.add_argument('--source',required=True);p.add_argument('--run',required=True)
 p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 a.out.write_text(json.dumps(validate(a.root,a.source,a.run),indent=2,sort_keys=True)+'\n')
 print('P14_P01_P02_HOSTED_16_TESTS_40_PNGS_PASS')
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,KeyError,TypeError) as e:
  print(str(e),file=sys.stderr);sys.exit(2)
