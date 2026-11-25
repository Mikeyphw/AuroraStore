#!/usr/bin/env python3
"""P15 — opt-in, isolated API36 ARM64 P14 parity acceptance.

No local Gradle, Play sign-in, root, display override, third-party install,
or uninstall of an app present at preflight. An OS installer-decline prompt is
NOT exercised; its genuine confirmation remains a separate manual P15 gate.
"""
from __future__ import annotations
import argparse, datetime, hashlib, json, os, re, selectors, shutil, struct, subprocess, sys, tempfile, time, zlib
from pathlib import Path

REPO='Mikeyphw/AuroraStore'
SERIAL='localhost:5555'
PKG='com.aurora.store.debug'
TEST_PKG=PKG+'.test'
AUTH='I_AUTHORIZE_P15_TEST_APK_INSTALLS'
RUN_WORKFLOW='Aurora R4 P15 — Signed Physical Acceptance APKs'
SUITES=(
 ('nav3-search-details','com.aurora.store.compose.ui.r4.R4P14OfflineNav3JourneyDeviceTest',4),
 ('download-installer-policy','com.aurora.store.data.installer.R4P14P03LifecycleDeviceTest',8),
 ('download-ui','com.aurora.store.compose.ui.r4.R4P14P03DownloadUiDeviceTest',8),
 ('room-dao','com.aurora.store.data.room.download.DownloadLifecycleDeviceTest',9),
)
WORKER='com.aurora.store.data.work.DownloadWorkerOfflineDeviceTest'
WORKER_METHODS=('truncatedResponseRetriesThenResumesSameAttemptExactly',
                'shaMismatchRejectsPayloadWithoutInstallHandoff',
                'cancelledAttemptIsNotResurrectedOrDownloaded')
SHOTS=('r4_p14_search_route.png','r4_p14_downloads_route.png',
 'r4_p14_settings_route.png','r4_p14_preferences_route.png',
 'r4_p14_games_tab.png','r4_p14_updates_tab.png','r4_p14_populated_search.png',
 'r4_p14_details_identity.png','r4_p14_details_carousel.png','r4_p14_details_reviews.png',
 'r4_p14p03_queued.png','r4_p14p03_downloading.png','r4_p14p03_failed.png',
 'r1g_awaiting_retry.png','r1g_cancelled.png')

class Refused(Exception):pass
def need(condition,why):
 if not condition:raise Refused('P15_REFUSED_'+why)
def sha(data):return hashlib.sha256(data).hexdigest()
def json_save(path, obj):
 path.parent.mkdir(parents=True,exist_ok=True)
 temp=path.with_name(path.name+'.pending')
 temp.write_text(json.dumps(obj,sort_keys=True,indent=2)+'\n')
 os.replace(temp,path)
def command(args, timeout=90,check=True):
 try:p=subprocess.run([str(x) for x in args],capture_output=True,text=True,timeout=timeout)
 except (OSError,subprocess.TimeoutExpired) as exc:raise Refused('COMMAND_ERROR_'+str(exc)) from exc
 if check:need(p.returncode==0,'COMMAND_'+str(args[:4])+'_'+(p.stderr or p.stdout)[-300:])
 return p
def adb(*args,check=True,timeout=60):
 return command(['adb','-s',SERIAL,*args],timeout=timeout,check=check)
def prop(name):return adb('shell','getprop',name).stdout.strip().replace('\r','')
def package_paths():
 # pm path is read-only; capture exact install paths for interrupted-run ownership.
 return {pkg: tuple(x.removeprefix('package:') for x in
               adb('shell','pm','path',pkg,check=False).stdout.splitlines()
               if x.startswith('package:')) for pkg in (PKG,TEST_PKG)}
def packages_installed():
 return {pkg: bool(paths) for pkg,paths in package_paths().items()}
