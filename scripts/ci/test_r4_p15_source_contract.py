#!/usr/bin/env python3
"""P15 adversarial source, device authorization and actual PNG decode checks."""
from pathlib import Path
import io,importlib,sys,tempfile,subprocess,struct,zlib,json,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import r4_p15_source_contract as c
import r4_p15_physical_acceptance as physical
ROOT=Path(__file__).resolve().parents[2]

def refuses(call,part):
 try:call()
 except (c.Refused,physical.Refused) as e:assert part in str(e),(part,str(e))
 else:raise AssertionError('P15_UNCAUGHT_NEGATIVE_'+part)

def source_mutations():
 assert c.source_only(ROOT)
 d=(ROOT/c.DEVICE).read_text();w=(ROOT/c.WF).read_text();a=(ROOT/c.ARTIFACT).read_text()
 changes=[
  (c.check_device,d.replace("SERIAL='localhost:5555'","SERIAL='emulator-5554'"),'DEVICE_MISSING_'),
  (c.check_device,d.replace("AUTH='I_AUTHORIZE_P15_TEST_APK_INSTALLS'","AUTH=''"),'DEVICE_MISSING_'),
  (c.check_device,d.replace("'ro.build.version.sdk'","'ro.build.version.codename'"),'DEVICE_MISSING_'),
  (c.check_device,d.replace("'ro.product.cpu.abi'","'ro.build.characteristics'"),'DEVICE_MISSING_'),
  (c.check_device,d.replace("'ro.kernel.qemu'","'ro.kernel.other'"),'DEVICE_MISSING_'),
  (c.check_device,d.replace("'arm64-v8a'","'x86_64'"),'DEVICE_MISSING_'),
  (c.check_device,d.replace("need(not any(packages.values())","need(any(packages.values())"),'DEVICE_MISSING_'),
  (c.check_device,d.replace("'owned_install_intent'","'untracked_install'"),'DEVICE_MISSING_'),
  (c.check_device,d.replace("'installed_by_this_run'","'untracked_packages'"),'DEVICE_MISSING_'),
  (c.check_device,d.replace("'release_qualified'","'released'"),'DEVICE_MISSING_'),
  (c.check_device,d.replace('def cleanup(out):','def skip_cleanup(out):'),'DEVICE_MISSING_'),
  (c.check_device,d.replace('def screenshot_evidence(out):','def skip_screenshots(out):'),'DEVICE_MISSING_'),
  (c.check_device,d.replace('selector.select(','selector.poll('),'DEVICE_MISSING_'),
  (c.check_device,d.replace("INSTRUMENTATION_CODE: -1","INSTRUMENTATION_CODE: 1"),'DEVICE_MISSING_'),
  (c.check_device,d.replace('I_AUTHORIZE_P15_TEST_APK_INSTALLS','I_ACCEPT_ALL_INSTALLS'),'DEVICE_MISSING_'),
  (c.check_device,d.replace('P15_MANUAL_OS_INSTALLER_DECLINE_AND_RELEASE_NOT_QUALIFIED','P15_ALL_RELEASED'),'DEVICE_MISSING_'),
  (c.check_device,d+'\n# su -c','UNAUTHORIZED_DEVICE_MUTATION_'),
  (c.check_device,d+'\n# adb root','UNAUTHORIZED_DEVICE_MUTATION_'),
  (c.check_device,d+'\n# wm density reset','UNAUTHORIZED_DEVICE_MUTATION_'),
  (c.check_device,d+'\n# gh workflow run','UNAUTHORIZED_DEVICE_MUTATION_'),
  (c.check_manifest,a.replace("'aapt'","'fake_aapt'"),'MANIFEST_MARKER_'),
  (c.check_manifest,a.replace("'apksigner'","'skip_signing'"),'MANIFEST_MARKER_'),
  (c.check_manifest,a.replace("'physical_qualified':False","'physical_qualified':True"),'MANIFEST_MARKER_'),
  (c.check_manifest,a.replace("'release_qualified':False","'release_qualified':True"),'MANIFEST_MARKER_'),
  (c.check_manifest,a.replace('P15_DEVICE_INSTALLS_NOT_EXECUTED','P15_INSTALLS_DONE'),'MANIFEST_MARKER_'),
  (c.check_workflow,w.replace('  contents: read','  contents: write'),'WF_MARKER_'),
  (c.check_workflow,w.replace('persist-credentials: false','persist-credentials: true'),'WF_MARKER_'),
  (c.check_workflow,w.replace('git diff --check '+c.BASE+' HEAD','true'),'WF_MARKER_'),
  (c.check_workflow,w.replace(':app:assembleVanillaDebugAndroidTest',':app:assembleVanillaRelease'),'WF_MARKER_'),
  (c.check_workflow,w+'\n# adb install','WORKFLOW_DEVICE_EXECUTION_'),
 ]
 for i,(fun,modified,reason) in enumerate(changes):
  try:refuses(lambda:fun(modified),reason)
  except Exception as e:raise AssertionError(f"MUTATION {i} {e}") from e
 print('P15_SOURCE_NEGATIVE_MUTATIONS_PASS',len(changes))
 return len(changes)

