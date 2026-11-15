#!/usr/bin/env python3
"""Fail-closed P14-P03 source/run-bound Android evidence audit (76 tests, 20 PNGs)."""
from __future__ import annotations
import argparse,hashlib,json,re,struct,sys
from pathlib import Path
import r4_p05_screenshot_audit as png

SHOTS=('r4_p14p03_queued.png','r4_p14p03_downloading.png','r4_p14p03_failed.png',
       'r1g_awaiting_retry.png','r1g_cancelled.png')
PROFILES={'full':(1080,2400,420),'compact':(720,1600,320)}
MODES=('light','dark')
WORKER_METHODS=('truncatedResponseRetriesThenResumesSameAttemptExactly',
 'shaMismatchRejectsPayloadWithoutInstallHandoff',
 'cancelledAttemptIsNotResurrectedOrDownloaded')
RESULT='P14P03_HOSTED_76_TESTS_20_PNGS_PASS'
def need(ok,reason):
 if not ok:raise ValueError('P14P03_REFUSED_'+reason)
def sha(data):return hashlib.sha256(data).hexdigest()
def validate(root:Path,source:str,run:str)->dict:
 need(bool(re.fullmatch('[a-f0-9]{40}',source)),'INVALID_SOURCE')
 need(bool(re.fullmatch('[0-9]+',str(run))),'INVALID_RUN')
 need((root/'metadata/source-sha.txt').read_text().strip()==source,'SOURCE_DRIFT')
 need((root/'metadata/run-id.txt').read_text().strip()==str(run),'RUN_DRIFT')
 images={};digests=set();total=0
 for profile,(width,height,density) in PROFILES.items():
  need((root/'metadata'/f'{profile}.txt').read_text().strip()==f'{width}x{height} density={density}','DISPLAY_'+profile)
  for mode in MODES:
   for label,count in (('lifecycle',8),('download-ui',4),('final-ui',4)):
    body=(root/'logs'/profile/f'{label}-{mode}.txt').read_text()
    need(f'OK ({count} tests)' in body and 'FAILURES!!!' not in body and
         'INSTRUMENTATION_STATUS_CODE: -2' not in body,'LOG_'+profile+'_'+mode+'_'+label)
    total+=count
   for name in SHOTS:
    key=f'{profile}/{mode}/{name}';path=root/'screenshots'/key
    parsed=png.load_pixels(path)
    need((parsed['width'],parsed['height'])==(width,height),
         'COMPOSITOR_DIMENSIONS_'+key)
    digest=parsed['sha256']
    need(digest not in digests,'DUPLICATE_FRAME_'+key)
    digests.add(digest);images[key]=parsed
 body=(root/'logs/full/baseline-dao-light.txt').read_text()
 need('OK (9 tests)' in body and 'FAILURES!!!' not in body,'BASELINE_DAO')
 total+=9
 for method in WORKER_METHODS:
  s=(root/'logs/full'/f'worker-{method}-light.txt').read_text()
  need('OK (1 test)' in s and 'FAILURES!!!' not in s,'WORKER_'+method)
  total+=1
 need(total==76 and len(images)==20 and len(digests)==20,'INVENTORY')
 return {'schema':1,'result':RESULT,'source_sha':source,'run_id':str(run),
  'android_api':36,'abi':'x86_64','tests_executed':total,
  'screenshots_count':len(images),'screenshots':images,
  'viewports':PROFILES,'themes':list(MODES),
  'production_room_dao_executions':41,'production_worker_executions':3,
  'real_compose_download_ui_executions':32,
  'installer_decline_policy_qualified':True,'installed_apk_prompt_decline_qualified':False,
  'production_downloads_external_network_qualified':False,
  'real_installer_qualified':False,'real_account_qualified':False,
  'physical_arm64_qualified':False,'full_upstream_visual_signoff':False,
  'release_qualified':False,
  'p14_p01_p02_frozen_sha':'6e9418baaefadd4afcf4320b4a4b193546e66ec7',
  'p14_p01_p02_frozen_run':43665032046,
 }
def main():
 p=argparse.ArgumentParser()
 p.add_argument('--root',type=Path,required=True)
 p.add_argument('--source',required=True)
 p.add_argument('--run',required=True)
 p.add_argument('--out',type=Path,required=True)
 a=p.parse_args()
 a.out.write_text(json.dumps(validate(a.root,a.source,a.run),indent=2,sort_keys=True)+'\n')
 print('P14P03_HOSTED_76_TESTS_20_PNGS_PASS_P15_PENDING')
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,KeyError,TypeError) as e:
  print(str(e),file=sys.stderr);raise SystemExit(2)
