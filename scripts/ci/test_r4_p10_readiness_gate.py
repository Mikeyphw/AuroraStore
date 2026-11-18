#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""P10 adversarial evidence/CI tests. No Android/Play operations."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import r4_p10_readiness_gate as m
ROOT=Path(__file__).resolve().parents[2]

def refuse(fn,code):
 try:fn()
 except m.Refused as exc:assert code in str(exc),(code,str(exc))
 else:raise AssertionError('R4_P10_NEGATIVE_NOT_REFUSED_'+code)

def main():
 statusbytes=(ROOT/m.STATUS).read_bytes()
 rr=(ROOT/m.RECEIPT).read_bytes()
 pp=(ROOT/m.PROVENANCE).read_bytes()
 status=json.loads(statusbytes);receipt=json.loads(rr);apk=json.loads(pp)
 got=m.check_evidence(status,receipt,apk,rr,pp)
 assert got['device_tests']==52 and got['screenshots']==25
 assert got['release_qualified'] is False
 wf=(ROOT/m.WORKFLOW).read_text()
 m.check_workflow(wf)
 cases=0
 def corrupt(field,new,code):
  nonlocal cases
  s=copy.deepcopy(status);s[field]=new
  refuse(lambda:m.check_evidence(s,receipt,apk,rr,pp),code);cases+=1
 corrupt('parent_source_sha','0'*40,'STATUS_FIELD_parent_source_sha')
 corrupt('p09_api36_emulator_conclusion','failure','STATUS_FIELD_p09_api36_emulator_conclusion')
 corrupt('p09_instrumentation_executions',43,'STATUS_FIELD_p09_instrumentation_executions')
 corrupt('original_author_visual_fidelity_approved',True,'FABRICATED_QUALIFICATION')
 corrupt('physical_arm64_qualified',True,'FABRICATED_QUALIFICATION')
 corrupt('automatic_merge_allowed',True,'FABRICATED_QUALIFICATION')
 corrupt('release_qualified',True,'FABRICATED_QUALIFICATION')
 corrupt('live_google_play_qualified',True,'FABRICATED_QUALIFICATION')
 corrupt('physical_and_live_play_qualification_deferred_by_user',False,'STATUS_FIELD')
 corrupt('evidence_sha256',{},'STATUS_EVIDENCE_PINS')
 # Raw receipt must match pinned digest, not merely match manipulated parsed data.
 refuse(lambda:m.check_evidence(status,receipt,apk,rr+b' ',pp),'P09_RECEIPT_SHA256');cases+=1
 refuse(lambda:m.check_evidence(status,receipt,apk,rr,pp+b' '),'P09_APK_PROVENANCE_SHA256');cases+=1
 def edited_receipt(change,code):
  nonlocal cases
  r=copy.deepcopy(receipt);change(r)
  refuse(lambda:m.check_evidence(status,r,apk,rr,pp),code);cases+=1
 edited_receipt(lambda r:r.update(real_device_tests=51),'P09_EXACT_DEVICE_TEST_INVENTORY')
 edited_receipt(lambda r:r['suite_counts'].update({'r4-offline-account-session':8}),
                'P09_EXACT_DEVICE_TEST_INVENTORY')
 edited_receipt(lambda r:r['screenshots'].pop('light/r4_activity_more_sheet.png'),
                'P09_EXACT_25_SCREENSHOT_PATHS')
 edited_receipt(lambda r:r['screenshots']['light/r4_update_idle.png'].update(sha256='bad'),
                'SCREENSHOT_HASH')
 edited_receipt(lambda r:r['screenshots']['light/r4_update_idle.png'].update(non_background_samples=0),
                'SCREENSHOT_CONTENT')
 edited_receipt(lambda r:r['screenshots']['light/r4_update_idle.png'].update(sha256=r['screenshots']['light/r4_update_verifying.png']['sha256']),
                'SCREENSHOT_HASH_REUSE')
 edited_receipt(lambda r:r.update(real_google_account_login_qualified=True),'P09_DEVICE_FALSE_FLAG')
 def edited_apk(change,code):
  nonlocal cases
  a=copy.deepcopy(apk);change(a)
  refuse(lambda:m.check_evidence(status,receipt,a,rr,pp),code);cases+=1
 edited_apk(lambda a:a.update(source_sha='f'*40),'APK_PROVENANCE_SOURCE')
 edited_apk(lambda a:a['apk_pair']['app'].update(package='com.invalid.app'),'APK_app_IDENTITY')
 edited_apk(lambda a:a.update(release_qualified=True),'APK_UNSUPPORTED_CLAIM')
 # Workflow gate must not accept any permission escalation or skipped checks.
 for old,new,code in [
  ('  actions: read','  actions: write','WORKFLOW_PERMISSION_ESCALATION'),
  ('  contents: read','  contents: write','WORKFLOW_PERMISSION_ESCALATION'),
  ('python3 -B scripts/ci/r4_p10_readiness_gate.py --repo .','echo bypass','WORKFLOW_INVOCATION'),
  ('bash scripts/ci/r4_p05_emulator_acceptance.sh','echo skip tests','WORKFLOW_INVOCATION'),
  ('scripts/ci/r4_p06_apk_reuse.py finalize','echo forged provenance','WORKFLOW_INVOCATION'),
 ]:
  assert old in wf
  refuse(lambda old=old,new=new:m.check_workflow(wf.replace(old,new,1)),code);cases+=1
 assert cases==27,cases
 print('R4_P10_P09_HOSTED_EVIDENCE_27_ADVERSARIAL_MUTATIONS_REFUSED_PASS')
 print('R4_P10_SOURCE_WORKFLOW_REVIEW_CONTRACTS_PASS')

if __name__=='__main__':main()
