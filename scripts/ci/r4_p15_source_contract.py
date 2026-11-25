#!/usr/bin/env python3
"""P15 additive source contract. Immutable P13/P14 and explicit device-write boundary."""
from __future__ import annotations
import argparse,json,re,subprocess,sys
from pathlib import Path
BASE='1ab625ea916de533de4bbc9db8703aafc23f691b'
BRANCH='feature/aurora-r4-p15-physical-arm64-20261115'
PINS='docs/r4/R4_P15_SOURCE_PINS.json'
DOC='docs/r4/R4_P15_PHYSICAL_ARM64_ACCEPTANCE.md'
DEVICE='scripts/ci/r4_p15_physical_acceptance.py'
ARTIFACT='scripts/ci/r4_p15_artifact_manifest.py'
CONTRACT='scripts/ci/r4_p15_source_contract.py'
UNIT='scripts/ci/test_r4_p15_source_contract.py'
WF='.github/workflows/aurora-r4-p15-apks.yml'
ADDITIVE={PINS,DOC,DEVICE,ARTIFACT,CONTRACT,UNIT,WF}
class Refused(ValueError):pass
def need(x,why):
 if not x:raise Refused('P15_SOURCE_REFUSED_'+why)
def git(root,*args):
 p=subprocess.run(['git',*args],cwd=root,capture_output=True,text=True)
 need(p.returncode==0,'GIT_'+args[0]+'_'+p.stderr[-250:]);return p.stdout.strip()
def check_device(s):
 required=('SERIAL=\'localhost:5555\'', 'AUTH=\'I_AUTHORIZE_P15_TEST_APK_INSTALLS\'',
  "'ro.build.version.sdk'","'ro.product.cpu.abi'","'ro.kernel.qemu'",
  "'arm64-v8a'", "need(not any(packages.values())",
  'verify_artifact(artifact_dir)', 'GH_HOSTED_BUILD_NOT_VERIFIED',
  'GH_ARTIFACT_BYTES_DRIFT_', 'GH_ARTIFACT_MANIFEST_DRIFT',
  'P15_BRANCH_HEAD_CHANGED', 'P15_TARGETED_CI_NOT_GREEN_FOR_SOURCE',
  "('app',PKG)", "('instrumentation',TEST_PKG)",
  "'owned_install_intent'", "'installed_by_this_run'","'installed_package_paths'",
  'OWNERSHIP_PATH_NOT_PROVEN_', 'CLEANUP_OWNERSHIP_NOT_PROVEN_',
  "'cleanup'", "'physical_arm64_qualified'", "'release_qualified'",
  "'real_installer_prompt_decline_qualified'",
  "'p14_physical_parity_pass'", "record['physical_arm64_qualified']=False", "def cleanup(out):",
  'def screenshot_evidence(out):','def instrument(', 'selector.select(',
  'INSTRUMENTATION_CODE: -1','P15_PHYSICAL_32_OF_32_P14_PARITY_PASS_15_PNGS_CLEANUP_PASS',
  'P15_MANUAL_OS_INSTALLER_DECLINE_AND_RELEASE_NOT_QUALIFIED',
  "if args.preflight:","elif args.run:","elif args.cleanup:",
  'len(images)==15','len(record.get(\'screenshots\',{}))==15')
 for key in required:need(key in s,'DEVICE_MISSING_'+key)
 for forbidden in ('su -c','adb -s localhost:5555 shell pm clear','adb root',
                   'wm size reset','wm density reset', 'gh workflow run',
                   'am start -a android.intent.action.DELETE'):
  need(forbidden not in s,'UNAUTHORIZED_DEVICE_MUTATION_'+forbidden)
 need('I_AUTHORIZE_P15_TEST_APK_INSTALLS' in s and "need(ack==AUTH" in s,'AUTH_GUARD')
 need(s.count("'adb','-s',SERIAL")==3,'ONLY_EXPLICIT_SERIAL_ADB')
 need("'real_installer_prompt_decline_qualified':False" in s,'FALSE_INSTALLER_CLAIM')
 return True