def safety_mock_tests():
 class Result:
  def __init__(self,s='',rc=0):self.stdout=s;self.stderr='';self.returncode=rc
 original_adb=physical.adb;original_which=physical.shutil.which
 facts={'sdk':'36','abi':'arm64-v8a','qemu':'','hardware':'mt6785','existing':set()}
 requests=[]
 def mock_adb(*args,**kwargs):
  requests.append(args)
  if args==('get-state',):return Result('device\n')
  if args[:2]==('shell','getprop'):
   m={'ro.build.version.sdk':facts['sdk'],'ro.product.cpu.abi':facts['abi'],
      'ro.kernel.qemu':facts['qemu'],'ro.hardware':facts['hardware'],
      'sys.boot_completed':'1'}
   return Result(m[args[2]]+'\n')
  if args[:3]==('shell','pm','path'):
   return Result('package:/data/app/fake/base.apk\n' if args[-1] in facts['existing'] else '')
  raise AssertionError('UNAUTHORIZED_ADB_CALL_'+repr(args))
 try:
  physical.adb=mock_adb
  physical.shutil.which=lambda key:'/usr/bin/mock'
  result=physical.inspect_device();assert result['api']==36 and not any(result['preexisting_packages'].values())
  assert all(x==('get-state',) or x[:2]==('shell','getprop') or x[:3]==('shell','pm','path') for x in requests)
  # No acknowledgement must refuse BEFORE reading any device or artifact.
  before=len(requests);refuses(lambda:physical.run_physical(Path('/nonexistent'),Path('/tmp/out'),''),'EXPLICIT_DEVICE_WRITE_AUTHORIZATION_REQUIRED')
  assert len(requests)==before
  facts['qemu']='1';refuses(physical.inspect_device,'EMULATOR_REFUSED');facts['qemu']=''
  facts['abi']='x86_64';refuses(physical.inspect_device,'NOT_PHYSICAL_ARM64');facts['abi']='arm64-v8a'
  facts['sdk']='35';refuses(physical.inspect_device,'ANDROID_API_NOT_36');facts['sdk']='36'
  facts['existing']={physical.PKG};refuses(physical.inspect_device,'PREEXISTING_AURORA_APP_OR_TEST_DONOT_OVERWRITE');facts['existing']=set()
  print('P15_PHYSICAL_READ_ONLY_MOCK_PREFLIGHT_PASS 5')
 finally:
  physical.adb=original_adb;physical.shutil.which=original_which

def make_png(path,blank=False):
 w,h=320,480
 rows=[]
 for y in range(h):
  if blank:pixels=bytes([30,30,30])*w
  else:pixels=b''.join(bytes(((x*5+y*3)%256,(x*2+y*7)%256,(x*4+y)%256)) for x in range(w))
  rows.append(b'\0'+pixels)
 raw=b''.join(rows)
 def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
 path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+
                   chunk(b'tEXt',b'pad='+b'x'*2200)+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))

def png_mutations():
 with tempfile.TemporaryDirectory(prefix='p15-png-negative-') as d:
  a=Path(d)/'valid.png';make_png(a)
  report=physical.unpack_png_info(a,12);assert report['width']==320 and report['body_changed_samples']>12
  blank=Path(d)/'blank.png';make_png(blank,True);refuses(lambda:physical.unpack_png_info(blank,12),'PNG_BLANK_BODY_')
  broken=Path(d)/'corrupt.png';data=bytearray(a.read_bytes());data[-8]^=17;broken.write_bytes(data)
  refuses(lambda:physical.unpack_png_info(broken,12),'PNG_CRC')
  print('P15_PNG_NONBLANK_AND_CRC_NEGATIVE_PASS 3')


