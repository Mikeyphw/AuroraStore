#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R4 exact-source targeted APK reuse, never a substitute for emulator tests.

Reuses R3D's already-qualified immutable run, manifest, APK digest and APK-signature
verifiers. The R3D implementation is not modified: only its branch selector is
parameterized to point at the known R4 draft PR in this isolated process.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time

REPO = 'Mikeyphw/AuroraStore'
BRANCH = 'feature/r4-p03-pr113-expressive-v4-20261113'
R3D_BRANCH = 'feature/r3c04-c02-c08-import-handoff-archives-20261109'
WORKFLOW = '.github/workflows/aurora-targeted.yml'
SOURCE_SHA = re.compile(r'^[0-9a-f]{40}$')

class Refused(RuntimeError): pass

def need(condition, why):
    if not condition: raise Refused('R4_P06_HF17_REFUSED_' + why)

def validate_context(sha: str, env=None) -> None:
    env = os.environ if env is None else env
    need(SOURCE_SHA.fullmatch(sha) is not None, 'INVALID_SHA')
    need(env.get('GITHUB_SHA') == sha, 'GITHUB_SHA_DRIFT')
    need(env.get('GITHUB_REPOSITORY') == REPO, 'WRONG_REPOSITORY')
    need(env.get('GITHUB_REF') == 'refs/heads/' + BRANCH, 'WRONG_BRANCH')
    need(env.get('GITHUB_EVENT_NAME') in ('push', 'workflow_dispatch'), 'WRONG_EVENT')
    need(bool(env.get('GH_TOKEN') or env.get('GITHUB_TOKEN')), 'TOKEN_REQUIRED')

def require_trusted_pair():
    # Not a copy of R3D signing verification: import the canonical source pinned
    # against the unmodified R3D Git tree by the enclosing workflow/launcher.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import r3c07_hf03_apk_pair as pair
    need(pair.REPO == REPO, 'R3D_REPOSITORY_CONTRACT_DRIFT')
    need(pair.WORKFLOW == WORKFLOW, 'R3D_WORKFLOW_CONTRACT_DRIFT')
    need(pair.BRANCH == R3D_BRANCH, 'R3D_BRANCH_CONTRACT_DRIFT')
    need(pair.TEST_JOBS == frozenset({
        'Source-change classification',
        'Targeted source and security contracts',
        'Targeted Android compilation (no emulator or release)',
    }), 'R3D_THREE_JOB_CONTRACT_DRIFT')
    need(set(pair.NAMES) == {'app', 'androidTest'}, 'R3D_ROLE_CONTRACT_DRIFT')
    pair.BRANCH = BRANCH  # R4 selector, strictly scoped to this subprocess
    return pair

