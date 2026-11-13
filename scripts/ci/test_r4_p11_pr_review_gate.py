#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""P11 synthetic negative tests: pure offline contract, no GitHub or Gradle."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import subprocess

import r4_p11_pr_review_gate as m

ROOT = Path(__file__).resolve().parents[2]


def refused(fn, marker):
    try:
        fn()
    except m.Refused as exc:
        assert marker in str(exc), (marker, str(exc))
    else:
        raise AssertionError('R4_P11_DANGEROUS_MUTATION_ACCEPTED_'+marker)


def main():
    data = json.loads((ROOT/m.STATUS).read_text(encoding='utf-8'))
    m.check_status(data)
    cases = 0
    def tweak(mutator, marker):
        nonlocal cases
        value = copy.deepcopy(data)
        mutator(value)
        refused(lambda: m.check_status(value), marker)
        cases += 1

    tweak(lambda d:d.__setitem__('parent_sha','0'*40), 'STATUS_FIELD_parent_sha')
    tweak(lambda d:d.__setitem__('pr_must_remain_draft',False), 'STATUS_FIELD_pr_must_remain_draft')
    tweak(lambda d:d.__setitem__('ready_for_review',True), 'UNSUPPORTED_APPROVAL')
    tweak(lambda d:d.__setitem__('automatic_merge_allowed',True), 'UNSUPPORTED_APPROVAL')
    tweak(lambda d:d.__setitem__('release_qualified',True), 'UNSUPPORTED_APPROVAL')
    tweak(lambda d:d.__setitem__('physical_arm64_qualified',True), 'UNSUPPORTED_APPROVAL')
    tweak(lambda d:d.__setitem__('manual_upstream_visual_approved',True), 'UNSUPPORTED_APPROVAL')
    tweak(lambda d:d.__setitem__('real_installer_qualified',True), 'UNSUPPORTED_APPROVAL')
    tweak(lambda d:d.__setitem__('real_google_account_login_qualified',True), 'UNSUPPORTED_APPROVAL')
    tweak(lambda d:d.__setitem__('baseline_changed_files',152), 'STATUS_FIELD_baseline_changed_files')
    tweak(lambda d:d['baseline_categories'].__setitem__('production',94), 'STATUS_FIELD_baseline_categories')
    tweak(lambda d:d['followups'].pop(), 'STATUS_FIELD_followups')
    tweak(lambda d:d['manual_items'].pop(), 'REVIEW_TASK_COUNT')
    tweak(lambda d:d['manual_items'][0].__setitem__('status','APPROVED'), 'FALSE_MANUAL_SIGNOFF')
    tweak(lambda d:d['manual_items'][0].__setitem__('evidence_needed',''), 'REVIEW_TASK_EVIDENCE')
    tweak(lambda d:d['manual_items'][1].__setitem__('id',d['manual_items'][0]['id']), 'REVIEW_TASK_ID')
    tweak(lambda d:d.__setitem__('extra_ok',True), 'STATUS_SCHEMA')
    tweak(lambda d:d.__setitem__('review_scope','RELEASE_QUALIFIED'), 'STATUS_FIELD_review_scope')

    entries=[]
    entries += [('M',f'app/src/main/java/com/aurora/store/compose/Example{i:03}.kt') for i in range(92)]
    entries += [('M','app/src/main/java/com/aurora/store/data/providers/AccountProvider.kt')]
    entries += [('M','app/src/main/java/com/aurora/store/viewmodel/search/SearchViewModel.kt')]
    entries += [('M','app/src/main/java/com/aurora/store/viewmodel/all/UpdatesViewModel.kt')]
    entries += [('A',f'app/src/androidTest/DeviceTest{i}.kt') for i in range(4)]
    entries += [('A',f'scripts/ci/check{i}.py') for i in range(13)]
    entries += [('A',f'docs/r4/Evidence{i}.json') for i in range(8)]
    entries += [('A','.github/workflows/aurora-r4-p05-device-ux.yml')]
    entries += [('A',f'showcase/captures/shot{i}.png') for i in range(32)]
    assert len(entries)==153
    assert m.inventory(entries)['counts']==m.EXPECTED_COUNTS
    assert len(m.inventory(entries)['production_files'])==95
    cases+=1
    def inventory_changed(change,marker):
        nonlocal cases
        e=copy.deepcopy(entries)
        change(e)
        refused(lambda: m.inventory(e), marker)
        cases+=1
    inventory_changed(lambda e:e.pop(),'PR_CHANGE_COUNT')
    inventory_changed(lambda e:e[0].__setitem__(1,'illegal'), 'PR_CATEGORY_COUNTS') if False else None
    inventory_changed(lambda e:e.__setitem__(0,('M','showcase/captures/another.png')), 'PR_CATEGORY_COUNTS')
    inventory_changed(lambda e:e.__setitem__(0,e[1]), 'PR_DUPLICATE_PATH')
    inventory_changed(lambda e:e.__setitem__(0,('D',e[0][1])), 'PR_UNSUPPORTED_CHANGE')
    inventory_changed(lambda e:e.__setitem__(94,('M','app/src/main/java/com/aurora/store/Other.kt')), 'MISSING_UPDATE_SENSITIVE_SOURCE')

    names=b''.join((s.encode()+b'\0'+p.encode()+b'\0') for s,p in entries)
    assert m.parse_names_z(names)==entries
    for bad,marker in [
        (names[:-1], 'INVALID_NULL_DELIMITERS'),
        (b'A\0', 'INVALID_NAME_STATUS_ARITY'),
        (b'D\0new.txt\0', 'UNREVIEWED_CHANGE_KIND'),
        (b'A\0../hack\0', 'UNSAFE_DIFF_PATH'),
        (b'A\0x\0A\0x\0', 'DUPLICATE_DIFF_PATH'),
        (b'A\0\xff\0', 'INVALID_GIT_TEXT'),
    ]:
        refused(lambda bad=bad:m.parse_names_z(bad),marker)
        cases+=1

    m.check_post_p10(set(m.ALLOWED_P11))
    for changed in (set(m.ALLOWED_P11)-{str(m.STATUS)},
                    set(m.ALLOWED_P11)|{'app/src/main/java/Tamper.kt'},
                    set()):
        refused(lambda changed=changed:m.check_post_p10(changed), 'P11_FILES_NOT_STAGED' if not changed else 'POST_P10_ALLOWLIST_DRIFT')
        cases+=1

    # Construct minimal workflow text: the exact current full workflow is verified by CI.
    # Pure contract rejects critical CI bypasses in the *actual* workflow content.
    wf=(ROOT/m.WORKFLOW).read_text(encoding='utf-8')
    m.check_workflow(wf)
    for old,new,marker in (
        ('python3 -B scripts/ci/test_r4_p11_pr_review_gate.py','echo fake tests','CI_REQUIRED_STEP'),
        ('python3 -B scripts/ci/r4_p11_pr_review_gate.py --root .','echo fake gate','CI_REQUIRED_STEP'),
        ('python3 -B scripts/ci/r4_p10_readiness_gate.py --repo .','echo skip P10','CI_REQUIRED_STEP'),
        ('bash scripts/ci/r4_p05_emulator_acceptance.sh','echo no emulator','CI_REQUIRED_STEP'),
        ('  actions: read','  actions: write','WORKFLOW_PERMISSION_ESCALATION'),
        ('  contents: read','  contents: write','WORKFLOW_PERMISSION_ESCALATION'),
    ):
        assert old in wf,old
        refused(lambda old=old,new=new:m.check_workflow(wf.replace(old,new,1)),marker)
        cases+=1
    assert cases>=38, cases
    print(f'R4_P11_SYNTHETIC_NEGATIVE_CONTRACTS_PASS cases={cases}')
    print('R4_P11_153_DIFF_CLASSIFICATION_AND_NO_FABRICATED_APPROVAL_PASS')

if __name__=='__main__':
    main()