def device_transaction_mock():
 # Exercise actual two-APK ownership/rollback code with NO ADB executable used.
 import types
 with tempfile.TemporaryDirectory(prefix='p15-device-transaction-') as d:
  root=Path(d);art=root/'apks';art.mkdir()
  bodies={'app':b'app-test-payload','instrumentation':b'instrumentation-test-payload'}
  names={'app':'aurora-p15-app.apk','instrumentation':'aurora-p15-androidTest.apk'}
  for role,data in bodies.items():(art/names[role]).write_bytes(data)
  manifest={'source_sha':'a'*40,'run_id':'1234',
            'apks':{role:{'file':names[role],'sha256':hashlib.sha256(data).hexdigest()}
                    for role,data in bodies.items()}}
  kept={};installed=[];writes=[];calls=[]
  original={name:getattr(physical,name) for name in
    ('inspect_device','verify_artifact','packages_installed','package_paths','adb','instrument','screenshot_evidence')}
  def state():return {physical.PKG:bool(kept.get(physical.PKG)),physical.TEST_PKG:bool(kept.get(physical.TEST_PKG))}
  def mock_adb(*args,**kwargs):
   calls.append(args)
   if args[0]=='install':
    pkg=physical.PKG if 'aurora-p15-app.apk' in args[-1] else physical.TEST_PKG
    kept[pkg]=('/data/app/p15-test-'+pkg+'/base.apk',)
    installed.append(pkg);writes.append(('install',pkg))
    return types.SimpleNamespace(returncode=0,stdout='Success',stderr='')
   if args[0]=='uninstall':
    pkg=args[1];kept.pop(pkg,None);writes.append(('uninstall',pkg))
    return types.SimpleNamespace(returncode=0,stdout='Success',stderr='')
   if args[:3]==('shell','pm','list'):
    return types.SimpleNamespace(returncode=0,stdout='instrumentation:com.aurora.store.debug.test/com.aurora.store.HiltInstrumentationTestRunner (target=com.aurora.store.debug)',stderr='')
   raise AssertionError('UNEXPECTED_DEVICE_MOCK_COMMAND_'+repr(args))
  try:
   physical.inspect_device=lambda allow_existing=False: {'preexisting_packages':{physical.PKG:False,physical.TEST_PKG:False},'api':36}
   physical.verify_artifact=lambda _:manifest
   physical.packages_installed=state
   physical.package_paths=lambda:{pkg:tuple(kept.get(pkg,())) for pkg in (physical.PKG,physical.TEST_PKG)}
   physical.adb=mock_adb
   physical.instrument=lambda *args: calls.append(('test',args[1]))
   physical.screenshot_evidence=lambda out:{name:{'sha256':str(i).zfill(64)} for i,name in enumerate(physical.SHOTS)}
   physical.run_physical(art,root/'success',physical.AUTH)
   receipt=json.loads((root/'success/receipt.json').read_text())
   assert len([x for x in writes if x[0]=='install'])==2
   assert len([x for x in writes if x[0]=='uninstall'])==2
   assert not kept and receipt['p14_physical_parity_pass'] is True
   assert receipt['physical_arm64_qualified'] is False
   assert receipt['real_installer_prompt_decline_qualified'] is False
   assert receipt['cleanup']=='PASS_NO_TEST_APKS_REMAIN'
   kept.clear();writes.clear();calls.clear()
   def fail(*args):raise physical.Refused('SIMULATED_DEVICE_TEST_FAILURE')
   physical.instrument=fail
   refuses(lambda:physical.run_physical(art,root/'failure',physical.AUTH),'SIMULATED_DEVICE_TEST_FAILURE')
   failed=json.loads((root/'failure/receipt.json').read_text())
   assert not kept and failed['p14_physical_parity_pass'] is False
   assert failed['cleanup']=='PASS_NO_TEST_APKS_REMAIN'
   assert len([x for x in writes if x[0]=='uninstall'])==2
   # Journal-based recovery must never uninstall an app whose APK path changed.
   changed=root/'recovery';changed.mkdir()
   record=json.loads((root/'success/journal.json').read_text())
   record['owned_install_intent']=[physical.PKG]
   record['installed_by_this_run']=[physical.PKG]
   physical.json_save(changed/'journal.json',record)
   kept[physical.PKG]=('/data/app/other-install/base.apk',)
   before=len(writes)
   refuses(lambda:physical.cleanup(changed),'CLEANUP_OWNERSHIP_NOT_PROVEN_')
   assert len(writes)==before
  finally:
   for name,func in original.items():setattr(physical,name,func)
 print('P15_TEST_OWNED_APK_TRANSACTION_CLEANUP_AND_REFUSAL_MOCK_PASS 3')


