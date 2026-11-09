#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Aurora CI: targeted PR checks, conservative five-merge gate planning, exact-SHA gate dispatch.

No local Android/Gradle compilation. All heavy work runs in GitHub Actions only.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

INITIAL_GATE_SHA = '6c1de393d0f9df15c4d70b58b0b24e211c480a80'
DEFAULT_INTERVAL = 5
GATE_TAG_PREFIX = 'aurora-full-gate/'

GROUP_TESTS = {
    'download': ['check_r1a.py', 'check_r1b.py', 'check_r1c.py', 'check_r1d.py', 'check_r1d2.py', 'check_r1e.py', 'check_r1f.py', 'check_r1g.py'],
    'installer': ['check_r2a.py', 'check_r2b.py', 'test_r2b_sql_cas.py', 'check_r2c.py', 'check_r2d.py', 'test_r2d_host_contract.py', 'check_r3b.py'],
    'play': ['check_r3.py', 'check_r3c.py', 'check_r3c02.py', 'check_r3c03.py', 'test_r3c03_contract.py', 'check_r3c03_c01.py', 'test_r3c03_c01_sql.py', 'test_r3c03_c01_security.py', 'check_r3c03_c02.py', 'test_r3c03_c02_security.py'],
    'update': ['check_r3.py', 'test_r3a_downgrade_contract.py', 'check_r3b.py'],
    'ui': ['check_r1f.py', 'check_r3c02.py'],
    'artifact': ['check_r3b.py', 'test_r3a_downgrade_contract.py',
                 'check_r3c03_c02.py', 'test_r3c03_c02_security.py'],
}
ALL_TESTS = sorted({'check_foundation.py', 'test_aurora_ci_policy.py'} | {t for ts in GROUP_TESTS.values() for t in ts})
WORKFLOW_SENSITIVE = ('.github/workflows/', 'scripts/ci/aurora_ci_policy.py', 'scripts/ci/test_aurora_ci_policy.py')
RISK_PREFIXES = (
    '.github/workflows/',
    'scripts/ci/aurora_ci_policy.py',
    'scripts/ci/test_aurora_ci_policy.py',
    'app/src/main/java/com/aurora/store/data/installer/verification/',
    'app/src/main/java/com/aurora/store/data/security/',
    'app/src/main/java/com/aurora/store/data/room/MigrationHelper.kt',
    'gradle/wrapper/',
    'app/build.gradle.kts',
    'build.gradle.kts',
    'settings.gradle.kts',
)
EXPECTED_JOBS = {
    'aurora-foundation.yml': {
        'Source and bundle contract',
        'Kotlin formatting — every app source set',
        'Kotlin formatting — root Gradle scripts',
        'Android Lint — vanillaDebug',
        'Android vanilla debug compilation and JVM tests',
        'Compile unsigned vanilla release candidate (not certified)',
    },
    'aurora-r1d-emulator.yml': {
        'R1D source and fixture contract',
        'R1D production Room DAO + watchdog + process restart on API 36',
    },
    'aurora-r2d-install-emulator.yml': {
        'R2C and R2D fail-closed contracts',
        'R2D real APK session, force-stop and Room recovery on API 36',
    },
}


def cmd_git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    p = subprocess.run(['git', *args], cwd=cwd, text=True, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, check=False)
    if check and p.returncode:
        raise RuntimeError(f'CI_POLICY_GIT_REFUSED: {" ".join(args)}: {p.stderr.strip()}')
    return p.stdout.strip()


def paths_between(base: str, head: str, *, cwd: Path | None = None) -> list[str]:
    if not re.fullmatch('[0-9a-f]{40}', head):
        raise ValueError('expected a full 40-character head SHA')
    if not re.fullmatch('[0-9a-f]{40}', base):
        raise ValueError('expected a full 40-character base SHA')
    return sorted(set(filter(None, cmd_git('diff', '--name-only', '--no-renames',
                                          '--diff-filter=ACDMRTUXB', base, head, cwd=cwd).splitlines())))


