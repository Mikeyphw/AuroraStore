#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Aurora R4 P10: verify P09 hosted evidence without qualifying a release.

All inputs are checked-in, source-bound evidence bytes; never contacts GitHub.
The archived receipt was produced by the hosted P09 Android emulator. This
script checks its exact identity and internal invariants; it does NOT re-run
emulator tests, independently authenticate GitHub or infer manual visual fidelity.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

P09='ecb9c4db5d347f5073ceacc4ef0555f9d6e52608'
P10_SOURCE_CHECKPOINT='a21f81a03ea618dcd2fe97d3725343f81449b715'
R3D='4afa0a40815da035547d7b62460d56bc6d0e26bc'
AUTHOR='8ff1cbc8d252cee26507372b8ead59d72872c9da'
MERGE='340ecef9ffd8235a6e721ca37604fc380728fbf4'
REPO='Mikeyphw/AuroraStore'
WORKFLOW=Path('.github/workflows/aurora-r4-p05-device-ux.yml')
STATUS=Path('docs/r4/R4_P10_INTEGRATION_STATUS.json')
RECEIPT=Path('docs/r4/evidence/R4_P09_HF22_DEVICE_RECEIPT.json')
PROVENANCE=Path('docs/r4/evidence/R4_P09_HF22_APK_PROVENANCE.json')
EXPECTED_HASHES={
 'device_receipt':'29b60e58fcbd6f28a5122248c4e1f7b15f96410c20ef77afca01bc290f01173c',
 'apk_provenance':'c783f43516b7cf38de5fa17118acabdcc48a15843d8a4488b125f72059c7b7c8',
}
RUN='43498499144'
SUITES={
 'download-dao-cancellation':9,'real-offline-worker':8,
 'download-ui-cancellation':4,'r4-offline-account-session':9,
 'r4-expressive-light':5,'r4-expressive-dark':5,
 'r4-activity-light':6,'r4-activity-dark':6,
}
SCREENS={
 'r4_update_downloading.png','r4_update_idle.png','r4_update_verifying.png',
 'r4_update_installing.png','r4_expressive_menu.png',
 'r4_activity_settings.png','r4_activity_ui_preferences.png',
 'r4_activity_more_sheet.png','r4_activity_main.png','r4_activity_search.png',
 'r4_activity_downloads.png','r4_activity_updates.png',
}
SCREEN_KEYS={'%s/%s'%(mode,name) for mode in ('light','dark') for name in SCREENS}
SCREEN_KEYS.add('light/r4_real_app_launch.png')
FALSE_FLAGS=('original_author_visual_fidelity_approved','real_google_account_login_qualified',
 'spoof_restart_ui_behavior_qualified','physical_arm64_qualified',
 'live_google_play_qualified','real_installer_qualified','production_signing_qualified',
 'release_qualified','automatic_merge_allowed')

class Refused(RuntimeError):pass

def need(ok,why):
 if not ok:raise Refused('R4_P10_REFUSED_'+why)

def sha(b:bytes):return hashlib.sha256(b).hexdigest()

def git(root,*cmd):
 p=subprocess.run(['git',*cmd],cwd=root,capture_output=True,text=True)
 need(p.returncode==0,'GIT_'+cmd[0]+'_'+p.stderr[-150:])
 return p.stdout.strip()

def read_json(root,path):
 p=root/path
 need(p.is_file() and not p.is_symlink() and p.stat().st_size<=128000,'MISSING_OR_OVERSIZED_'+path.name)
 return p.read_bytes(),json.loads(p.read_text(encoding='utf-8'))