def artifact_provenance_mock():
 # Physical run must reject local APK+manifest forgery by comparison with a
 # separately fetched exact-SHA green GitHub Actions artifact.
 import shutil,types
 with tempfile.TemporaryDirectory(prefix='p15-attestation-mock-') as tmp:
  work=Path(tmp);canonical=work/'canonical';local=work/'local'
  canonical.mkdir();local.mkdir()
  files={'app':('aurora-p15-app.apk',b'A'*5000),
         'instrumentation':('aurora-p15-androidTest.apk',b'B'*5000)}
  source='a'*40;run='1234';name=f'aurora-r4-p15-apks-{source}-{run}-1'
  m={'schema':1,'repo':physical.REPO,'source_sha':source,'run_id':run,
     'run_attempt':1,'app_package':physical.PKG,'test_package':physical.TEST_PKG,
     'android_tests':32,'expected_screenshots':15,
     'apks':{role:{'file':n,'sha256':hashlib.sha256(b).hexdigest(),
                   'signer_sha256':'f'*64} for role,(n,b) in files.items()}}
  for role,(n,b) in files.items():
   (canonical/n).write_bytes(b);(local/n).write_bytes(b)
  raw=json.dumps(m,sort_keys=True,indent=2)+'\n'
  (canonical/'p15-apk-manifest.json').write_text(raw)
  (local/'p15-apk-manifest.json').write_text(raw)
  prior={x:getattr(physical,x) for x in ('gh_api','command','shutil')}
  facts={'head':source,'targeted':True}
  def fake_api(endpoint):
   if endpoint=='actions/runs/'+run:return {'head_sha':source,'status':'completed','conclusion':'success','name':physical.RUN_WORKFLOW}
   if endpoint.startswith('git/ref/'):return {'object':{'sha':facts['head']}}
   if endpoint.startswith('actions/runs?'):
    return {'workflow_runs':[{'head_sha':source,'name':'Aurora — Targeted CI',
      'conclusion':'success'}] if facts['targeted'] else []}
   if endpoint=='actions/runs/'+run+'/artifacts?per_page=100':
    return {'artifacts':[{'name':name,'expired':False}]}
   raise AssertionError('UNEXPECTED_GITHUB_ENDPOINT_'+endpoint)
  def fake_command(argv,**kw):
   assert argv[:3]==['gh','run','download']
   destination=Path(argv[-1]);destination.mkdir(parents=True,exist_ok=True)
   for f in canonical.iterdir():shutil.copyfile(f,destination/f.name)
   return types.SimpleNamespace(returncode=0,stdout='',stderr='')
  try:
   physical.gh_api=fake_api;physical.command=fake_command
   physical.shutil.which=lambda x:'/usr/bin/fake'
   assert physical.verify_artifact(local)['source_sha']==source
   facts['head']='b'*40
   refuses(lambda:physical.verify_artifact(local),'P15_BRANCH_HEAD_CHANGED')
   facts['head']=source;facts['targeted']=False
   refuses(lambda:physical.verify_artifact(local),'P15_TARGETED_CI_NOT_GREEN_FOR_SOURCE')
   facts['targeted']=True
   (local/'aurora-p15-app.apk').write_bytes(b'evil'+b'A'*4996)
   m['apks']['app']['sha256']=hashlib.sha256((local/'aurora-p15-app.apk').read_bytes()).hexdigest()
   (local/'p15-apk-manifest.json').write_text(json.dumps(m,sort_keys=True,indent=2)+'\n')
   refuses(lambda:physical.verify_artifact(local),'GH_ARTIFACT_MANIFEST_DRIFT')
   print('P15_GITHUB_APK_BYTES_AND_GREEN_BRANCH_MOCK_PASS 4')
  finally:
   for key,old in prior.items():setattr(physical,key,old)

def main():
 source_mutations();safety_mock_tests();png_mutations();device_transaction_mock();artifact_provenance_mock()
 print('P15_DEVICE_TESTS_NOT_RUN_NO_LOCAL_GRADLE_NO_ADB_WRITES')
if __name__=='__main__':main()