def classify(paths: list[str], *, present: set[str] | None = None) -> dict:
    groups: set[str] = set()
    sensitive = False
    android = False
    for path in paths:
        if any(path.startswith(p) for p in WORKFLOW_SENSITIVE):
            sensitive = True
        if path.startswith(('app/src/', 'app/schemas/', 'app/build.gradle', 'gradle/',
                            'build.gradle', 'settings.gradle')):
            android = True
        # Room schema changes require hosted KSP compilation and all relevant schema tests.
        if path.startswith('app/schemas/'):
            groups.update(('play', 'installer'))
        # Import tests belong to an independent source; no forged Play classification.
        if ('/data/artifact/' in path or '/data/importer/' in path
                or 'r3c04' in path.lower()):
            groups.add('artifact')
        if path.startswith(('app/src/main/java/com/aurora/store/data/room/download/',
                            'app/src/main/java/com/aurora/store/data/work/',
                            'app/src/main/java/com/aurora/store/data/helper/DownloadHelper.kt',
                            'app/src/androidTest/java/com/aurora/store/data/work/',
                            'app/src/androidTest/java/com/aurora/store/data/room/download/')):
            groups.add('download')
        if '/installer/' in path or 'Install' in path or '/room/Migration' in path:
            groups.add('installer')
        if ('/play/' in path or '/model/Play' in path or 'r3c' in path.lower()
                or 'historical' in path.lower()):
            groups.add('play')
        if ('/update/' in path or 'r3a' in path.lower()):
            groups.add('update')
        if ('/compose/' in path or 'viewmodel/' in path or 'r1f' in path.lower()):
            groups.add('ui')
        if path.startswith('scripts/ci/check_r1'):
            groups.add('download')
        if path.startswith('scripts/ci/check_r2'):
            groups.add('installer')
    tests = {'check_foundation.py', 'test_aurora_ci_policy.py'}
    if sensitive or (android and not groups):
        tests.update(ALL_TESTS)
    else:
        for group in groups:
            tests.update(GROUP_TESTS[group])
    # Optional future checks are added only when the actual source includes them.
    # Never pretend a new test passed merely because a filename was anticipated.
    if present is None:
        present = {p.name for p in (Path(__file__).parent).glob('*.py')}
    if 'play' in groups and 'test_r3c03_c03_schema.py' in present:
        tests.add('test_r3c03_c03_schema.py')
    if 'artifact' in groups:
        tests.update(x for x in present if re.fullmatch(
            r'(?:check|test)_r3c04_[a-z0-9_]+\.py', x
        ))
    # Baseline group contracts remain mandatory; a deleted file must fail at exec.
    return {'groups': sorted(groups) or ['baseline'], 'tests': sorted(tests),
            'needs_android': android, 'ci_sensitive': sensitive, 'changed_files': len(paths)}


def first_parent_commits(head: str, *, cwd: Path | None = None) -> list[str]:
    return cmd_git('rev-list', '--first-parent', head, cwd=cwd).splitlines()


def most_recent_gate(head: str, *, cwd: Path | None = None) -> tuple[str, str]:
    first_parent = first_parent_commits(head, cwd=cwd)
    commits = set(first_parent)
    gates = cmd_git('tag', '--list', f'{GATE_TAG_PREFIX}*', cwd=cwd).splitlines()
    indexed: dict[str, str] = {}
    for tag in gates:
        commit = cmd_git('rev-parse', f'refs/tags/{tag}^{{commit}}', cwd=cwd)
        if commit in commits:
            indexed[commit] = tag
    for commit in first_parent:
        if commit in indexed:
            return commit, indexed[commit]
    if INITIAL_GATE_SHA not in commits:
        raise RuntimeError('CI_GATE_REFUSED: confirmed initial baseline is not first-parent ancestor')
    return INITIAL_GATE_SHA, 'confirmed-initial-full-gate'