def inspect_device(allow_existing=False):
 need(shutil.which('adb'),'ADB_NOT_INSTALLED')
 need(adb('get-state').stdout.strip()=='device','ADB_DEVICE_NOT_READY')
 sdk=prop('ro.build.version.sdk');abi=prop('ro.product.cpu.abi')
 hardware=prop('ro.hardware');qemu=prop('ro.kernel.qemu')
 need(sdk=='36','ANDROID_API_NOT_36_'+sdk)
 need(abi=='arm64-v8a','NOT_PHYSICAL_ARM64_'+abi)
 need(qemu!='1' and hardware not in ('ranchu','goldfish','qemu'), 'EMULATOR_REFUSED')
 need(prop('sys.boot_completed')=='1','BOOT_NOT_COMPLETE')
 packages=packages_installed()
 if not allow_existing:need(not any(packages.values()),'PREEXISTING_AURORA_APP_OR_TEST_DONOT_OVERWRITE')
 return {'api':36,'abi':abi,'qemu':False,'hardware':hardware,
         'preexisting_packages':packages,'serial':SERIAL}
def gh_api(path):
 need(shutil.which('gh'),'GH_MISSING_PROVENANCE_REQUIRED')
 p=command(['gh','api','repos/'+REPO+'/'+path],timeout=90)
 try:return json.loads(p.stdout)
 except ValueError as exc:raise Refused('GH_RESPONSE_NOT_JSON') from exc
def verify_artifact(root):
 manifest=json.loads((root/'p15-apk-manifest.json').read_text())
 source=manifest.get('source_sha','');run=manifest.get('run_id')
 need(re.fullmatch(r'[0-9a-f]{40}',source) is not None,'INVALID_APK_SOURCE')
 need(isinstance(run,str) and run.isdigit(),'INVALID_RUN_ID')
 need(manifest.get('schema')==1 and manifest.get('repo')==REPO,'BAD_MANIFEST_REPOSITORY')
 need(manifest.get('app_package')==PKG and manifest.get('test_package')==TEST_PKG,'BAD_APK_PACKAGE')
 need(manifest.get('android_tests')==32 and manifest.get('expected_screenshots')==15,'BAD_TEST_INVENTORY')
 arts=manifest.get('apks',{})
 need(set(arts)=={'app','instrumentation'},'APK_INVENTORY')
 names=set()
 for key in ('app','instrumentation'):
  entry=arts[key];name=entry.get('file','')
  need(name in ('aurora-p15-app.apk','aurora-p15-androidTest.apk') and name not in names,'APK_FILENAME')
  names.add(name)
  path=root/name
  need(path.is_file() and path.stat().st_size>1000,'APK_FILE_MISSING_'+key)
  need(sha(path.read_bytes())==entry.get('sha256'),'APK_SHA_MISMATCH_'+key)
  need(re.fullmatch(r'[0-9a-f]{64}',entry.get('signer_sha256','')) is not None,'APK_SIGNER_SHA_MISSING')
 need(arts['app']['file']=='aurora-p15-app.apk' and arts['instrumentation']['file']=='aurora-p15-androidTest.apk','APK_ROLE_SWAP')
 workflow=gh_api('actions/runs/'+run)
 need(workflow.get('head_sha')==source and workflow.get('conclusion')=='success' and
      workflow.get('status')=='completed' and workflow.get('name')==RUN_WORKFLOW,
      'GH_HOSTED_BUILD_NOT_VERIFIED')
 branch=workflow.get('head_branch')
 need(branch=='feature/aurora-consolidated-integration-20261125','P15_INTEGRATION_BRANCH_REQUIRED')
 need(type(manifest.get('run_attempt')) is int and manifest['run_attempt']>=1 and
      workflow.get('run_attempt')==manifest['run_attempt'],'P15_RUN_ATTEMPT_DRIFT')
 remote_head=gh_api('git/ref/heads/'+branch)
 need(remote_head.get('object',{}).get('sha')==source,'P15_BRANCH_HEAD_CHANGED')
 other_runs=gh_api('actions/runs?branch='+branch+'&per_page=100').get('workflow_runs',[])
 need(any(r.get('head_sha')==source and r.get('name')=='Aurora — Targeted CI'
          and r.get('conclusion')=='success' for r in other_runs),
      'P15_TARGETED_CI_NOT_GREEN_FOR_SOURCE')
 artifact_name='aurora-r4-p15-apks-'+source+'-'+run+'-'+str(manifest.get('run_attempt',1))
 artifact_list=gh_api('actions/runs/'+run+'/artifacts?per_page=100').get('artifacts',[])
 need(len([a for a in artifact_list if a.get('name')==artifact_name and not a.get('expired')])==1,
      'GH_APK_ARTIFACT_NOT_FOUND')
 # An arbitrary local APK+manifest pair is NOT a trusted GitHub artifact. Fetch
 # the actual workflow upload again and compare its bytes before ANY install.
 with tempfile.TemporaryDirectory(prefix='aurora-p15-attest-') as tmp:
  result=command(['gh','run','download',run,'--repo',REPO,
                  '--name',artifact_name,'--dir',tmp],timeout=600)
  upstream=Path(tmp)
  need((upstream/'p15-apk-manifest.json').read_bytes()==
       (root/'p15-apk-manifest.json').read_bytes(), 'GH_ARTIFACT_MANIFEST_DRIFT')
  for role in ('app','instrumentation'):
   name=arts[role]['file'];other=upstream/name
   need(other.is_file() and sha(other.read_bytes())==arts[role]['sha256'],
        'GH_ARTIFACT_BYTES_DRIFT_'+role)
 return manifest

