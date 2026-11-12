#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build and independently inspect disposable Android fixture APKs (hosted SDK only).

No Android Gradle build is required. Generated ephemeral keys are deliberately NOT
committed, published or suitable for release signing.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

PACKAGE = 'com.aurora.r3d.fixture.history'
SOURCE = Path(__file__).resolve().parent/'fixtures/r3d_p03/CanaryReceiver.java'


def require(ok, message):
    if not ok: raise RuntimeError('R3D_P03_FIXTURE_REFUSED '+message)


def run(args, *, cwd=None):
    p = subprocess.run([str(x) for x in args], cwd=cwd, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
    require(p.returncode == 0, 'command failed '+str(args[:2])+' '+p.stdout[-1200:])
    return p.stdout


def tool(root, binary):
    selected = root/'build-tools/35.0.0'/binary
    require(selected.is_file(), 'exact Android SDK build-tools 35.0.0 missing binary '+binary)
    return selected


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest(version):
    # The receiver is exported only in a disposable APK on a clean emulator.
    return f'''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="{PACKAGE}" android:versionCode="{version}" android:versionName="{version}.0">
    <uses-sdk android:minSdkVersion="23" android:targetSdkVersion="28" />
    <application android:hasCode="true" android:debuggable="true"
        android:label="R3D disposable Android fixture" android:allowBackup="false">
        <receiver android:name=".CanaryReceiver" android:enabled="true"
            android:exported="true">
            <intent-filter><action android:name="{PACKAGE}.CANARY" /></intent-filter>
        </receiver>
    </application>
</manifest>
'''


def build(args):
    sdk = Path(os.environ.get('ANDROID_SDK_ROOT') or os.environ.get('ANDROID_HOME') or '')
    require(sdk.is_dir() and sdk != Path('.'), 'SDK_ROOT required on hosted runner')
    platform = sdk/'platforms/android-36/android.jar'
    require(platform.is_file(), 'API36 platform required')
    aapt2, d8, align, signer = (tool(sdk, x) for x in ('aapt2','d8','zipalign','apksigner'))
    out = Path(args.out).resolve()
    require(not out.exists(), 'output path must not already exist')
    out.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix='r3d-p03-build-') as dirname:
        temp = Path(dirname)
        cls = temp/'classes'
        cls.mkdir()
        run(['javac', '-source', '8', '-target', '8', '-classpath', platform,
             '-d', cls, SOURCE])
        dex = temp/'dex'
        dex.mkdir()
        run([d8, '--min-api', '23', '--lib', platform, '--output', dex,
             *sorted(cls.rglob('*.class'))])
        require((dex/'classes.dex').is_file(), 'missing generated classes.dex')
        certs = {}
        for key in ('matching', 'mismatched'):
            keystore = temp/(key+'.jks')
            run(['keytool','-genkeypair','-noprompt','-alias','r3d'+key,
                 '-keyalg','RSA','-keysize','3072','-validity','2',
                 '-dname','CN=R3D Disposable Test Only,OU=Emulator QA,O=Aurora',
                 '-keystore',keystore,'-storepass','changeit','-keypass','changeit'])
            certs[key] = keystore
        configs = (('v1',1,'matching'), ('v2',2,'matching'), ('v3_wrong_signer',3,'mismatched'))
        apks = {}
        for name, version, key in configs:
            mf = temp/(name+'-AndroidManifest.xml')
            mf.write_text(manifest(version), encoding='utf-8')
            unsigned = temp/(name+'-unsigned.apk')
            run([aapt2, 'link', '-o', unsigned, '-I', platform,
                 '--manifest', mf, '--min-sdk-version', '23', '--target-sdk-version', '28',
                 '--version-code', str(version), '--version-name', str(version)+'.0'])
            with zipfile.ZipFile(unsigned,'a') as archive:
                archive.write(dex/'classes.dex','classes.dex',compress_type=zipfile.ZIP_DEFLATED)
            aligned = temp/(name+'-aligned.apk')
            run([align, '-f', '4', unsigned, aligned])
            dest = out/(name+'.apk')
            run([signer,'sign','--ks',certs[key], '--ks-key-alias','r3d'+key,
                 '--ks-pass','pass:changeit','--key-pass','pass:changeit',
                 '--out',dest,aligned])
            ver = run([signer,'verify','--verbose','--print-certs',dest])
            m = re.search(r"Signer #1 certificate SHA-256 digest:\s*([0-9a-fA-F]{64})", ver)
            require(m is not None, 'signed certificate SHA-256 missing')
            pkg_dump = run([aapt2,'dump','badging',dest])
            exact = re.search(r"package: name='([^']+)' versionCode='(\d+)'",pkg_dump)
            require(exact is not None and exact.group(1)==PACKAGE and int(exact.group(2))==version,
                    'manifest package/version mismatch '+name)
            apks[name]={'file':dest.name,'sha256':digest(dest),
                        'bytes':dest.stat().st_size,'version_code':version,
                        'signing_certificate_sha256':m.group(1).lower(), 'package':PACKAGE}
        require(apks['v1']['signing_certificate_sha256']==apks['v2']['signing_certificate_sha256'],
                'v1 and v2 must share signer')
        require(apks['v1']['signing_certificate_sha256']!=apks['v3_wrong_signer']['signing_certificate_sha256'],
                'negative control must use different signer')
        manifest_file = out/'fixtures.json'
        manifest_file.write_text(json.dumps({'schema':1,'package':PACKAGE,
            'fixture_scope':'DISPOSABLE_ONLY','production_signature':False,
            'hosted_build_only':True,'android_api':36,'build_tools':'35.0.0','apks':apks}, indent=2,sort_keys=True)+'\n')
    print('R3D_P03_EPHEMERAL_DISPOSABLE_APKS_BUILT signer_continuity=true signer_mismatch=true')


