#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R3C06 P5: source-bound, manually opted-in R1D evidence; NEVER creates a PASS from absent tests."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

SIGNED_RE = re.compile(r"^[0-9a-f]{64}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
PACKAGE = 'com.aurora.r3c06.fixture'
OFFICIAL_BUNDLETOOL_SHA256 = 'a099cfa1543f55593bc2ed16a70a7c67fe54b1747bb7301f37fdfd6d91028e29'


class QualificationRefused(RuntimeError):
    pass


def require(yes, message):
    if not yes:
        raise QualificationRefused(message)


def load(path):
    require(path.is_file(), 'missing required receipt: ' + str(path))
    doc = json.loads(path.read_text(encoding='utf-8'))
    require(isinstance(doc, dict), 'receipt must be object: ' + str(path))
    return doc


def validate_live(doc, expected_sha, run_id):
    require(doc.get('overall') == 'PASS', 'live OS receipt did not PASS')
    require(doc.get('source_sha') == expected_sha and doc.get('run_id') == run_id,
            'live install source/run does not match dispatch')
    require(doc.get('android_api') == 36 and doc.get('fixture_package') == PACKAGE,
            'wrong live install SDK or fixture package')
    require(doc.get('signed_v2_verified') is True, 'v2 signature not proved')
    require(doc.get('private_app_uid_staging_verified') is True,
            'fixture was not proved staged by Aurora app UID')
    require(doc.get('private_fixture_cleanup_verified') is True,
            'app-private fixture deletion is not verified')
    require(doc.get('emulator_unknown_sources_preprovisioned') is True,
            'hosted emulator permission precondition was not recorded')
    require(doc.get('emulator_unknown_sources_effective_verified') is True,
            'Android app did not attest effective unknown-source capability')
    require(doc.get('instrumentation_status_proof_verified') is True,
            'structured Android instrumentation status was not verified')
    require(isinstance(doc.get('fixture_sha256'), str) and
            SIGNED_RE.fullmatch(doc['fixture_sha256']), 'missing test-signed fixture hash')
    results = doc.get('results')
    require(isinstance(results, list) and len(results) == 2,
            'requires exactly two Android OS outcomes')
    require([r.get('outcome') for r in results if isinstance(r, dict)] ==
            ['DENY', 'ACCEPT'], 'required denial THEN installation is missing')
    require(all(r.get('system_consent_ui_verified') is True and
                r.get('android_callback_verified') is True and
                r.get('instrumentation_status_verified') is True and
                r.get('foreground_activity_verified') is True for r in results),
            'system confirmation or actual callback not proved')
    require(doc.get('physical_device_qualified') is False and
            doc.get('release_qualified') is False,
            'live gate must not forge physical/release status')
    return True


def validate_bundletool(doc, expected_sha, run_id):
    """Independently bind the host matrix receipt to measured split proofs.

    Host JSON alone is not proof of genuine cryptography; the paired, pinned
    bundletool runner must have executed its apksigner checks on exact bytes.
    This validator refuses inconsistent or incomplete *claims* in that receipt.
    """
    require(doc.get('source_sha') == expected_sha and doc.get('run_id') == run_id,
            'bundletool source/run must match this dispatch')
    require(doc.get('android_api') == 36, 'bundletool device API mismatch')
    require(doc.get('bundletool_sha256') == OFFICIAL_BUNDLETOOL_SHA256,
            'bundletool SHA differs from pinned official binary')
    require(doc.get('publisher_authenticated') is False and
            doc.get('aurora_install_qualified') is False and
            doc.get('physical_qualified') is False,
            'bundletool cannot attest publisher, OS install or physical device')
    require(doc.get('refused_targeting_does_not_count_as_coverage') is True,
            'refused selections must not count as coverage')
    require(doc.get('overall') in {'PASS', 'PARTIAL'}, 'bundletool report did not execute')
    for label in ('bundle_sha256','signed_archive_sha256'):
        require(isinstance(doc.get(label), str) and
                SIGNED_RE.fullmatch(doc[label]), 'missing digest: '+label)
    spec = doc.get('device_spec')
    require(isinstance(spec,dict) and spec.get('sdkVersion') == 36 and
            isinstance(spec.get('supportedAbis'),list) and
            isinstance(spec.get('supportedLocales'),list) and
            isinstance(spec.get('screenDensity'),int),
            'bundletool real API36 device spec missing')
    cov = doc.get('coverage')
    results = doc.get('results')
    require(isinstance(cov, dict) and isinstance(results,dict) and
            all(isinstance(cov.get(dim), bool) for dim in ('abi','density','locale','sdk')),
            'bundletool dimensions/results missing')
    require(set(results) == {'device', *cov.keys()}, 'results/coverage inventory mismatch')

    def inspect(label):
        result=results[label]
        require(isinstance(result,dict) and result.get('status') in {'SIGNED','REFUSED'},
                'unsigned or unrecognized matrix result: '+label)
        if result['status']=='REFUSED':
            require(result.get('apks')==[] and result.get('sha256')==[] and
                    result.get('error_type')=='bundletool refused targeting',
                    'refused target misrepresented APK bytes: '+label)
            return False
        signer=result.get('signer_sha256')
        names=result.get('apks');hashes=result.get('sha256')
        proof=result.get('verified_apks')
        require(isinstance(signer,str) and SIGNED_RE.fullmatch(signer) and
                isinstance(names,list) and names and
                len(names)==len(set(names)) and
                isinstance(hashes,list) and len(hashes)==len(names) and
                isinstance(proof,list) and len(proof)==len(names),
                'selected APK signatures/inventory incomplete: '+label)
        for name,digest,part in zip(names,hashes,proof):
            require(isinstance(name,str) and name.endswith('.apk') and '/' not in name and
                    isinstance(digest,str) and SIGNED_RE.fullmatch(digest) and
                    isinstance(part,dict) and part.get('name')==name and
                    part.get('sha256')==digest and
                    part.get('signer_sha256')==signer and
                    part.get('v2_api24_27_verified') is True and
                    part.get('api36_verified') is True and
                    part.get('declared_sdk_range_verified') is True and
                    isinstance(part.get('archive_member'),str) and
                    Path(part['archive_member']).name == name and
                    isinstance(part.get('api36_reported_schemes'),dict),
                    'invalid exact split signing proof: '+label)
            # Reported API36 v2/v3 must be genuine; v2 is separately attested.
            require(part.get('api36_reported_schemes',{}).get('2') is True or
                    part.get('api36_reported_schemes',{}).get('3') is True,
                    'split has no API36 v2/v3 proof: '+label)
        return True

    require(inspect('device'), 'device selection is not cryptographically signed')
    baseline=results['device']
    require(isinstance(doc.get('fixture_certificate_sha256'),str) and
            SIGNED_RE.fullmatch(doc['fixture_certificate_sha256']) and
            doc['fixture_certificate_sha256']==baseline['signer_sha256'],
            'signed split signer does not match generated fixture keystore')
    derived={}
    for label in cov:
        signed=inspect(label)
        candidate=results[label]
        if signed:
            require(candidate['signer_sha256']==baseline['signer_sha256'],
                    'matrix split signer differs from device selection: '+label)
        if label.startswith('feature-'):
            dimension=signed and any(label[len('feature-'):] in n for n in candidate['apks'])
        else:
            dimension=(signed and
                       (candidate['apks'],candidate['sha256']) !=
                       (baseline['apks'],baseline['sha256']))
        derived[label]=bool(dimension)
        require(cov[label] is derived[label], 'forged or stale matrix coverage: '+label)
    full=all(derived[k] for k in ('abi','density','locale','sdk')) and any(
        k.startswith('feature-') for k in derived) and all(
        value for key,value in derived.items() if key.startswith('feature-'))
    require((doc['overall']=='PASS') == full,
            'bundletool claimed PASS with absent/partial coverage or vice versa')
    return full,cov


def attest(base, expected_sha, run_id, live, matrix):
    require(SHA_RE.fullmatch(expected_sha) is not None, 'expected exact commit SHA required')
    require(re.fullmatch(r'[0-9]+', run_id) is not None, 'Actions run ID required')
    require(live or matrix, 'P5 manual receipt cannot fabricate acceptance for default read-only run')
    live_path = base / 'R3C06_P3_LIVE_OS_INSTALL_RECEIPT.json'
    bundle_path = base / 'R3C06_P3_BUNDLETOOL_MATRIX_RECEIPT.json'
    if not live:
        require(not live_path.exists(), 'unexpected live-install receipt from a read-only run')
    if not matrix:
        require(not bundle_path.exists(), 'unexpected bundletool receipt from a no-matrix run')
    live_ok = validate_live(load(live_path), expected_sha, run_id) if live else False
    matrix_ok, coverage = validate_bundletool(load(bundle_path), expected_sha, run_id) if matrix else (False,{})
    # 'PASS' means requested tests ran and proved their requested scope. It does
    # NOT imply complete R3C06, real world APKMirror or physical-device coverage.
    overall = 'PASS' if ((not live or live_ok) and (not matrix or matrix_ok)) else 'PARTIAL'
    return {'overall': overall, 'qualification_scope': 'MANUAL_HOSTED_API36_ONLY',
            'source_sha':expected_sha, 'run_id':run_id,'android_api':36,
            'r1d_readonly_51_precondition': 'separate_R3C06_P4_API36_READONLY_RECEIPT',
            'live_install_requested':live,'live_install_qualified':live_ok,
            'system_denial_and_acceptance_verified':live_ok,
            'bundletool_requested':matrix,'bundletool_full_matrix_qualified':matrix_ok,
            'bundletool_coverage':coverage,
            'real_world_vendor_archives_qualified':False,
            'physical_device_qualified':False,'release_qualified':False,
            'production_play_evidence_modified':False}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--logs', type=Path,required=True)
    ap.add_argument('--receipt', type=Path,required=True)
    ap.add_argument('--sha',required=True)
    ap.add_argument('--run-id',required=True)
    ap.add_argument('--expect-live',choices=('yes','no'),required=True)
    ap.add_argument('--expect-bundletool',choices=('yes','no'),required=True)
    args=ap.parse_args()
    require(args.receipt.resolve() != (args.logs/'R3C06_P3_LIVE_OS_INSTALL_RECEIPT.json').resolve(),
            'cannot overwrite raw OS receipt')
    receipt=attest(args.logs,args.sha,args.run_id,
                   args.expect_live=='yes',args.expect_bundletool=='yes')
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    args.receipt.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print('R3C06_P5_MANUAL_HOSTED_'+receipt['overall']+' sha='+args.sha+
          ' live='+str(receipt['live_install_qualified'])+
          ' matrix='+str(receipt['bundletool_full_matrix_qualified']))


if __name__=='__main__':
    try: main()
    except (QualificationRefused, ValueError, OSError, json.JSONDecodeError, TypeError) as error:
        print('R3C06_P5_MANUAL_REFUSED: '+str(error),file=sys.stderr)
        raise SystemExit(2)