def gate_plan(head: str, interval: int, *, cwd: Path | None = None, force: bool = False) -> dict:
    if interval < 1 or interval > 25:
        raise ValueError('Gate interval must be between 1 and 25')
    history = first_parent_commits(head, cwd=cwd)
    anchor, tag = most_recent_gate(head, cwd=cwd)
    units = history.index(anchor)
    changed = paths_between(anchor, head, cwd=cwd)
    risk = sorted(p for p in changed if any(p.startswith(r) for r in RISK_PREFIXES))
    reasons = (['manual-full-gate'] if force else []) + (['cadence'] if units >= interval else []) + (['high-risk-change'] if risk else [])
    return {'head_sha': head, 'baseline_sha': anchor, 'baseline_tag': tag,
            'overlay_units_since_gate': units, 'interval': interval,
            'high_risk_paths': risk, 'due': bool(reasons), 'reasons': reasons,
            'counting_rule': 'one first-parent master commit per unit (conservative for squash/direct pushes)'}


def api(method: str, path: str, *, payload: dict | None = None) -> dict | None:
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    if not token or not re.fullmatch(r'[\w.-]+/[\w.-]+', repo):
        raise RuntimeError('CI_GATE_REFUSED: missing authenticated GitHub repository context')
    url = 'https://api.github.com/repos/' + repo + '/' + path.lstrip('/')
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {'Authorization': 'Bearer ' + token,
               'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28',
               'User-Agent': 'aurora-ci-gate-v1'}
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            content = resp.read()
            return json.loads(content) if content else None
    except HTTPError as exc:
        detail = exc.read(2000).decode('utf-8', 'replace')
        raise RuntimeError(f'CI_GATE_API_REFUSED: {method} {path}: HTTP {exc.code} {detail[:300]}') from exc


def ensure_master(head: str) -> None:
    current = api('GET', 'branches/master')
    if not current or current['commit']['sha'] != head:
        raise RuntimeError('CI_GATE_REFUSED: master advanced during full gate; no certification tag')


def workflow_runs(file: str, head: str) -> list[dict]:
    data = api('GET', f'actions/workflows/{file}/runs?branch=master&event=workflow_dispatch&per_page=100')
    return [r for r in data['workflow_runs'] if r['head_sha'] == head and r['event'] == 'workflow_dispatch']


def verify_run(file: str, run: dict, head: str) -> None:
    if run['head_sha'] != head or run['status'] != 'completed' or run['conclusion'] != 'success':
        raise RuntimeError(f'CI_GATE_REFUSED: {file} run is not successful on exact head')
    jobs = api('GET', f'actions/runs/{run["id"]}/jobs?filter=latest&per_page=100')
    if not jobs or jobs.get('total_count', 0) > 100:
        raise RuntimeError(f'CI_GATE_REFUSED: {file} job listing incomplete')
    by_name = {j['name']: j for j in jobs['jobs']}
    required = EXPECTED_JOBS[file]
    if not required.issubset(by_name):
        raise RuntimeError(f'CI_GATE_REFUSED: {file} missing jobs: {sorted(required - by_name.keys())}')
    if any(by_name[name]['status'] != 'completed' or by_name[name]['conclusion'] != 'success'
           or by_name[name]['head_sha'] != head for name in required):
        raise RuntimeError(f'CI_GATE_REFUSED: {file} mandatory jobs not all green on exact SHA')
    print(f'CI_FULL_GATE_WORKFLOW_PASS: {file} run={run["id"]} jobs={len(required)} sha={head}', flush=True)