def verify(folder):
    base=Path(folder).resolve()
    payload=json.loads((base/'fixtures.json').read_text())
    require(payload.get('schema')==1 and payload.get('package')==PACKAGE and
            payload.get('fixture_scope')=='DISPOSABLE_ONLY' and
            payload.get('production_signature') is False and
            payload.get('android_api') == 36 and payload.get('build_tools') == '35.0.0',
            'invalid fixture manifest scope')
    aps=payload.get('apks',{})
    require(set(aps)=={'v1','v2','v3_wrong_signer'},'missing or extra fixture APKs')
    for name,ver in [('v1',1),('v2',2),('v3_wrong_signer',3)]:
        item=aps[name]
        require(item['file']==name+'.apk' and item['version_code']==ver and
                item['package']==PACKAGE,'fixture identity mismatch '+name)
        file=base/item['file']
        require(file.is_file() and not file.is_symlink() and
                file.stat().st_size==item['bytes'] and digest(file)==item['sha256'],
                'fixture byte integrity mismatch '+name)
    require(aps['v1']['signing_certificate_sha256']==aps['v2']['signing_certificate_sha256'] and
            aps['v1']['signing_certificate_sha256']!=aps['v3_wrong_signer']['signing_certificate_sha256'],
            'fixture certificate continuity violation')
    # The manifest is a claim, not proof. Verify the actual ZIP signatures and
    # Android manifest identities *again* immediately before device execution.
    sdk = Path(os.environ.get('ANDROID_SDK_ROOT') or os.environ.get('ANDROID_HOME') or '')
    require(sdk.is_dir() and sdk != Path('.'), 'Android SDK needed to verify signed fixture bytes')
    signer, aapt2 = tool(sdk,'apksigner'), tool(sdk,'aapt2')
    for name, version in [('v1',1),('v2',2),('v3_wrong_signer',3)]:
        apk = base/(name+'.apk')
        signed = run([signer,'verify','--verbose','--print-certs',apk])
        match = re.search(r'Signer #1 certificate SHA-256 digest:\s*([0-9a-fA-F]{64})',signed)
        require(match is not None and match.group(1).lower() ==
                aps[name]['signing_certificate_sha256'],
                'actual APK signature no longer matches signed fixture manifest '+name)
        actual = run([aapt2,'dump','badging',apk])
        match = re.search(r"package: name='([^']+)' versionCode='(\d+)'", actual)
        require(match is not None and match.group(1)==PACKAGE and int(match.group(2))==version,
                'actual APK signed manifest package/version changed '+name)
    return payload


def main():
    ap=argparse.ArgumentParser()
    sub=ap.add_subparsers(dest='action',required=True)
    b=sub.add_parser('build');b.add_argument('--out',required=True)
    v=sub.add_parser('verify');v.add_argument('--dir',required=True)
    args=ap.parse_args()
    if args.action=='build':build(args)
    elif args.action=='verify':verify(args.dir);print('R3D_P03_FIXTURE_DIGESTS_PASS')

if __name__=='__main__':main()