def check_evidence(status:dict,receipt:dict,apk:dict,rawreceipt:bytes,rawapk:bytes):
 need(isinstance(status,dict) and status.get('schema')==1 and status.get('kind')=='aurora-r4-p10-hosted-integration-review','STATUS_IDENTITY')
 for field,expected in {
  'repository':REPO,'draft_pr':2,'parent_source_sha':P09,
  'upstream_author_sha':AUTHOR,'genuine_merge_sha':MERGE,'r3d_base_sha':R3D,
  'p09_targeted_ci_run':43498509688,'p09_api36_emulator_run':43498499144,
  'p09_targeted_ci_conclusion':'success','p09_api36_emulator_conclusion':'success',
  'p09_instrumentation_executions':52,'p09_nonblank_unique_screenshots':25,
  'p09_offline_account_preference_executions':9,
  'reviewed_retained_r3d_compose_files':19,'retained_followup_source_files':2,
  'integration_status':'HOSTED_OFFLINE_ACCEPTANCE_PASSED_RELEASE_NOT_QUALIFIED',
  'offline_synthetic_fixtures_only':True,'physical_and_live_play_qualification_deferred_by_user':True,
  'manual_visual_review_still_required':True,'source_gate_required':True,
  'full_emulator_gate_required':True,'no_production_source_changes_in_p10':True,
 }.items():need(status.get(field)==expected,'STATUS_FIELD_'+field)
 for k in FALSE_FLAGS:need(status.get(k) is False,'FABRICATED_QUALIFICATION_'+k)
 need(status.get('evidence_paths')=={'device_receipt':str(RECEIPT),'apk_provenance':str(PROVENANCE)},'EVIDENCE_PATHS')
 need(status.get('evidence_sha256')==EXPECTED_HASHES,'STATUS_EVIDENCE_PINS')
 need(sha(rawreceipt)==EXPECTED_HASHES['device_receipt'],'P09_RECEIPT_SHA256')
 need(sha(rawapk)==EXPECTED_HASHES['apk_provenance'],'P09_APK_PROVENANCE_SHA256')
 need(receipt.get('result')=='PASS_DEVICE_TESTS_AND_NONBLANK_UNIQUE_CAPTURE' and
      receipt.get('source_sha')==P09 and receipt.get('run_id')==RUN and
      receipt.get('api_level')==36 and receipt.get('architecture')=='x86_64' and
      receipt.get('hosted_emulator_only') is True and receipt.get('offline_fixtures_only') is True,
      'P09_DEVICE_SOURCE_CONTEXT')
 need(receipt.get('real_device_tests')==52 and receipt.get('suite_counts')==SUITES and
      receipt.get('offline_synthetic_account_preference_tests')==9,
      'P09_EXACT_DEVICE_TEST_INVENTORY')
 shots=receipt.get('screenshots')
 need(isinstance(shots,dict) and set(shots)==SCREEN_KEYS and len(shots)==25,
      'P09_EXACT_25_SCREENSHOT_PATHS')
 hashes=[]
 for name,metadata in shots.items():
  need(isinstance(metadata,dict) and re.fullmatch('[a-f0-9]{64}',metadata.get('sha256','')) is not None,
       'SCREENSHOT_HASH_'+name)
  hashes.append(metadata['sha256'])
  need(metadata.get('width',0)>=320 and metadata.get('height',0)>=480 and
       metadata.get('non_background_samples',0)>=42 and metadata.get('sampled_colors',0)>=8,
       'SCREENSHOT_CONTENT_'+name)
 need(len(set(hashes))==25,'SCREENSHOT_HASH_REUSE')
 for flag in ('screenshots_nonblank_validated','screenshots_unique_validated',
              'expressive_popup_theme_canvas_validated','main_more_to_settings_navigation_tested',
              'full_app_navigation_qualified','physical_and_live_play_qualification_deferred'):
  need(receipt.get(flag) is True,'P09_DEVICE_FLAG_'+flag)
 for flag in ('release_qualified','physical_arm64_qualified','real_google_account_login_qualified',
              'spoof_restart_ui_behavior_qualified','external_google_play_update_verified',
              'real_installer_update_verified','visual_manual_approved'):
  need(receipt.get(flag) is False,'P09_DEVICE_FALSE_FLAG_'+flag)
 need(apk.get('overall')=='PASS' and apk.get('role')=='APK_INPUT_PROVENANCE_ONLY' and
      apk.get('source_sha')==P09 and apk.get('run_id')==RUN and
      apk.get('mode') in ('INDEPENDENT_HOSTED_BUILD','EXACT_TARGETED_ARTIFACT'),
      'APK_PROVENANCE_SOURCE')
 pair=apk.get('apk_pair')
 need(isinstance(pair,dict) and set(pair)=={'app','androidTest'},'APK_ROLE_SET')
 for role,pack in (('app','com.aurora.store.debug'),('androidTest','com.aurora.store.debug.test')):
  obj=pair[role]
  need(obj.get('package')==pack and re.fullmatch('[a-f0-9]{64}',obj.get('sha256','')) and
       re.fullmatch('[a-f0-9]{64}',obj.get('signer_sha256','')) and obj.get('size',0)>10000,
       'APK_'+role+'_IDENTITY')
 need(pair['app']['sha256']!=pair['androidTest']['sha256'],'IDENTICAL_APK_ROLES')
 for flag in ('release_qualified','physical_device_qualified','publisher_authenticated','installation_qualified',
              'instrumentation_qualified'):
  need(apk.get(flag) is False,'APK_UNSUPPORTED_CLAIM_'+flag)
 return {'p09_source_sha':P09,'device_tests':52,'screenshots':25,'hosted_only':True,
         'manual_visual_approved':False,'release_qualified':False,'physical_arm64_qualified':False}

