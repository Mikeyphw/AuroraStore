#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Exact-head, signed build-pair reuse between Aurora Targeted CI and R1D.

Targeted CI publishes a sealed, run-bound pair; R1D accepts only the three
successful jobs from the source-bound targeted run, exact APK digests, exact
packages and independently verified per-role Android signing certificates. It does not bless
any installer, real publisher, physical hardware or release artifact.

If an eligible run exists but the artifact is corrupt/ambiguous, fail closed.
If no eligible complete run exists (or pre-optimization runs lack an artifact),
R1D builds independently; no test skips or manufactured success evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

# Reuse Aurora's independently qualified SDK37-aware certificate parser.
# It distinguishes a single signer repeated across V2/V3 schemes from
# multiple signer identities, malformed evidence, and certificate drift.
from r3c06_bundletool_matrix import (
    Refused as SigningProofRefused,
    signed_schemes as checked_signing_schemes,
    single_signer as checked_single_signer,
)

REPO = 'Mikeyphw/AuroraStore-Standalone'
BRANCH = 'feature/r3c04-c02-c08-import-handoff-archives-20261109'
WORKFLOW = '.github/workflows/aurora-targeted.yml'
TEST_JOBS = frozenset({
    'Source-change classification',
    'Targeted source and security contracts',
    'Targeted Android compilation (no emulator or release)',
})
APP_PKG = 'com.aurora.store.debug'
TEST_PKG = 'com.aurora.store.debug.test'
ROLE_PATHS = {
    'app': Path('app/build/outputs/apk/vanilla/debug'),
    'androidTest': Path('app/build/outputs/apk/androidTest'),
}
NAMES = {'app': 'app.apk', 'androidTest': 'androidTest.apk'}
MANIFEST = 'manifest.json'
APK_LIMIT = 150 * 1024 * 1024
ZIP_LIMIT = 310 * 1024 * 1024
ARTIFACT_LIMIT = 310 * 1024 * 1024
SHA = re.compile(r'^[0-9a-f]{40}$')

class Refused(RuntimeError):
    pass


def ensure(condition: bool, why: str) -> None:
    if not condition:
        raise Refused('R3C07_HF03_APK_REFUSED: ' + why)


