#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Requalify integration, preserving original source reviews at their exact commits.

Historical checks are executed from an isolated detached Git worktree; they never
constitute acceptance of the integrated tree. Current checks exercise the live
source and workflow wiring, and hosted jobs must produce fresh evidence.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

BRANCH = 'feature/aurora-consolidated-integration-20261125'
INPUTS = {
    'master': '12840634f1a812c613eda49dff5abeeb6e02cc25',
    'r3d': '4afa0a40815da035547d7b62460d56bc6d0e26bc',
    'p05': '596dc4b679f93c83a3375191a74b03f08da3bf35',
    'p13': '47c360e9cb553f73fb6858cd364ea19835bada6e',
    'p14': '6e9418baaefadd4afcf4320b4a4b193546e66ec7',
    'p14p03': '64f92015871670c3f9032d682e6154d5dae57bbc',
    'p15': 'bd373314917089bed85105d1e5266d2859728a38',
}
LANES = {
    'p05': ('p05-device-ux', 'check_aur_int01.py --lane p05'),
    'p13': ('p13b-integrated', 'r4_p13b_source_contract.py --root . --integration'),
    'p14': ('p14-p01-journeys', 'r4_p14_p01_source_contract.py --root . --integration'),
    'p14p03': ('p14-p03-lifecycle', 'r4_p14_p03_source_contract.py --root . --integration'),
    'p15': ('p15-apks', 'r4_p15_source_contract.py --root . --integration'),
}
HISTORICAL = {
    'p05': [('r4_p07_source_parity','--repo'),('r4_p08_retained_decisions','--repo'),
            ('r4_p10_readiness_gate','--repo'),('r4_p11_pr_review_gate','--root'),
            ('r4_p12_visual_contrast_gate','--root')],
    'p13': [('r4_p13b_source_contract','--root')],
    'p14': [('r4_p14_p01_source_contract','--root')],
    'p14p03': [('r4_p14_p03_source_contract','--root')],
    'p15': [('r4_p15_source_contract','--root')],
}

def git(root, *args):
    return subprocess.check_output(['git', '-c', 'core.hooksPath=/dev/null', *args],
                                   cwd=root, text=True, timeout=90).strip()

def need(ok, why):
    if not ok:
        raise ValueError('AUR_INT01_REFUSED_' + why)

def run(root, script, *args):
    subprocess.run([sys.executable, '-B', 'scripts/ci/' + script + '.py', *args],
                   cwd=root, check=True, timeout=240)

def historical(root, lane):
    with tempfile.TemporaryDirectory(prefix='aur-int01-history-') as tmp:
        old = Path(tmp)/'checkout'
        git(root, 'worktree', 'add', '--detach', str(old), INPUTS[lane])
        try:
            need(git(old, 'rev-parse', 'HEAD') == INPUTS[lane], 'HISTORY_CHECKOUT')
            for script, option in HISTORICAL[lane]:
                run(old, 'test_' + script)
                run(old, script, option, '.')
        finally:
            git(root, 'worktree', 'remove', '--force', str(old))
    print('AUR_INT01_HISTORICAL_SOURCE_REPLAY_PASS', lane, INPUTS[lane], flush=True)

def current(root, lane):
    def text(path): return (root/path).read_text(encoding='utf-8')
    wf, invocation = LANES[lane]
    workflow = text('.github/workflows/aurora-r4-'+wf+'.yml')
    need('      - '+BRANCH+'\n' in workflow and 'python3 -B scripts/ci/'+invocation in workflow,
         'INTEGRATION_WORKFLOW_'+lane)
    if lane == 'p05':
        import r4_p12_visual_contrast_gate as m
        import r4_p09_session_source_contract as session
        session.check(session.load(root))
        m.check_populated_test(text(m.POPULATED_TEST))
        m.check_pixel_source(text(m.PIXEL_AUDIT),text(m.PIXEL_TESTS))
        m.check_status(json.loads(text(m.STATUS)))
    elif lane == 'p13':
        import r4_p13b_source_contract as m
        m.check_test(text(m.TEST)); m.check_nav(text(m.NAV_TEST)); m.check_runner(text(m.RUNNER))
        m.check_audit(text(m.AUDIT)); m.check_signoff(text(m.SIGNOFF))
        m.check_references(json.loads(text(m.REFERENCES))); m.check_workflow(workflow)
    elif lane == 'p14':
        import r4_p14_p01_source_contract as m
        m.source_checks(root)
    elif lane == 'p14p03':
        import r4_p14_p03_source_contract as m
        m.source_only(root)
    elif lane == 'p15':
        import r4_p15_source_contract as m
        m.source_only(root)
    print('AUR_INT01_CURRENT_SOURCE_PASS', lane, flush=True)

def verify(root, lane):
    root=Path(root).resolve(strict=True)
    need(not git(root,'status','--porcelain'), 'DIRTY_TREE')
    head=git(root,'rev-parse','HEAD')
    for name,sha in INPUTS.items():
        need(git(root,'merge-base',sha,head)==sha,'INPUT_NOT_ANCESTOR_'+name)
    # Do not allow new integrated code to overwrite historical review records.
    evidence='docs/r4/evidence'
    need(not git(root,'diff','--name-only',INPUTS['p15'],head,'--',evidence), 'HISTORICAL_EVIDENCE_DRIFT')
    git(root,'diff','--check',INPUTS['master'],head)
    run(root,'test_aur_int01_room')
    historical(root,lane)
    current(root,lane)
    print('AUR_INT01_LANE_SOURCE_PASS', lane, head, 'HOSTED_ACCEPTANCE_PENDING', flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',default='.',type=Path)
    p.add_argument('--lane',required=True,choices=LANES)
    a=p.parse_args()
    verify(a.root,a.lane)