def check_manifest(s):
 for key in ("'apksigner'", "'aapt'", "'aapt2'", "'packagename'", 'certificate SHA-256 digest',
  'extract_package_name(', 'PACKAGE_TOOL_DISAGREEMENT_',
  'AAPT2_PACKAGE_UNRECOGNIZED_',
  'P15_HOSTED_APK_SHA256_AND_SIGNING_CERT_IDENTITY_PASS',
  "'source_sha':sha", "'run_id':run", "'run_attempt':int(attempt)",
  "'physical_qualified':False", "'installer_prompt_decline_qualified':False",
  "'release_qualified':False", "'aurora-p15-app.apk'", "'aurora-p15-androidTest.apk'",
  "'com.aurora.store.debug'", 'P15_DEVICE_INSTALLS_NOT_EXECUTED',
  'extract_signer_sha256(', 'SIGNER_CERT_CONFLICT_',
  "'--verbose'", 'V\\d+(?:\\.\\d+)?'):
  need(key in s,'MANIFEST_MARKER_'+key)
 return True
def check_workflow(s):
 for key in (BRANCH,'on:\n  push:', 'permissions:\n  contents: read',
  'persist-credentials: false', 'if: always()',
  ':app:assembleVanillaDebug :app:assembleVanillaDebugAndroidTest',
  'r4_p15_artifact_manifest.py', 'r4_p15_source_contract.py',
  'test_r4_p15_source_contract.py','actions/upload-artifact@',
  'GitHub-only Android APKs', 'git diff --check '+BASE+' HEAD'):
  need(key in s,'WF_MARKER_'+key)
 need(not re.search(r'(?m)^\s*(contents|actions|pull-requests): write\b',s),'WORKFLOW_WRITE_PERMISSION')
 for key in ('adb install','adb -s','am instrument','/dev/kvm'):
  need(key not in s,'WORKFLOW_DEVICE_EXECUTION_'+key)
 return True
def source_only(root):
 for file in ADDITIVE:need((root/file).is_file(),'MISSING_'+file)
 p=json.loads((root/PINS).read_text())
 need(p.get('schema')==1 and p.get('base_sha')==BASE,'BASE_SHA')
 need(p.get('p14_p01_p02_sha')=='6e9418baaefadd4afcf4320b4a4b193546e66ec7','PR4_SHA')
 need(len(p.get('protected_blobs',{}))==17,'PROTECTED_PIN_COUNT')
 need(all(re.fullmatch('[0-9a-f]{40}',x) for x in p['protected_blobs'].values()),'INVALID_SOURCE_BLOB')
 check_device((root/DEVICE).read_text())
 check_manifest((root/ARTIFACT).read_text())
 check_workflow((root/WF).read_text())
 doc=(root/DOC).read_text()
 for marker in ('P15','hosted','ARM64','32','15','manual installer','read-only','localhost:5555','rollback','I_AUTHORIZE_P15_TEST_APK_INSTALLS'):
  need(marker in doc,'DOC_SCOPE_'+marker)
 return True
def verify(root):
 source_only(root)
 need(git(root,'merge-base',BASE,'HEAD')==BASE,'P14P03_NOT_ANCESTOR')
 need(not git(root,'status','--porcelain'),'WORKTREE_DIRTY')
 changed=set(git(root,'diff','--name-only',BASE,'HEAD').splitlines())
 need(changed==ADDITIVE,'ADDITIVE_ONLY_'+repr(sorted(changed^ADDITIVE)))
 pins=json.loads((root/PINS).read_text())['protected_blobs']
 for path,blob in pins.items():
  need(git(root,'rev-parse',BASE+':'+path)==blob,'BASE_PIN_DRIFT_'+path)
  need(git(root,'rev-parse','HEAD:'+path)==blob,'PROTECTED_P14_DRIFT_'+path)
 return git(root,'rev-parse','HEAD')
def main():
 a=argparse.ArgumentParser();a.add_argument('--source-only',action='store_true')
 a.add_argument('--root',default='.',type=Path);a.add_argument('--integration',action='store_true');p=a.parse_args()
 if p.integration:
  from check_aur_int01 import verify as integration_verify
  integration_verify(p.root,'p15');return
 try:print('P15_SOURCE_PASS',source_only(p.root) if p.source_only else verify(p.root))
 except (Refused,OSError,ValueError,KeyError,TypeError) as e:
  print(str(e),file=sys.stderr);raise SystemExit(2)
if __name__=='__main__':main()