def probe(root: Path, sha: str, tmp: Path, github_output: Path, wait_seconds: int = 240,
          pair=None, sleep=time.sleep, env=None):
    validate_context(sha, env)
    pair = require_trusted_pair() if pair is None else pair
    need(pair.exact_head(root, sha) == sha, 'CHECKOUT_SHA_DRIFT')
    need(not tmp.exists(), 'TEMP_OUTPUT_EXISTS')
    need(not github_output.exists() or github_output.stat().st_size == 0, 'GITHUB_OUTPUT_NOT_EMPTY')
    need(not any((root/path).exists() for path in (
        'app/build/outputs/apk/vanilla/debug', 'app/build/outputs/apk/androidTest'
    )), 'PREEXISTING_APK_OUTPUTS')
    need(0 <= wait_seconds <= 300, 'INVALID_WAIT_RANGE')
    # A clean runner often starts ahead of the PR's parallel Targeted CI.
    # Wait only for a source-matched, fully green three-job targeted run.
    chosen = pair.selected_run(sha)
    for _ in range((wait_seconds + 14) // 15):
        if chosen is not None: break
        sleep(15)
        chosen = pair.selected_run(sha)
    if chosen is None:
        github_output.write_text('reused=false\n', encoding='utf-8')
        print('R4_P06_HF17_NO_ELIGIBLE_TARGETED_ARTIFACT_INDEPENDENT_HOSTED_BUILD_REQUIRED',flush=True)
        return False
    artifact = pair.matching_artifact(chosen, sha)
    if artifact is None:
        # A successful old run with no artifact is never itself a qualification.
        github_output.write_text('reused=false\n', encoding='utf-8')
        print('R4_P06_HF17_NO_IMMUTABLE_APK_PAIR_INDEPENDENT_BUILD_REQUIRED',flush=True)
        return False
    files = pair.download_artifact(artifact, int(chosen['id']))
    need(set(files) == {'app.apk', 'androidTest.apk', pair.MANIFEST}, 'ARTIFACT_FILE_SET_DRIFT')
    try:
        doc = json.loads(files[pair.MANIFEST])
    except (ValueError,UnicodeError) as e:
        raise Refused('R4_P06_HF17_REFUSED_INVALID_TARGETED_MANIFEST') from e
    pair.verify_doc(doc, sha, int(chosen['id']), files, int(chosen['run_attempt']))
    # Verify both actual APK cryptographic signatures and package identities
    # before publishing either into the Gradle output directories.
    tmp.mkdir(parents=True)
    try:
        for name in ('app.apk', 'androidTest.apk'):
            (tmp/name).write_bytes(files[name])
        verified = pair.validate_pair(tmp/'app.apk', tmp/'androidTest.apk')
        need(verified == doc['files'], 'APK_SIGNER_OR_DIGEST_DRIFT')
        for role,rel in pair.ROLE_PATHS.items():
            target=root/rel
            target.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(tmp/pair.NAMES[role], target/pair.NAMES[role])
        (tmp/pair.MANIFEST).write_bytes(files[pair.MANIFEST])
        (tmp/'reuse-source.json').write_text(json.dumps({
            'source_sha':sha,
            'targeted_run_id':str(chosen['id']),
            'targeted_run_attempt':str(chosen['run_attempt']),
            'artifact_id':artifact['id'],
            'manifest_sha256':pair.sha(files[pair.MANIFEST]),
        },indent=2,sort_keys=True)+'\n',encoding='utf-8')
        github_output.write_text('reused=true\n',encoding='utf-8')
    except BaseException:
        # Do not let partial APK copies become inputs to any fallback build.
        for rel in pair.ROLE_PATHS.values():
            shutil.rmtree(root/rel, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    print('R4_P06_HF17_EXACT_SOURCE_SIGNED_APK_PAIR_REUSED sha='+sha+
          ' run='+str(chosen['id'])+' artifact='+str(artifact['id']),flush=True)
    return True

def finalize(root: Path, sha: str, tmp: Path, receipt: Path, reused: bool, pair=None,
             env=None):
    validate_context(sha, env)
    pair = require_trusted_pair() if pair is None else pair
    need(pair.exact_head(root, sha) == sha, 'CHECKOUT_SHA_DRIFT')
    need(receipt.parent.is_dir(), 'RECEIPT_PARENT_MISSING')
    pair.finalize(root, tmp, sha, receipt, reused)
    doc=json.loads(receipt.read_text())
    need(doc.get('overall')=='PASS' and doc.get('role')=='APK_INPUT_PROVENANCE_ONLY'
         and doc.get('source_sha')==sha and doc.get('release_qualified') is False
         and doc.get('physical_device_qualified') is False
         and doc.get('instrumentation_qualified') is False,
         'APK_PAIR_PROVENANCE_RECEIPT_DRIFT')
    print('R4_P06_HF17_EXACT_SHA_SIGNED_APK_INPUT_PROVENANCE_PASS sha='+sha,flush=True)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest='action',required=True)
    for action in ('probe','finalize'):
        p=sub.add_parser(action)
        p.add_argument('--root',type=Path,default=Path('.'))
        p.add_argument('--sha',required=True)
        p.add_argument('--tmp',type=Path,required=True)
        if action=='probe':
            p.add_argument('--github-output',type=Path,required=True)
            p.add_argument('--wait-seconds',type=int,default=240)
        else:
            p.add_argument('--receipt',type=Path,required=True)
            p.add_argument('--reused',choices=('true','false'),required=True)
    a=ap.parse_args()
    root=a.root.resolve(strict=True)
    if a.action=='probe':probe(root,a.sha,a.tmp,a.github_output,a.wait_seconds)
    else:finalize(root,a.sha,a.tmp,a.receipt,a.reused=='true')

if __name__=='__main__':
    try: main()
    except (Refused,OSError,ValueError,KeyError) as e:
        print('R4_P06_HF17_REFUSED '+str(e),file=sys.stderr)
        raise SystemExit(1)
