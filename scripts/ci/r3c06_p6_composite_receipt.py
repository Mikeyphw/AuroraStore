#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent R3C06 composite targeting receipt: production AAB + on-demand fixture.

A PASS means TWO real AABs were separately matrix-tested on one hosted API36
runner. It NEVER means Aurora's shipping AAB contains a feature, nor publisher,
Play, physical, release, live installation, or real vendor archive acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import r3c06_p5_manual_receipt as p5

SHA = re.compile(r'[0-9a-f]{40}\Z')
HEX = re.compile(r'[0-9a-f]{64}\Z')
DIMS = ('abi','density','locale','sdk')
FEATURE = 'featureproof'
FEATURE_KEY = 'feature-'+FEATURE

class Refused(RuntimeError): pass

def require(ok,reason):
    if not ok: raise Refused(reason)

def load(path):
    p=Path(path)
    require(p.is_file() and not p.is_symlink(),'required evidence file missing/unsafe: '+str(p))
    doc=json.loads(p.read_text(encoding='utf-8'))
    require(isinstance(doc,dict),'receipt not an object')
    return doc

def selected(doc,key):
    val=doc['results'][key]
    require(val['status']=='SIGNED' and val.get('apks') and
            len(val['apks'])==len(val.get('verified_apks',[])),
            'unsigned or incomplete selected split: '+key)
    return val

def attest(production,feature,manifest,expected_sha,run_id):
    require(bool(SHA.fullmatch(expected_sha)) and run_id.isdecimal(),
            'exact source SHA and numeric run ID required')
    for label,doc in (('production',production),('feature',feature)):
        try:
            p5.validate_bundletool(doc,expected_sha,run_id)
        except (p5.QualificationRefused,KeyError,TypeError,ValueError) as e:
            raise Refused(label+' matrix evidence invalid: '+str(e)) from e
        require(doc['android_api']==36 and doc.get('publisher_authenticated') is False and
                doc.get('aurora_install_qualified') is False and
                doc.get('physical_qualified') is False,
                label+' claimed unsupported scope')
    for f in ('source_sha','run_id'):
        require(manifest.get(f)==(expected_sha if f=='source_sha' else run_id),
                'feature AAB inspection not run-bound: '+f)
    require(manifest.get('overall')=='PASS' and manifest.get('on_demand') is True and
            manifest.get('fusing_disabled') is True and
            manifest.get('feature_marker_verified') is True and
            manifest.get('fixture_package')=='com.aurora.r3c06.featurefixture' and
            manifest.get('module')==FEATURE and
            manifest.get('publisher_authenticated') is False and
            manifest.get('production_aab_modified') is False and
            manifest.get('aurora_install_qualified') is False and
            manifest.get('physical_device_qualified') is False and
            manifest.get('release_qualified') is False,
            'feature AAB dump/marker evidence incomplete or overclaimed')
    require(manifest.get('bundletool_sha256')==p5.OFFICIAL_BUNDLETOOL_SHA256 and
            manifest.get('bundle_sha256')==feature.get('bundle_sha256'),
            'feature manifest and signed matrix used different AAB or tool')
    require(production.get('device_spec')==feature.get('device_spec'),
            'real API36 device specifications differ between fixture and production')
    require(set(production['coverage'])==set(DIMS),
            'production matrix must report precisely four measured dimensions')
    require(all(production['coverage'][k] is True for k in DIMS),
            'production AAB has missing real ABI/density/locale/SDK coverage')
    require(set(feature['coverage'])==set(DIMS)|{FEATURE_KEY},
            'isolated fixture must report precisely one requested dynamic feature')
    require(feature['coverage'][FEATURE_KEY] is True,
            'official bundletool did not produce the requested feature module')
    base=selected(feature,'device')
    chosen=selected(feature,FEATURE_KEY)
    prefix=FEATURE+'-'
    require(not any(n.startswith(prefix) for n in base['apks']),
            'on-demand feature was already present in default device selection')
    featured=[n for n in chosen['apks'] if n.startswith(prefix)]
    require(featured and len(featured)==len(set(featured)),
            'requested module did not produce its own exact feature APK')
    require(chosen['signer_sha256']==base['signer_sha256']==feature['fixture_certificate_sha256'],
            'feature APK signer differs from exact fixture key')
    require(all(x.get('name') in chosen['apks'] and
                x.get('archive_member','').split('/')[-1]==x.get('name') and
                x.get('v2_api24_27_verified') is True and
                x.get('api36_verified') is True and
                x.get('declared_sdk_range_verified') is True for x in chosen['verified_apks']),
            'feature cryptographic proofs incomplete')
    require(production['bundle_sha256'] != feature['bundle_sha256'] and
            production['signed_archive_sha256'] != feature['signed_archive_sha256'] and
            production['fixture_certificate_sha256'] != feature['fixture_certificate_sha256'],
            'production and isolated fixture evidence must be independent')
    require(all(HEX.fullmatch(x) is not None for x in (
            production['bundle_sha256'],feature['bundle_sha256'],
            production['signed_archive_sha256'],feature['signed_archive_sha256'])),
            'missing split archive hashes')
    # Composite PASS intentionally does NOT change upstream P5 matrix PARTIAL.
    require(production['overall']=='PARTIAL','production AAB cannot claim dynamic feature')
    return {'overall':'PASS','qualification_scope':'TWO_INDEPENDENT_AABS_HOSTED_API36',
            'source_sha':expected_sha,'run_id':run_id,'android_api':36,
            'production_matrix_overall':production['overall'],
            'isolated_feature_matrix_overall':feature['overall'],
            'production_bundle_sha256':production['bundle_sha256'],
            'feature_bundle_sha256':feature['bundle_sha256'],
            'production_signed_archive_sha256':production['signed_archive_sha256'],
            'feature_signed_archive_sha256':feature['signed_archive_sha256'],
            'production_signer_sha256':production['fixture_certificate_sha256'],
            'feature_signer_sha256':feature['fixture_certificate_sha256'],
            'production_dimensions':{k:True for k in DIMS},
            'isolated_on_demand_feature':FEATURE,
            'feature_apk_names':featured,
            'actual_apk_v2_api36_signatures_verified':True,
            'same_aab_all_five_dimensions_qualified':False,
            'aurora_production_dynamic_feature_qualified':False,
            'real_world_vendor_archives_qualified':False,
            'publisher_authenticated':False,
            'play_delivery_performed':False,
            'aurora_install_qualified':False,
            'physical_device_qualified':False,
            'release_qualified':False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--production',required=True)
    p.add_argument('--feature',required=True)
    p.add_argument('--manifest',required=True)
    p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--sha',required=True)
    p.add_argument('--run-id',required=True)
    args=p.parse_args()
    dest=args.receipt.resolve()
    require(dest not in {Path(args.production).resolve(),Path(args.feature).resolve(),
                         Path(args.manifest).resolve()},'may not overwrite raw evidence')
    result=attest(load(args.production),load(args.feature),load(args.manifest),
                  args.sha,args.run_id)
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    args.receipt.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print('R3C06_P6_COMPOSITE_TARGETING_PASS sha='+args.sha+' run='+args.run_id)

if __name__=='__main__':
    try:main()
    except (Refused,p5.QualificationRefused,ValueError,KeyError,TypeError,OSError,json.JSONDecodeError) as e:
        print('R3C06_P6_COMPOSITE_REFUSED: '+str(e),file=sys.stderr)
        raise SystemExit(2)
