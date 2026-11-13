#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Aurora R4 P11: exact-Git-tree PR source inventory and honest review staging.

Offline CI check. This inventories Git objects, not live API/UX behavior.
It neither contacts GitHub nor changes a PR's draft/merge/release state.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

REPO = 'Mikeyphw/AuroraStore'
PR = 2
BRANCH = 'feature/r4-p03-pr113-expressive-v4-20261113'
BASE = '4afa0a40815da035547d7b62460d56bc6d0e26bc'
P09 = 'ecb9c4db5d347f5073ceacc4ef0555f9d6e52608'
P10 = 'a21f81a03ea618dcd2fe97d3725343f81449b715'
AUTHOR = '8ff1cbc8d252cee26507372b8ead59d72872c9da'
MERGE = '340ecef9ffd8235a6e721ca37604fc380728fbf4'
STATUS = Path('docs/r4/R4_P11_PR_REVIEW_STATUS.json')
WORKFLOW = Path('.github/workflows/aurora-r4-p05-device-ux.yml')
ALLOWED_P11 = frozenset({
    '.github/workflows/aurora-r4-p05-device-ux.yml',
    'docs/r4/R4_P11_PR_REVIEW_CHECKLIST.md',
    str(STATUS),
    'scripts/ci/r4_p11_pr_review_gate.py',
    'scripts/ci/test_r4_p11_pr_review_gate.py',
})
EXPECTED_COUNTS = {
    'production': 95, 'instrumentation': 4, 'ci': 13,
    'docs': 8, 'workflow': 1, 'other': 32,
}
PENDING_IDS = frozenset({
    'original_author_pixel_fidelity', 'retained_r3d_behavior',
    'live_google_account_and_switching', 'spoof_restart_runtime',
    'physical_arm64', 'actual_install_update', 'release_signing',
})
FALSE_FLAGS = (
    'ready_for_review', 'automatic_merge_allowed', 'manual_upstream_visual_approved',
    'live_google_play_qualified', 'real_google_account_login_qualified',
    'spoof_restart_ui_qualified', 'physical_arm64_qualified',
    'real_installer_qualified', 'production_signing_qualified', 'release_qualified',
)

class Refused(RuntimeError):
    pass


def need(ok: bool, reason: str) -> None:
    if not ok:
        raise Refused('R4_P11_REFUSED_' + reason)


def git(root: Path, *args: str) -> bytes:
    proc = subprocess.run(['git', *args], cwd=root, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)
    need(proc.returncode == 0, 'GIT_' + args[0] + '_' +
         proc.stderr.decode('utf-8', 'replace')[-180:])
    return proc.stdout


def parse_names_z(data: bytes) -> list[tuple[str, str]]:
    """Git diff --name-status --no-renames -z has status\0path\0 pairs."""
    need(data.endswith(b'\0') if data else True, 'INVALID_NULL_DELIMITERS')
    records = data.split(b'\0')[:-1] if data else []
    need(len(records) % 2 == 0, 'INVALID_NAME_STATUS_ARITY')
    result = []
    for i in range(0, len(records), 2):
        try:
            status = records[i].decode('ascii', 'strict')
            path = records[i + 1].decode('utf-8', 'strict')
        except UnicodeError as exc:
            raise Refused('R4_P11_REFUSED_INVALID_GIT_TEXT') from exc
        need(status in ('A', 'M'), 'UNREVIEWED_CHANGE_KIND_' + status)
        need(path != '' and not path.startswith('/') and
             not any(segment in ('', '.', '..') for segment in path.split('/')) and
             '\\' not in path and '\n' not in path and '\r' not in path,
             'UNSAFE_DIFF_PATH')
        result.append((status, path))
    need(len({path for _, path in result}) == len(result), 'DUPLICATE_DIFF_PATH')
    return result


def category(path: str) -> str:
    if path.startswith('app/src/main/'):
        return 'production'
    if path.startswith('app/src/androidTest/'):
        return 'instrumentation'
    if path.startswith('scripts/ci/'):
        return 'ci'
    if path.startswith('docs/'):
        return 'docs'
    if path.startswith('.github/workflows/'):
        return 'workflow'
    return 'other'