def unpack_png_info(path,threshold=12):
 # stdlib strict PNG decoder. Validate signature, CRC, entire inflate stream and pixel diversity.
 raw=path.read_bytes();need(2048<len(raw)<40_000_000 and raw.startswith(b'\x89PNG\r\n\x1a\n'), 'PNG_SIGNATURE_'+path.name)
 offset=8;ids=[];ihdr=None;end=False
 while offset<len(raw):
  need(offset+12<=len(raw),'PNG_TRUNCATED')
  n=struct.unpack_from('>I',raw,offset)[0]
  need(n<40_000_000 and offset+12+n<=len(raw),'PNG_LENGTH')
  kind=raw[offset+4:offset+8];payload=raw[offset+8:offset+8+n]
  crc=struct.unpack_from('>I',raw,offset+8+n)[0]
  need(zlib.crc32(kind+payload)&0xffffffff==crc,'PNG_CRC')
  if kind==b'IHDR':
   need(ihdr is None and n==13,'PNG_DOUBLE_IHDR');ihdr=struct.unpack('>IIBBBBB',payload)
  elif kind==b'IDAT':ids.append(payload)
  elif kind==b'IEND':need(n==0 and offset+12==len(raw),'PNG_BAD_END');end=True
  offset+=12+n
 need(end and ids and ihdr,'PNG_STRUCTURE')
 w,h,depth,color,compression,filtermethod,interlace=ihdr
 need(320<=w<=4320 and 480<=h<=8192 and depth==8 and color in (2,6) and
      (compression,filtermethod,interlace)==(0,0,0),'PNG_UNSUPPORTED_FORMAT')
 bpp=3 if color==2 else 4;stride=w*bpp
 need(h*(stride+1)<=130_000_000,'PNG_TOO_LARGE')
 decoder=zlib.decompressobj();pixels=decoder.decompress(b''.join(ids),h*(stride+1)+1)+decoder.flush()
 need(decoder.eof and not decoder.unconsumed_tail and not decoder.unused_data and len(pixels)==h*(stride+1),'PNG_DECODE')
 prev=bytearray(stride);index=0;points=[];center=None
 xs=range(w//50,w*49//50,8)
 for y in range(h):
  filtertype=pixels[index]; row=bytearray(pixels[index+1:index+1+stride]);index+=stride+1
  need(filtertype in range(5),'PNG_FILTER')
  for i in range(stride):
   a=row[i-bpp] if i>=bpp else 0;b=prev[i];c=prev[i-bpp] if i>=bpp else 0
   if filtertype==1: row[i]=(row[i]+a)&255
   elif filtertype==2: row[i]=(row[i]+b)&255
   elif filtertype==3: row[i]=(row[i]+((a+b)//2))&255
   elif filtertype==4:
    p=a+b-c;da,db,dc=abs(p-a),abs(p-b),abs(p-c)
    row[i]=(row[i]+(a if da<=db and da<=dc else b if db<=dc else c))&255
  if y==h//2:center=tuple(row[(w//2)*bpp:(w//2)*bpp+3])
  if h//20<=y<h*9//10 and (y-h//20)%8==0:
   points.extend(tuple(row[x*bpp:x*bpp+3]) for x in xs)
  prev=row
 need(center is not None,'PNG_NO_CENTER')
 changed=sum(sum(abs(a-b) for a,b in zip(rgb,center))>=52 for rgb in points)
 colors=len(set(points))
 need(changed>=threshold and colors>=8,'PNG_BLANK_BODY_'+path.name+f'_changed_{changed}_colors_{colors}')
 return {'sha256':sha(raw),'width':w,'height':h,'bytes':len(raw),'body_changed_samples':changed,'sampled_colors':colors}

def screenshot_evidence(out):
 images={};dims=None;hashes=set()
 for filename in SHOTS:
  dest=out/'screenshots'/filename;dest.parent.mkdir(parents=True,exist_ok=True)
  # IMPORTANT: use binary ADB output, never text-recode PNG bytes.
  commandline=['adb','-s',SERIAL,'exec-out','run-as',PKG,'cat','files/'+filename]
  try:q=subprocess.run(commandline,capture_output=True,timeout=45)
  except (OSError,subprocess.TimeoutExpired) as ex:raise Refused('PNG_ADB_ERROR_'+str(ex)) from ex
  need(q.returncode==0,'MISSING_CAPTURE_'+filename)
  dest.write_bytes(q.stdout)
  data=unpack_png_info(dest,42 if filename.startswith('r4_p14_') else 12)
  now=(data['width'],data['height'])
  need(dims is None or dims==now,'MIXED_CAPTURE_DIMENSIONS')
  need(data['sha256'] not in hashes,'DUPLICATE_FRAME_'+filename)
  hashes.add(data['sha256']);dims=now;images[filename]=data
 need(len(images)==15,'MISSING_15_SCREENSHOTS')
 return images

def instrument(klass,label,expected,out,runner):
 log=out/'logs'/(label+'.txt');log.parent.mkdir(parents=True,exist_ok=True)
 cmd=['adb','-s',SERIAL,'shell','am','instrument','-w','-r','-e','class',klass,runner]
 print('P15_INSTRUMENT_BEGIN',label,expected,flush=True)
 selector=selectors.DefaultSelector()
 proc=None
 try:
  proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0)
  assert proc.stdout is not None
  selector.register(proc.stdout,selectors.EVENT_READ)
  deadline=time.monotonic()+840;chunks=[]
  with log.open('wb') as fh:
   while selector.get_map():
    need(time.monotonic()<deadline,'INSTRUMENT_TIMEOUT_'+label)
    events=selector.select(timeout=min(1,max(.1,deadline-time.monotonic())))
    for key,_ in events:
     chunk=os.read(key.fileobj.fileno(),65536)
     if not chunk:
      selector.unregister(key.fileobj)
      break
     chunks.append(chunk)
     fh.write(chunk);fh.flush()
     sys.stdout.buffer.write(chunk);sys.stdout.buffer.flush()
  rc=proc.wait(timeout=20)
 finally:
  selector.close()
  if proc is not None and proc.poll() is None:
   proc.terminate()
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
  if proc is not None and proc.stdout is not None:proc.stdout.close()
 body=log.read_text(errors='replace')
 suffix='test' if expected==1 else 'tests'
 need(rc==0 and re.search(r'(?m)^OK \('+str(expected)+' '+suffix+r'\)$',body) is not None and
     re.search(r'(?m)^INSTRUMENTATION_CODE: -1$',body) is not None and
     not re.search(r'FAILURES!!!|INSTRUMENTATION_FAILED|INSTRUMENTATION_STATUS_CODE: -2|Process crashed',body),
     'INSTRUMENT_FAILURE_'+label)
 print('P15_INSTRUMENT_PASS',label,expected,flush=True)


def run_physical(artifact_dir,out,ack):
 need(ack==AUTH,'EXPLICIT_DEVICE_WRITE_AUTHORIZATION_REQUIRED')
 need(not out.exists() or not any(out.iterdir()),'OUTPUT_DIR_ALREADY_USED')
 report=inspect_device();manifest=verify_artifact(artifact_dir)
 out.mkdir(parents=True,exist_ok=True)
 journal=out/'journal.json'
 record={'schema':1,'source_sha':manifest['source_sha'],'run_id':manifest['run_id'],
  'serial':SERIAL,'preflight':report,'owned_install_intent':[],
  'installed_by_this_run':[],'installed_package_paths':{},'phase':'PREFLIGHT_PASS',
  'cleanup':'NOT_STARTED','physical_arm64_qualified':False,'p14_physical_parity_pass':False,
  'release_qualified':False,
  'real_installer_prompt_decline_qualified':False,
  'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 json_save(journal,record)
 first=None
 try:
  for key,pkg in (('app',PKG),('instrumentation',TEST_PKG)):
   need(not packages_installed()[pkg],'OWNERSHIP_PRE_INSTALL_CHANGED')
   entry=manifest['apks'][key]; apk=artifact_dir/entry['file']
   need(sha(apk.read_bytes())==entry['sha256'],'APK_CHANGED_AFTER_PROVENANCE')
   record['owned_install_intent'].append(pkg);record['phase']='INSTALLING_'+key;json_save(journal,record)
   result=adb('install','--no-streaming',str(apk),check=False,timeout=180)
   need(result.returncode==0 and 'Success' in result.stdout,'APK_INSTALL_FAILED_'+key+'_'+(result.stdout+result.stderr)[-200:])
   need(packages_installed()[pkg],'APK_NOT_RECOGNIZED_'+key)
   record['installed_by_this_run'].append(pkg)
   record['installed_package_paths'][pkg]=list(package_paths()[pkg]);json_save(journal,record)
  ins=adb('shell','pm','list','instrumentation').stdout
  match=re.search(r'instrumentation:(\S+)\s+\(target='+re.escape(PKG)+r'\)',ins)
  need(match is not None and 'HiltInstrumentationTestRunner' in match.group(1),'HILT_RUNNER_NOT_FOUND')
  runner=match.group(1)
  record['phase']='INSTRUMENTATION';json_save(journal,record)
  for label,klass,count in SUITES:instrument(klass,label,count,out,runner)
  for method in WORKER_METHODS:
   instrument(WORKER+'#'+method,'worker-'+method,1,out,runner)
  images=screenshot_evidence(out)
  record.update(phase='ANDROID_32_OF_32_PASS',executions=32,screenshots=images)
  json_save(journal,record)
 except BaseException as e:
  first=e
  record['failure']=str(e)[:550];record['phase']='FAILED';json_save(journal,record)
 finally:
  # Never leave test APKs installed after success or ordinary failures.
  # Device state changes after a crash require explicit --cleanup with journal.
  errors=[]
  for pkg in reversed(record['owned_install_intent']):
   if pkg not in (PKG,TEST_PKG) or report['preexisting_packages'].get(pkg):
    errors.append('OWNERSHIP_REFUSED_'+pkg);continue
   present=package_paths()[pkg]
   if present:
    expected=tuple(record['installed_package_paths'].get(pkg,()))
    if pkg not in record['installed_by_this_run'] or not expected or present!=expected:
     errors.append('OWNERSHIP_PATH_NOT_PROVEN_'+pkg);continue
    x=adb('uninstall',pkg,check=False,timeout=100)
    if x.returncode or package_paths()[pkg]:errors.append('CLEANUP_FAILED_'+pkg)
  record['cleanup']='PASS_NO_TEST_APKS_REMAIN' if not errors else 'FAILED_'+','.join(errors)
  record['p14_physical_parity_pass']=bool(first is None and not errors and record.get('executions')==32 and len(record.get('screenshots',{}))==15)
  record['physical_arm64_qualified']=False  # The real OS prompt-decline gate is still pending.
  record['phase']='P15_PHYSICAL_P14_PARITY_PASS_MANUAL_INSTALLER_PENDING' if record['p14_physical_parity_pass'] else 'INCOMPLETE'
  json_save(journal,record)
  receipt=out/'receipt.json';json_save(receipt,record)
  if errors:raise Refused('CLEANUP_NOT_PROVEN_'+','.join(errors)) from first
 if first:raise first
 print('P15_PHYSICAL_32_OF_32_P14_PARITY_PASS_15_PNGS_CLEANUP_PASS',flush=True)
 print('P15_MANUAL_OS_INSTALLER_DECLINE_AND_RELEASE_NOT_QUALIFIED',flush=True)
 print('P15_RECEIPT',out/'receipt.json',flush=True)

def cleanup(out):
 journal=out/'journal.json'; need(journal.is_file(),'MISSING_OWNERSHIP_JOURNAL')
 record=json.loads(journal.read_text());need(record.get('schema')==1 and record.get('serial')==SERIAL,'BAD_JOURNAL')
 need(set(record.get('owned_install_intent',[]))<=set((PKG,TEST_PKG)),'OWNERSHIP_INVALID')
 need(not any(record['preflight']['preexisting_packages'].values()),'CANNOT_UNINSTALL_PREEXISTING_APPS')
 inspect_device(allow_existing=True)
 for pkg in reversed(record.get('owned_install_intent',[])):
  paths=package_paths()[pkg]
  if paths:
   expected=tuple(record.get('installed_package_paths',{}).get(pkg,()))
   need(pkg in record.get('installed_by_this_run',[]) and expected and paths==expected,
        'CLEANUP_OWNERSHIP_NOT_PROVEN_'+pkg)
   result=adb('uninstall',pkg,check=False,timeout=100)
   need(result.returncode==0 and not package_paths()[pkg], 'CLEANUP_'+pkg)
 record['cleanup']='PASS_NO_TEST_APKS_REMAIN';record['phase']='CLEANUP_ONLY_NOT_QUALIFIED'
 record['physical_arm64_qualified']=False
 record['p14_physical_parity_pass']=False
 json_save(journal,record)
 print('P15_CLEANUP_PASS_NO_TEST_APKS_REMAIN')

def main():
 parser=argparse.ArgumentParser(description='AuroraStore P15 — explicit physical ARM64 acceptance')
 op=parser.add_mutually_exclusive_group(required=True)
 op.add_argument('--preflight',action='store_true')
 op.add_argument('--run',action='store_true')
 op.add_argument('--cleanup',action='store_true')
 parser.add_argument('--serial',default=SERIAL)
 parser.add_argument('--artifact-dir',type=Path)
 parser.add_argument('--output',type=Path,default=Path('/sdcard/Download/AuroraStore-P15-physical'))
 parser.add_argument('--authorize',default='')
 args=parser.parse_args()
 try:
  need(args.serial==SERIAL,'ONLY_LOCALHOST_5555_SUPPORTED')
  if args.preflight:
   result=inspect_device();print(json.dumps(result,indent=2,sort_keys=True));print('P15_READ_ONLY_PREFLIGHT_PASS_NO_DEVICE_WRITES')
  elif args.run:
   need(args.artifact_dir is not None,'MISSING_HOSTED_APK_ARTIFACT_DIRECTORY')
   run_physical(args.artifact_dir,args.output,args.authorize)
  elif args.cleanup:cleanup(args.output)
 except (Refused,OSError,ValueError,KeyError,TypeError) as e:
  print('P15_REFUSED',str(e),file=sys.stderr,flush=True);raise SystemExit(2)
if __name__=='__main__':main()