def run(argv: list[str], *, binary=False, timeout=120):
    try:
        p = subprocess.run(argv, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Refused(f'R3C07_HF03_APK_REFUSED: unavailable command {argv[0]}: {exc}') from exc
    if p.returncode:
        detail=(p.stderr or p.stdout)[-1100:].decode('utf-8', 'replace')
        raise Refused(f'R3C07_HF03_APK_REFUSED: {argv[0]} exited {p.returncode}: {detail}')
    return p.stdout if binary else p.stdout.decode('utf-8', 'replace').strip()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def exact_head(root: Path, expected: str) -> str:
    ensure(SHA.fullmatch(expected) is not None, 'invalid exact HEAD SHA')
    actual = run(['git','-C',str(root),'rev-parse','HEAD'])
    ensure(actual == expected, 'checkout differs from exact requested commit')
    ensure(os.getenv('GITHUB_REPOSITORY') == REPO, 'wrong GitHub repository')
    return actual


def find_tool(prefix: str) -> str:
    sdk = Path(os.environ.get('ANDROID_SDK_ROOT') or os.environ.get('ANDROID_HOME') or '')
    tools = sorted((sdk/'build-tools').glob('*/'+prefix), reverse=True) if str(sdk) not in ('','.') else []
    tools = [p for p in tools if p.is_file()]
    if tools:
        return str(tools[0])
    tool=shutil.which(prefix)
    ensure(tool is not None, f'{prefix} missing: cannot authenticate APK')
    return str(tool)


def check_apk(path: Path, role: str) -> dict:
    ensure(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= APK_LIMIT,
           f'{role} missing, symlink or invalid size')
    raw=path.read_bytes()
    ensure(raw.startswith(b'PK'), f'{role} not an APK ZIP')
    apksigner=find_tool('apksigner')
    # SDK37 prints one certificate line per signing scheme, unlike SDK36.
    # Cryptographic verification is mandatory for the actual API36 window;
    # signer text alone is never accepted as evidence of verification.
    cert_output=run([apksigner,'verify','--verbose','--print-certs',
                     '--min-sdk-version','36','--max-sdk-version','36',
                     str(path)],timeout=90)
    try:
        certificate=checked_single_signer(cert_output)
        schemes=checked_signing_schemes(cert_output)
    except SigningProofRefused as exc:
        raise Refused(f'R3C07_HF06_SIGNER_REFUSED: {role}: {exc}') from exc
    ensure(schemes.get('2') is True or schemes.get('3') is True,
           f'{role} lacks verified APK v2/v3 signing scheme on API36')
    aapt=find_tool('aapt')
    package=run([aapt,'dump','badging',str(path)],timeout=90)
    packages=re.findall(r"^package:\s+name='([^']+)'",package,re.M)
    want=APP_PKG if role=='app' else TEST_PKG
    ensure(packages==[want], f'{role} unexpected package: {packages}')
    if role=='androidTest':
        xml=run([aapt,'dump','xmltree',str(path),'AndroidManifest.xml'],timeout=90)
        ensure('instrumentation' in xml and APP_PKG in xml and
               'HiltInstrumentationTestRunner' in xml,
               'AndroidTest APK does not target the real Hilt instrumented application')
    return {'filename':NAMES[role], 'size':len(raw), 'sha256':sha(raw),
            'package':want, 'signer_sha256':certificate}


def validate_pair(app: Path, test: Path) -> dict:
    info={'app':check_apk(app,'app'), 'androidTest':check_apk(test,'androidTest')}
    return info


def only_apk(path: Path) -> Path:
    found=sorted(path.rglob('*.apk'))
    ensure(len(found)==1 and found[0].is_file() and not found[0].is_symlink(),
           f'exactly one built APK required under {path}')
    return found[0]


def publish(root: Path, out: Path, expected: str) -> None:
    exact_head(root,expected)
    ensure(os.getenv('GITHUB_EVENT_NAME')=='pull_request', 'publish requires pull_request targeted CI')
    rid=os.getenv('GITHUB_RUN_ID','')
    attempt=os.getenv('GITHUB_RUN_ATTEMPT','')
    ensure(rid.isdecimal() and int(rid)>0 and attempt.isdecimal() and int(attempt)>0,
           'targeted run id/attempt missing')
    ensure(not out.exists(), 'publish output already exists')
    source={role:only_apk(root/rel) for role,rel in ROLE_PATHS.items()}
    certs=validate_pair(source['app'],source['androidTest'])
    out.mkdir(parents=True)
    for role,p in source.items():
        shutil.copyfile(p,out/NAMES[role])
    ensure(validate_pair(out/'app.apk',out/'androidTest.apk')==certs,
           'copied pair no longer matches build output')
    doc={'schema_version':1,'kind':'aurora-r3c07-hf03-targeted-apk-pair',
         'repository':REPO, 'source_sha':expected,'targeted_run_id':rid,
         'targeted_run_attempt':attempt,'build_variant':'vanillaDebug',
         'files':certs, 'installation_qualified':False,
         'publisher_authenticated':False,'physical_device_qualified':False,
         'release_qualified':False}
    (out/MANIFEST).write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(f'R3C07_HF03_TARGETED_APK_PAIR_PUBLISHED sha={expected} run={rid}',flush=True)


def api(path: str) -> dict:
    ensure(os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN'),
           'GH_TOKEN/GITHUB_TOKEN required for GitHub Actions provenance')
    ensure(path.startswith('repos/'+REPO+'/'), 'out of repository API request')
    reply=run(['gh','api',path],timeout=75,binary=True)
    ensure(len(reply)<2*1024*1024, 'oversized GitHub metadata response')
    try:
        result=json.loads(reply)
    except (ValueError,UnicodeDecodeError) as exc:
        raise Refused('R3C07_HF03_APK_REFUSED: invalid GitHub API JSON') from exc
    ensure(isinstance(result,dict),'unexpected GitHub API response type')
    return result


def qualifies_run(runmeta: dict, expected: str) -> bool:
    return (runmeta.get('head_sha')==expected and runmeta.get('head_branch')==BRANCH
            and runmeta.get('event')=='pull_request' and runmeta.get('status')=='completed'
            and runmeta.get('conclusion')=='success' and runmeta.get('path')==WORKFLOW
            and runmeta.get('repository',{}).get('full_name')==REPO)


def selected_run(expected: str) -> dict|None:
    # Pull-request-targeted jobs must be completed and green on the *source* SHA.
    # Workflow dispatch on a floating branch is never sufficient evidence.
    query=f'repos/{REPO}/actions/workflows/aurora-targeted.yml/runs?event=pull_request&head_sha={expected}&per_page=100'
    raw=api(query)
    ensure(raw.get('total_count',0)<=100,'unpaged targeted run listing')
    runs=[r for r in raw.get('workflow_runs',[]) if qualifies_run(r,expected)]
    runs.sort(key=lambda r:r['id'],reverse=True)
    for runmeta in runs:
        rid=runmeta['id']
        result=api(f'repos/{REPO}/actions/runs/{rid}/jobs?per_page=100')
        ensure(result.get('total_count',0)<=100,'unpaged targeted jobs')
        jobs=result.get('jobs',[])
        if (len(jobs)!=3 or {j.get('name') for j in jobs}!=TEST_JOBS or
            any(j.get('status')!='completed' or j.get('conclusion')!='success' or
                j.get('head_sha')!=expected for j in jobs)):
            continue
        return runmeta
    return None


def matching_artifact(runmeta: dict, expected: str) -> dict|None:
    rid=runmeta['id']
    result=api(f'repos/{REPO}/actions/runs/{rid}/artifacts?per_page=100')
    ensure(result.get('total_count',0)<=100,'unpaged targeted artifact list')
    name=f'aurora-targeted-apks-{expected}-{rid}-{runmeta["run_attempt"]}'
    artifacts=[a for a in result.get('artifacts',[]) if a.get('name')==name and not a.get('expired')]
    ensure(len(artifacts)<=1, 'ambiguous targeted APK artifacts')
    if not artifacts:
        return None  # Old targeted run from before this optimization; build independently.
    item=artifacts[0]
    ensure(0 < item.get('size_in_bytes',0) <= ARTIFACT_LIMIT, 'artifact archive unexpectedly large')
    ensure(item.get('workflow_run',{}).get('id') in (None,rid),
           'artifact run association does not match')
    return item


def download_artifact(item: dict, runid: int) -> dict[str,bytes]:
    # gh run download is the same well-tested extraction interface used by the
    # HF02 as-run receipt verifier. The extraction root is private and empty.
    # Inspect the entire extraction tree before accepting any bytes.
    name=item['name']
    with tempfile.TemporaryDirectory(prefix='aurora-r3c07-targeted-pair-',
                                      dir=os.getenv('RUNNER_TEMP') or None) as work:
        base=Path(work)
        run(['gh','run','download',str(runid),'-R',REPO,'-n',name,'-D',str(base)],timeout=360)
        found=list(base.rglob('*'))
        ensure(len(found)==3 and all(p.is_file() and not p.is_symlink() and
                                      p.parent==base for p in found),
               'artifact extraction contains extra paths, symlinks or directories')
        ensure({p.name for p in found}=={'app.apk','androidTest.apk',MANIFEST},
               'targeted APK artifact has unexpected file names')
        for p in found:
            ensure(0<p.stat().st_size<=(64*1024 if p.name==MANIFEST else APK_LIMIT),
                   'invalid artifact file size')
        ensure(sum(p.stat().st_size for p in found)<=ZIP_LIMIT,
               'expanded artifact exceeds size cap')
        return {p.name:p.read_bytes() for p in found}


def verify_doc(doc: dict, expected: str, rid: int, records: dict[str,bytes], attempt: int|None=None):
    ensure(doc.get('schema_version')==1 and doc.get('kind')=='aurora-r3c07-hf03-targeted-apk-pair'
           and doc.get('source_sha')==expected and doc.get('targeted_run_id')==str(rid)
           and doc.get('repository')==REPO and doc.get('build_variant')=='vanillaDebug',
           'artifact manifest mismatches exact source and run')
    ensure(isinstance(doc.get('targeted_run_attempt'),str) and doc['targeted_run_attempt'].isdigit(),
           'missing targeted run attempt')
    if attempt is not None:
        ensure(doc['targeted_run_attempt']==str(attempt), 'artifact came from wrong run attempt')
    for k in ('installation_qualified','publisher_authenticated','physical_device_qualified','release_qualified'):
        ensure(doc.get(k) is False, f'unsupported qualification flag {k}')
    declared=doc.get('files')
    ensure(isinstance(declared,dict) and set(declared)==set(NAMES),'missing or extra APK roles')
    for role,name in NAMES.items():
        entry=declared[role]
        ensure(isinstance(entry,dict) and entry.get('filename')==name and
               entry.get('size')==len(records[name]) and entry.get('sha256')==sha(records[name])
               and entry.get('package')==(APP_PKG if role=='app' else TEST_PKG) and
               re.fullmatch('[0-9a-f]{64}',entry.get('signer_sha256','')) is not None,
               f'APK {role} manifest integrity mismatch')


def consume(root: Path, tmp: Path, expected: str, github_output: Path):
    exact_head(root,expected)
    ensure(os.getenv('GITHUB_EVENT_NAME')=='workflow_dispatch', 'consume requires hosted R1D dispatch')
    ensure(not any(any((root/v).rglob('*.apk')) for v in ROLE_PATHS.values()),'existing APK outputs would make reuse ambiguous')
    chosen=selected_run(expected)
    artifact=matching_artifact(chosen,expected) if chosen else None
    if not artifact:
        github_output.write_text('reused=false\n',encoding='utf-8')
        print('R3C07_HF03_APK_PAIR_INDEPENDENT_BUILD_REQUIRED: no eligible artifact')
        return
    files=download_artifact(artifact,chosen['id'])
    try:
        doc=json.loads(files[MANIFEST])
    except (UnicodeError,ValueError) as exc:
        raise Refused('R3C07_HF03_APK_REFUSED: manifest is not JSON') from exc
    verify_doc(doc,expected,chosen['id'],files,chosen['run_attempt'])
    ensure(not tmp.exists(),'reuse temp already exists')
    tmp.mkdir(parents=True)
    for name in NAMES.values():
        (tmp/name).write_bytes(files[name])
    verified=validate_pair(tmp/'app.apk',tmp/'androidTest.apk')
    ensure(verified==doc['files'],'actual signed APKs do not match declared manifest')
    for role,rel in ROLE_PATHS.items():
        dst=root/rel
        dst.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(tmp/NAMES[role],dst/NAMES[role])
    (tmp/MANIFEST).write_bytes(files[MANIFEST])
    (tmp/'reuse-source.json').write_text(json.dumps({
        'source_sha':expected,'targeted_run_id':str(chosen['id']),
        'targeted_run_attempt':str(chosen['run_attempt']),
        'artifact_id':artifact['id'],'manifest_sha256':sha(files[MANIFEST])},
        indent=2,sort_keys=True)+'\n',encoding='utf-8')
    github_output.write_text('reused=true\n',encoding='utf-8')
    print(f'R3C07_HF03_APK_PAIR_REUSED sha={expected} targeted_run={chosen["id"]} artifact={artifact["id"]}')


def finalize(root: Path, tmp: Path, expected: str, receipt: Path, reused: bool):
    exact_head(root,expected)
    rid=os.getenv('GITHUB_RUN_ID','')
    ensure(rid.isdecimal() and int(rid)>0,'R1D hosted run identity missing')
    pair={role:only_apk(root/rel) for role,rel in ROLE_PATHS.items()}
    actual=validate_pair(pair['app'],pair['androidTest'])
    parent={'targeted_run_id':None,'artifact_id':None,'manifest_sha256':None}
    if reused:
        ensure((tmp/MANIFEST).is_file() and (tmp/'reuse-source.json').is_file(),
               'no downloaded manifest/provenance to seal')
        doc=json.loads((tmp/MANIFEST).read_text())
        parent=json.loads((tmp/'reuse-source.json').read_text())
        verify_doc(doc,expected,int(parent['targeted_run_id']),{
            NAMES[r]:p.read_bytes() for r,p in pair.items()},int(parent['targeted_run_attempt']))
        ensure(doc['files']==actual,'installed build inputs were modified after source validation')
        ensure(parent['source_sha']==expected and parent['manifest_sha256']==sha((tmp/MANIFEST).read_bytes()),
               'reuse receipt source/manifest mismatch')
    else:
        ensure(not (tmp/'reuse-source.json').exists(), 'independent build carried stale reuse metadata')
    result={'overall':'PASS','role':'APK_INPUT_PROVENANCE_ONLY',
            'source_sha':expected,'run_id':rid,
            'mode':'EXACT_TARGETED_ARTIFACT' if reused else 'INDEPENDENT_HOSTED_BUILD',
            'apk_pair':actual,**parent,
            'instrumentation_qualified':False,'installation_qualified':False,
            'publisher_authenticated':False,'physical_device_qualified':False,'release_qualified':False}
    receipt.parent.mkdir(parents=True,exist_ok=True)
    receipt.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(f'R3C07_HF03_APK_SOURCE_PASS mode={result["mode"]} sha={expected} run={rid}',flush=True)


def main():
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest='op',required=True)
    for op in ('publish','consume','finalize'):
        p=sub.add_parser(op)
        p.add_argument('--root',type=Path,default=Path.cwd())
        p.add_argument('--sha',required=True)
        if op=='publish':p.add_argument('--out',required=True,type=Path)
        else:
            p.add_argument('--tmp',required=True,type=Path)
            if op=='consume':p.add_argument('--github-output',required=True,type=Path)
            else:
                p.add_argument('--receipt',required=True,type=Path)
                p.add_argument('--reused',required=True,choices=('true','false'))
    args=parser.parse_args()
    root=args.root.resolve(strict=True)
    if args.op=='publish': publish(root,args.out,args.sha)
    elif args.op=='consume':consume(root,args.tmp,args.sha,args.github_output)
    else:finalize(root,args.tmp,args.sha,args.receipt,args.reused=='true')

if __name__=='__main__':
    try: main()
    except (Refused,ValueError,KeyError,FileNotFoundError) as exc:
        print('R3C07_HF03_APK_REFUSED: '+str(exc),file=sys.stderr)
        raise SystemExit(1)