def risk_tag(path: str) -> str:
    # All non-UI Android behavior changes remain manual review, even if CI is green.
    if path.endswith('AccountProvider.kt') or '/viewmodel/' in path or '/data/' in path:
        return 'behavior-sensitive'
    if path.endswith(('ComposeActivity.kt', 'AuroraApp.kt')) or '/navigation/' in path:
        return 'navigation-lifecycle'
    if path.startswith('app/src/main/res/') or path.endswith('baseline-prof.txt'):
        return 'resources-configuration'
    if '/compose/' in path:
        return 'expressive-ui'
    if category(path) == 'production':
        return 'other-production'
    return 'supporting-evidence'


def inventory(entries: list[tuple[str, str]]) -> dict:
    need(len(entries) == 153, 'PR_CHANGE_COUNT_' + str(len(entries)))
    counts = dict(Counter(category(path) for _, path in entries))
    need(counts == EXPECTED_COUNTS, 'PR_CATEGORY_COUNTS_'+repr(counts))
    need(len({p for _, p in entries}) == 153, 'PR_DUPLICATE_PATH')
    need(all(s in ('A', 'M') for s, _ in entries), 'PR_UNSUPPORTED_CHANGE')
    sorted_entries = sorted(entries, key=lambda item: item[1])
    digest = hashlib.sha256(''.join(s+'\t'+p+'\n' for s,p in sorted_entries)
                            .encode('utf-8')).hexdigest()
    production = [
        {'path':p, 'change':s, 'risk':risk_tag(p)}
        for s,p in sorted_entries if category(p) == 'production'
    ]
    risk_counts = dict(Counter(item['risk'] for item in production))
    need(any(x['path'].endswith('AccountProvider.kt') for x in production),
         'MISSING_AUTH_SENSITIVE_SOURCE')
    need(any(x['path'].endswith('SearchViewModel.kt') for x in production),
         'MISSING_SEARCH_SENSITIVE_SOURCE')
    need(any(x['path'].endswith('UpdatesViewModel.kt') for x in production),
         'MISSING_UPDATE_SENSITIVE_SOURCE')
    return {'changed_files':153, 'counts':counts, 'path_status_sha256':digest,
            'production_files':production, 'production_risk_counts':risk_counts}


def check_post_p10(paths: set[str]) -> None:
    need(bool(paths), 'P11_FILES_NOT_STAGED')
    need(paths == ALLOWED_P11,
         'POST_P10_ALLOWLIST_DRIFT_' + ','.join(sorted(paths ^ ALLOWED_P11)))


def check_status(doc: dict) -> None:
    need(isinstance(doc, dict) and set(doc) == {
        'schema','kind','repository','pr_number','pr_must_remain_draft',
        'parent_sha','r3d_base_sha','p09_source_sha','author_sha','merge_sha',
        'phase','review_scope','baseline_changed_files','baseline_categories',
        'followups','manual_items',*FALSE_FLAGS}, 'STATUS_SCHEMA')
    expected = {
        'schema':1,'kind':'aurora-r4-p11-review-staging','repository':REPO,
        'pr_number':PR,'pr_must_remain_draft':True,'parent_sha':P10,
        'r3d_base_sha':BASE,'p09_source_sha':P09,
        'author_sha':AUTHOR,'merge_sha':MERGE,
        'phase':'DRAFT_REVIEW_STAGED_RELEASE_NOT_QUALIFIED',
        'review_scope':'SOURCE_INVENTORY_AND_OFFLINE_HOSTED_EVIDENCE_ONLY',
        'baseline_changed_files':153,'baseline_categories':EXPECTED_COUNTS,
        'followups':[
            'app/src/main/java/com/aurora/store/compose/ui/accounts/GoogleLoginScreen.kt',
            'app/src/main/java/com/aurora/store/compose/ui/spoof/SpoofScreen.kt',
        ],
    }
    for key, expected_value in expected.items():
        need(doc.get(key) == expected_value, 'STATUS_FIELD_'+key)
    for name in FALSE_FLAGS:
        need(doc.get(name) is False, 'UNSUPPORTED_APPROVAL_'+name)
    items = doc.get('manual_items')
    need(isinstance(items, list) and len(items) == len(PENDING_IDS),
         'REVIEW_TASK_COUNT')
    found = set()
    for item in items:
        need(isinstance(item, dict) and set(item) == {'id','status','evidence_needed'},
             'REVIEW_TASK_SCHEMA')
        task = item['id']
        need(isinstance(task, str) and task in PENDING_IDS and task not in found,
             'REVIEW_TASK_ID')
        need(item['status'] in ('PENDING','DEFERRED'), 'FALSE_MANUAL_SIGNOFF_'+task)
        need(isinstance(item['evidence_needed'], str) and len(item['evidence_needed']) >= 30,
             'REVIEW_TASK_EVIDENCE_'+task)
        found.add(task)
    need(found == PENDING_IDS, 'REVIEW_TASK_INVENTORY')


