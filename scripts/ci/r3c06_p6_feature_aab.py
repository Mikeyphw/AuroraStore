#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Check actual Gradle-built on-demand fixture AAB using pinned official bundletool.

Only proves isolated fixture structure. It does not install, sign, or edit Aurora.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

from r3c06_p5_manual_receipt import OFFICIAL_BUNDLETOOL_SHA256 as JAR_SHA

DIST = '{http://schemas.android.com/apk/distribution}'
MARKER = b'R3C06_FEATUREPROOF_ON_DEMAND_FIXTURE_ONLY\n'
PACKAGE = 'com.aurora.r3c06.featurefixture'

class Refused(RuntimeError): pass

def require(test, reason):
    if not test: raise Refused(reason)

def digest(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for block in iter(lambda: f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def check_xml(xml):
    root=ET.fromstring(xml)
    module=root.find(DIST+'module')
    require(module is not None, 'featureproof dist:module missing from actual AAB')
    delivery=module.find(DIST+'delivery')
    require(delivery is not None and delivery.find(DIST+'on-demand') is not None,
            'actual AAB feature is NOT on demand')
    require(delivery.find(DIST+'install-time') is None,'feature is install-time, not on-demand')
    fusing=module.find(DIST+'fusing')
    require(fusing is not None and fusing.get(DIST+'include')=='false',
            'feature fusing policy differs from pinned fixture')
    return True

def inspect(bundle,jar,source_sha,run_id):
    bundle=Path(bundle);jar=Path(jar)
    require(bundle.is_file() and bundle.suffix=='.aab' and not bundle.is_symlink(),
            'isolated AAB missing/unsafe')
    require(jar.is_file() and digest(jar)==JAR_SHA, 'official bundletool SHA mismatch')
    require(len(source_sha)==40 and all(c in '0123456789abcdef' for c in source_sha),
            'invalid source pin')
    require(run_id.isdecimal(), 'missing hosted run identity')
    with zipfile.ZipFile(bundle) as z:
        names=z.namelist()
        require(len(names)==len(set(names)),'duplicate AAB member')
        require('base/manifest/AndroidManifest.xml' in names and
                'featureproof/manifest/AndroidManifest.xml' in names,
                'real base and dynamic feature modules not both present in AAB')
        marker=[n for n in names if n.endswith('/assets/qualification.marker')]
        require(marker==['featureproof/assets/qualification.marker'],
                'feature marker absent or unexpectedly copied into base')
        require(z.read(marker[0])==MARKER, 'on-demand asset bytes differ')
    # Official bundletool `dump manifest` writes XML to STDOUT; it does not
    # support --output. Never infer on-demand status from source XML alone.
    r=subprocess.run(['java','-jar',str(jar),'dump','manifest',
                      '--bundle='+str(bundle),'--module=featureproof'],
                     capture_output=True,text=True,timeout=180)
    require(r.returncode==0 and '<manifest' in r.stdout,
            'official bundletool did not dump feature manifest '+r.stderr[-400:])
    check_xml(r.stdout)
    b=subprocess.run(['java','-jar',str(jar),'dump','manifest',
                      '--bundle='+str(bundle),'--module=base'],
                     capture_output=True,text=True,timeout=180)
    require(b.returncode==0 and '<manifest' in b.stdout,
            'official bundletool base manifest absent '+b.stderr[-400:])
    root=ET.fromstring(b.stdout)
    require(root.get('package')==PACKAGE, 'unexpected fixture package ID')
    return {'overall':'PASS','source_sha':source_sha,'run_id':run_id,
            'android_api':36,'module':'featureproof', 'on_demand':True,
            'fusing_disabled':True,'feature_marker_verified':True,
            'fixture_package':PACKAGE,'bundle_sha256':digest(bundle),
            'bundletool_sha256':JAR_SHA,'publisher_authenticated':False,
            'production_aab_modified':False,'aurora_install_qualified':False,
            'physical_device_qualified':False,'release_qualified':False}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--bundle',required=True)
    ap.add_argument('--bundletool-jar',required=True)
    ap.add_argument('--receipt',type=Path,required=True)
    args=ap.parse_args()
    result=inspect(args.bundle,args.bundletool_jar,
                   os.environ.get('GITHUB_SHA',''),os.environ.get('GITHUB_RUN_ID',''))
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    args.receipt.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print('R3C06_P6_FEATURE_AAB_MANIFEST_PASS sha='+result['source_sha'])

if __name__=='__main__':
    try:main()
    except (Refused,OSError,ValueError,ET.ParseError,zipfile.BadZipFile,subprocess.TimeoutExpired) as e:
        print('R3C06_P6_FEATURE_AAB_REFUSED: '+str(e),file=sys.stderr)
        raise SystemExit(2)