def check_workflow(content:str):
 require=[
 'python3 -B scripts/ci/test_r4_p10_readiness_gate.py',
 'python3 -B scripts/ci/r4_p10_readiness_gate.py --repo .',
 'python3 -B scripts/ci/test_r4_p09_session_source_contract.py',
 'python3 -B scripts/ci/r4_p09_session_source_contract.py --root .',
 'python3 -B scripts/ci/r4_p08_retained_decisions.py --repo .',
 'python3 -B scripts/ci/r4_p07_source_parity.py --repo .',
 'bash scripts/ci/r4_p05_emulator_acceptance.sh',
 'scripts/ci/r4_p06_apk_reuse.py probe',
 'scripts/ci/r4_p06_apk_reuse.py finalize',
 ]
 for item in require:need(content.count(item)==1,'WORKFLOW_INVOCATION_'+item)
 # Only actual YAML permission declarations count; comments, Python string
 # literals and source validation assertions must not trigger false positives.
 perms=re.findall(r'^  (actions|contents):\s*(read|write)\b',content,re.M)
 need(sorted(perms)==[('actions','read'),('contents','read')],'WORKFLOW_PERMISSION_ESCALATION')
 need('on:\n  push:\n' in content and '  workflow_dispatch:\n' in content,
      'WORKFLOW_TRIGGERS_REMOVED')
 need('cancel-in-progress: true' in content and
      'if: always()' in content and 'if-no-files-found: warn' in content,
      'WORKFLOW_CONCURRENCY_OR_RECEIPT_REMOVED')
 return True

def verify(root:Path):
 root=root.resolve(strict=True)
 current=git(root,'rev-parse','HEAD')
 need(bool(re.fullmatch('[a-f0-9]{40}',current)),'INVALID_HEAD')
 need(subprocess.run(['git','merge-base','--is-ancestor',P09,current],cwd=root).returncode==0,
      'P09_NOT_ANCESTOR')
 need(git(root,'rev-list','--parents','-n','1',MERGE).split()==[MERGE,R3D,AUTHOR],
      'AUTHOR_MERGE_PARENTS_CHANGED')
 # P10 is docs/source contract only: actual production or Android test changes
 # require new device evidence rather than inheriting the P09 success receipt.
 for prefix in (
  'app/src/main/','app/src/androidTest/','app/src/test/',
  'scripts/ci/r4_p05_emulator_acceptance.sh',
  'scripts/ci/r4_p05_screenshot_audit.py',
  'scripts/ci/r4_p06_apk_reuse.py',
  'scripts/ci/r4_p07_source_parity.py',
  'scripts/ci/r4_p08_retained_decisions.py',
  'scripts/ci/r4_p09_session_source_contract.py',
  'scripts/ci/test_r4_p09_session_source_contract.py',
  'scripts/ci/r3c07_hf03_apk_pair.py',
  '.github/workflows/aurora-targeted.yml',
  'gradle/libs.versions.toml', 'app/build.gradle.kts',
 ):
  # P10 certifies only its own frozen source snapshot; newer changes are
  # constrained by the downstream P11/P12 guards and fresh hosted emulator.
  need(not git(root,'diff','--name-only',P09,P10_SOURCE_CHECKPOINT,'--',prefix),
       'UNTESTED_POST_P09_APP_CHANGE_'+prefix)
 # Existing P08 and P09 audits preserve the genuine author/R3D decisions
 # and the nine live emulator account test source contracts respectively.
 import r4_p08_retained_decisions as retained
 import r4_p09_session_source_contract as account
 retained.verify(root)
 account.check(account.load(root))
 rr,r=read_json(root,RECEIPT)
 pp,p=read_json(root,PROVENANCE)
 _,status=read_json(root,STATUS)
 check_workflow((root/WORKFLOW).read_text(encoding='utf-8'))
 return check_evidence(status,r,p,rr,pp)

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--repo',type=Path,default=Path('.'))
 parser.add_argument('--out',type=Path)
 args=parser.parse_args()
 doc=verify(args.repo)
 if args.out:
  need(not args.out.exists(),'EXISTING_RECEIPT')
  args.out.parent.mkdir(parents=True,exist_ok=True)
  args.out.write_text(json.dumps(doc,sort_keys=True,indent=2)+'\n')
 print('R4_P10_GENUINE_AUTHOR_R3D_P08_P09_SOURCE_CONTRACTS_PASS')
 print('R4_P10_P09_EXACT_52_TESTS_25_UNIQUE_SCREENSHOTS_SIGNED_APK_PROVENANCE_PASS')
 print('R4_P10_HOSTED_INTEGRATION_ACCEPTED_REAL_WORLD_AND_RELEASE_UNQUALIFIED')

if __name__=='__main__':
 try:main()
 except (Refused,KeyError,TypeError,ValueError,OSError) as e:
  print(str(e),file=sys.stderr)
  sys.exit(2)