def check_workflow(content: str) -> None:
    for marker in (
        'python3 -B scripts/ci/test_r4_p11_pr_review_gate.py',
        'python3 -B scripts/ci/r4_p11_pr_review_gate.py --root .',
        'python3 -B scripts/ci/test_r4_p10_readiness_gate.py',
        'python3 -B scripts/ci/r4_p10_readiness_gate.py --repo .',
        'bash scripts/ci/r4_p05_emulator_acceptance.sh',
    ):
        need(content.count(marker) == 1, 'CI_REQUIRED_STEP_'+marker)
    perm = re.findall(r'^  (actions|contents):\s*(read|write)\b',content,re.M)
    need(sorted(perm) == [('actions','read'),('contents','read')],
         'WORKFLOW_PERMISSION_ESCALATION')
    need('  push:\n' in content and '  workflow_dispatch:\n' in content and
         'if: always()' in content, 'WORKFLOW_DEVICE_OR_RECEIPT_REMOVED')


def verify(root: Path) -> dict:
    root = root.resolve(strict=True)
    need((root/'.git').exists() or git(root,'rev-parse','--is-inside-work-tree').strip()==b'true',
         'NOT_A_GIT_REPOSITORY')
    head = git(root,'rev-parse','HEAD').decode().strip()
    need(re.fullmatch('[0-9a-f]{40}',head) is not None, 'INVALID_HEAD')
    need(subprocess.run(['git','merge-base','--is-ancestor',P10,head],cwd=root).returncode==0,
         'P10_PARENT_NOT_ANCESTOR')
    need(git(root,'rev-list','--parents','-n','1',MERGE).decode().strip().split()==
         [MERGE,BASE,AUTHOR], 'ORIGINAL_AUTHOR_MERGE_CHANGED')
    need(not git(root,'diff','--name-only','HEAD','--').strip() and
         not git(root,'diff','--cached','--name-only','--').strip(),
         'DIRTY_TRACKED_TREE')
    names = parse_names_z(git(root,'diff','--name-status','--no-renames','-z',BASE,P10))
    report = inventory(names)
    post_p10 = parse_names_z(git(root,'diff','--name-status','--no-renames','-z',P10,head))
    check_post_p10({path for _, path in post_p10})
    # Inherit the full P08/P09/P10 source/evidence verification, not a weaker substitute.
    import r4_p10_readiness_gate as p10
    inherited = p10.verify(root)
    need(inherited['device_tests']==52 and inherited['screenshots']==25 and
         inherited['release_qualified'] is False, 'P10_EVIDENCE_CHAIN_DRIFT')
    path = root/STATUS
    need(path.is_file() and not path.is_symlink() and path.stat().st_size<=20000,
         'MISSING_STATUS')
    check_status(json.loads(path.read_text(encoding='utf-8')))
    check_workflow((root/WORKFLOW).read_text(encoding='utf-8'))
    report.update({
        'schema':1,'kind':'aurora-r4-p11-source-review-receipt',
        'repo':REPO,'pr_number':PR,'audited_head_sha':head,
        'r3d_base_sha':BASE,'p10_pinned_sha':P10,
        'post_p10_paths':sorted({p for _,p in post_p10}),
        'hosted_prior_p09_device_tests':52,'hosted_prior_p09_screenshots':25,
        'manual_items_still_open':sorted(PENDING_IDS),
        'draft_only':True,'ready_for_review':False,'release_qualified':False,
        'physical_arm64_qualified':False,'live_google_play_qualified':False,
    })
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('.'))
    parser.add_argument('--out',type=Path,help='Write a non-overwriting JSON inventory receipt')
    args = parser.parse_args()
    result=verify(args.root)
    if args.out:
        need(not args.out.exists(),'EXISTING_REPORT')
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print('R4_P11_P10_PINNED_GIT_INVENTORY_153_PATHS_95_PRODUCTION_PASS')
    print('R4_P11_P08_P09_P10_OFFLINE_EVIDENCE_AND_REVIEW_GATES_PASS')
    print('R4_P11_DRAFT_REVIEW_STAGED_MANUAL_AND_RELEASE_GATES_UNQUALIFIED')

if __name__=='__main__':
    try:
        main()
    except (Refused,OSError,ValueError,KeyError) as e:
        print(str(e),file=sys.stderr)
        sys.exit(2)
