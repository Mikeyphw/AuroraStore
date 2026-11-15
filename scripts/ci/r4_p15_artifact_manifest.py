#!/usr/bin/env python3
"""P15 — attest *actual* GitHub-built vanilla debug + instrumentation APKs."""
from __future__ import annotations
import argparse,hashlib,json,os,re,shutil,subprocess,sys
from pathlib import Path
REPO='Mikeyphw/AuroraStore'
APP='com.aurora.store.debug';TEST=APP+'.test'
class Refused(ValueError):pass
def need(ok,reason):
 if not ok:raise Refused('P15_ARTIFACT_REFUSED_'+reason)
def tool(name):
 p=shutil.which(name)
 if p:return p
 base=Path(os.environ.get('ANDROID_HOME',os.environ.get('ANDROID_SDK_ROOT','/nonexistent')))/'build-tools'
 options=sorted(base.glob('*/'+name),reverse=True)
 need(bool(options),'MISSING_ANDROID_TOOL_'+name)
 return str(options[0])
def output(args):
 p=subprocess.run(args,capture_output=True,text=True,timeout=110)
 need(p.returncode==0,'PROCESS_FAILED_'+str(args[:2])+'_'+p.stderr[-250:])
 return p.stdout
def signer(apk):
 s=output([tool('apksigner'),'verify','--print-certs',str(apk)])
 m=re.search(r'(?im)^Signer #1 certificate SHA-256 digest:\s*([a-f0-9]{64})\s*$',s)
 need(m is not None,'UNSIGNED_OR_UNRECOGNIZED_SIGNER_'+apk.name)
 need('DOES NOT VERIFY' not in s and 'ERROR' not in s.upper(),'APK_SIGNATURE_FAILURE')
 return m.group(1).lower()
def package(apk):
 s=output([tool('aapt'),'dump','badging',str(apk)])
 m=re.search(r"(?m)^package: name='([^']+)' versionCode='([0-9]+)'",s)
 need(m is not None,'NO_APK_BADGING')
 return m.group(1)
def make(app,test,out,sha,run,attempt):
 need(re.fullmatch('[0-9a-f]{40}',sha) is not None,'SOURCE_SHA')
 need(run.isdigit() and attempt.isdigit(),'GH_RUN_ID')
 need(app.is_file() and test.is_file() and app.resolve()!=test.resolve(),'APK_PAIR')
 need(package(app)==APP and package(test)==TEST,'PACKAGE_NAME_MISMATCH')
 # Test target/runner matching is later checked again from real Android pm registry.
 out.mkdir(parents=True,exist_ok=True)
 entries={}
 for role,src,name in (('app',app,'aurora-p15-app.apk'),
                       ('instrumentation',test,'aurora-p15-androidTest.apk')):
  cert=signer(src)
  data=src.read_bytes();need(len(data)>10_000,'APK_TOO_SMALL_'+role)
  dest=out/name;dest.write_bytes(data)
  entries[role]={'file':name,'sha256':hashlib.sha256(data).hexdigest(),
                 'bytes':len(data),'signer_sha256':cert}
 manifest={'schema':1,'repo':REPO,'source_sha':sha,'run_id':run,'run_attempt':int(attempt),
           'app_package':APP,'test_package':TEST,'apks':entries,
           'android_tests':32,'expected_screenshots':15,
           'purpose':'P15 physical, explicit authorisation only',
           'physical_qualified':False,'installer_prompt_decline_qualified':False,
           'release_qualified':False}
 (out/'p15-apk-manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
 print('P15_HOSTED_APK_SHA256_AND_SIGNING_CERT_IDENTITY_PASS',sha,run)
 print('P15_DEVICE_INSTALLS_NOT_EXECUTED')
 return manifest

def main():
 p=argparse.ArgumentParser();p.add_argument('--app',type=Path,required=True)
 p.add_argument('--test',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
 p.add_argument('--source',required=True);p.add_argument('--run',required=True)
 p.add_argument('--attempt',default='1');a=p.parse_args()
 try:make(a.app,a.test,a.out,a.source,a.run,a.attempt)
 except (Refused,OSError,subprocess.SubprocessError) as e:
  print(str(e),file=sys.stderr);raise SystemExit(2)
if __name__=='__main__':main()
