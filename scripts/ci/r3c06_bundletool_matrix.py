#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real bundletool device-targeting oracle, not an on-device trust adapter.

Requires an actual App Bundle, an explicitly SHA-256-pinned bundletool jar, and
Android SDK tooling. Refuses to certify absent ABI/density/locale/feature coverage.
Does not install apps, reinterpret unsigned toc.pb as signer trust, or touch Play.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

class Refused(Exception):pass

def check(ok,msg):
    if not ok:raise Refused(msg)

def cmd(*args,timeout=300,allow_fail=False):
    r=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=timeout)
    if r.returncode and not allow_fail:raise Refused('command failed '+str(args[:3])+': '+r.stderr[-1300:])
    return r

def filehash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def qualifies_variant(reference, candidate):
    """A failed bundletool selection is NOT compatibility coverage.

    We only measure changed, successfully extracted, cryptographically signed APK
    outputs from the same trusted bundletool invocation. Refusal is uncovered.
    """
    return (reference.get('status') == 'SIGNED' and
            candidate.get('status') == 'SIGNED' and
            bool(candidate.get('apks')) and bool(candidate.get('sha256')) and
            (reference.get('apks'), reference.get('sha256')) !=
            (candidate.get('apks'), candidate.get('sha256')))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--bundle',required=True)
    ap.add_argument('--bundletool-jar',required=True)
    ap.add_argument('--bundletool-sha256',required=True)
    ap.add_argument('--feature',action='append',default=[])
    ap.add_argument('--strict-dimensions',action='store_true')
    ap.add_argument('--receipt',required=True)
    args=ap.parse_args()
    bundle=Path(args.bundle); jar=Path(args.bundletool_jar)
    check(bundle.is_file() and jar.is_file(), 'real AAB or bundletool jar missing')
    check(len(args.bundletool_sha256)==64 and filehash(jar)==args.bundletool_sha256.lower(),
          'bundletool binary SHA-256 mismatch')
    check(bundle.suffix.lower()=='.aab', 'expected a real AAB')
    check(cmd('adb','shell','getprop','ro.build.version.sdk').stdout.strip()=='36','API36 emulator/device required')
    sdk=Path(os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT') or '')
    tools=sorted((sdk/'build-tools').glob('*'),reverse=True)
    tools=[t for t in tools if (t/'apksigner').is_file()]
    check(tools,'Android build tools/apksigner missing')
    apksigner=tools[0]/'apksigner'
    with tempfile.TemporaryDirectory(prefix='aurora-bundletool-matrix-',
         dir=os.environ.get('RUNNER_TEMP') or os.environ.get('TMPDIR') or None) as directory:
        tmp=Path(directory)
        # Fixture key signs only generated bundletool APKs; never use production keys.
        password='r3c06-matrix-only'
        ks=tmp/'fixture.p12'
        cmd('keytool','-genkeypair','-noprompt','-alias','fixture',
            '-keyalg','RSA','-keysize','2048','-validity','2','-storetype','PKCS12',
            '-dname','CN=R3C06 Matrix Test,O=Local CI',
            '-keystore',ks,'-storepass',password,'-keypass',password)
        base=['java','-jar',str(jar)]
        specfile=tmp/'device.json'
        cmd(*base,'get-device-spec','--output='+str(specfile),timeout=180)
        spec=json.loads(specfile.read_text())
        check(all(k in spec for k in ('sdkVersion','screenDensity','supportedAbis','supportedLocales')),
              'bundletool device-spec incomplete')
        archive=tmp/'fixture.apks'
        cmd(*base,'build-apks','--bundle='+str(bundle),'--output='+str(archive),
            '--ks='+str(ks),'--ks-pass=pass:'+password,
            '--ks-key-alias=fixture','--key-pass=pass:'+password,timeout=600)
        def extract(label,device,modules=None):
            target=tmp/(label+'.json');target.write_text(json.dumps(device))
            out=tmp/label; out.mkdir()
            command=base+['extract-apks','--apks='+str(archive),
                          '--device-spec='+str(target),'--output-dir='+str(out)]
            if modules:command+=['--modules='+','.join(modules)]
            result=cmd(*command,allow_fail=True,timeout=240)
            if result.returncode:return {'status':'REFUSED','apks':[], 'error_type':'bundletool refused targeting'}
            packages=sorted(out.rglob('*.apk'))
            check(packages, 'bundletool returned no APKs for '+label)
            for apk in packages:
                verified=cmd(apksigner,'verify','--verbose',apk).stdout
                check('Verified using v2 scheme (APK Signature Scheme v2): true' in verified,
                      'unsigned or invalid extracted split '+apk.name)
            return {'status':'SIGNED','apks':[p.name for p in packages],
                    'sha256':[filehash(p) for p in packages]}
        results={'device':extract('device',spec)}
        check(results['device']['status']=='SIGNED','no signed device selection')
        scenarios={
            'abi':{**spec,'supportedAbis':['x86_64'] if 'x86_64' not in spec['supportedAbis'] else ['arm64-v8a']},
            'density':{**spec,'screenDensity':160 if spec['screenDensity'] != 160 else 480},
            'locale':{**spec,'supportedLocales':['ja-JP'] if 'ja-JP' not in spec['supportedLocales'] else ['pt-BR']},
            'sdk':{**spec,'sdkVersion':28 if spec['sdkVersion']!=28 else 35},
        }
        coverage={}
        for key,modified in scenarios.items():
            candidate=extract(key,modified)
            results[key]=candidate
            coverage[key]=qualifies_variant(results['device'],candidate)
        for feature in args.feature:
            check(bool(feature) and feature.replace('_','').isalnum(), 'invalid feature name')
            result=extract('feature-'+feature,spec,[feature])
            results['feature-'+feature]=result
            coverage['feature-'+feature]=(result['status']=='SIGNED' and
                                          any(feature in n for n in result['apks']))
        # A test must not claim every dimension or feature if its AAB does not contain them.
        all_covered=all(coverage.get(k,False) for k in ('abi','density','locale','sdk')) and bool(args.feature) and \
            all(coverage.get('feature-'+f,False) for f in args.feature)
        if args.strict_dimensions:check(all_covered,'fixture does not cover every requested targeting/feature dimension')
        receipt={'overall':'PASS' if all_covered else 'PARTIAL',
                 'bundle_sha256':filehash(bundle),'bundletool_sha256':filehash(jar),
                 'refused_targeting_does_not_count_as_coverage':True,
                 'source_sha':os.environ.get('GITHUB_SHA',''),
                 'android_api':36,'device_spec':spec,'coverage':coverage,
                 'results':results,'publisher_authenticated':False,
                 'aurora_install_qualified':False,'physical_qualified':False}
        output=Path(args.receipt);output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
        print('R3C06_BUNDLETOOL_'+receipt['overall']+' receipt='+str(output))

if __name__=='__main__':
    try: main()
    except (Refused,subprocess.TimeoutExpired,OSError,ValueError) as error:
        print('R3C06_BUNDLETOOL_REFUSED: '+str(error),file=sys.stderr)
        raise SystemExit(2)