def dispatch_gate(head: str, interval: int, *, force: bool) -> None:
    if os.environ.get('GITHUB_REF') != 'refs/heads/master':
        raise RuntimeError('CI_GATE_REFUSED: full gates only on master')
    plan = gate_plan(head, interval, force=force)
    print('CI_GATE_PLAN: ' + json.dumps(plan, sort_keys=True), flush=True)
    if not plan['due']:
        print('CI_GATE_NOT_DUE: skipping heavy workflows', flush=True)
        return
    ensure_master(head)
    known = {file: {r['id'] for r in workflow_runs(file, head)} for file in EXPECTED_JOBS}
    for file in EXPECTED_JOBS:
        api('POST', f'actions/workflows/{file}/dispatches', payload={'ref': 'master'})
        print(f'CI_FULL_GATE_DISPATCHED: {file}', flush=True)
    pending = set(EXPECTED_JOBS)
    selected: dict[str, dict] = {}
    deadline = time.monotonic() + 90 * 60
    while pending and time.monotonic() < deadline:
        ensure_master(head)
        for file in list(pending):
            runs = [r for r in workflow_runs(file, head) if r['id'] not in known[file]]
            if not runs:
                continue
            run = max(runs, key=lambda x: x['id'])
            if run['status'] != 'completed':
                continue
            verify_run(file, run, head)
            selected[file] = run
            pending.remove(file)
        if pending:
            print('CI_FULL_GATE_WAIT: ' + ', '.join(sorted(pending)), flush=True)
            time.sleep(20)
    if pending:
        raise RuntimeError('CI_GATE_REFUSED: timed out: ' + ', '.join(sorted(pending)))
    ensure_master(head)
    tag = f'{GATE_TAG_PREFIX}{os.environ["GITHUB_RUN_ID"]}'
    api('POST', 'git/refs', payload={'ref': 'refs/tags/' + tag, 'sha': head})
    print(f'CI_FULL_GATE_TAGGED_PASS: tag={tag} sha={head} workflows={len(selected)}', flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='action', required=True)
    for name in ('classify', 'run-targeted'):
        p = sub.add_parser(name)
        p.add_argument('--base', required=True)
        p.add_argument('--head', required=True)
        if name == 'classify':
            p.add_argument('--github-output')
    for name in ('gate-plan', 'gate-dispatch'):
        p = sub.add_parser(name)
        p.add_argument('--head', required=True)
        p.add_argument('--interval', type=int, default=DEFAULT_INTERVAL)
        p.add_argument('--force', action='store_true')
        if name == 'gate-plan':
            p.add_argument('--github-output')
    args = parser.parse_args()
    if args.action in {'classify', 'run-targeted'}:
        paths = paths_between(args.base, args.head)
        # Never drop an expected security test because a PR deleted its file.
        plan = classify(paths)
        print('CI_TARGETED_PLAN: ' + json.dumps(plan, sort_keys=True), flush=True)
        if args.action == 'classify':
            if args.github_output:
                with open(args.github_output, 'a', encoding='utf-8') as out:
                    out.write('needs_android=' + str(plan['needs_android']).lower() + '\n')
                    out.write('ci_sensitive=' + str(plan['ci_sensitive']).lower() + '\n')
                    out.write('group_names=' + ','.join(plan['groups']) + '\n')
        else:
            for name in plan['tests']:
                print('CI_TARGETED_TEST: ' + name, flush=True)
                subprocess.run([sys.executable, '-B', 'scripts/ci/' + name], check=True)
            print(f'CI_TARGETED_PASS: {len(plan["tests"])} checks', flush=True)
    elif args.action == 'gate-plan':
        plan = gate_plan(args.head, args.interval, force=args.force)
        print('CI_GATE_PLAN: ' + json.dumps(plan, sort_keys=True), flush=True)
        if args.github_output:
            with open(args.github_output, 'a', encoding='utf-8') as out:
                out.write('due=' + str(plan['due']).lower() + '\n')
                out.write('overlay_units_since_gate=' + str(plan['overlay_units_since_gate']) + '\n')
    else:
        dispatch_gate(args.head, args.interval, force=args.force)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
