#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Official bundletool API36 targeting probe; never an Aurora/Play trust oracle.

HF10: retain HF09 proof of *both* APK v2 cryptography (API24-27 verifier window) and
actual API36 verification. apksigner's default scheme-reporting is SDK-window
sensitive. A printed `v2: false` is not alone proof that v2 bytes are absent.
Fail closed on errors, changing APK bytes, mismatched signers, or missing
archive provenance; no split is re-signed or repaired after extraction.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import ssl
import tempfile
import zipfile

OFFICIAL_SHA = 'a099cfa1543f55593bc2ed16a70a7c67fe54b1747bb7301f37fdfd6d91028e29'
# Android SDK Build Tools 37 changed `--print-certs` from the legacy
# `Signer #1 certificate ...` form to per-scheme `V2 Signer:` / `V3.0 Signer:`.
# Accept only these documented, anchored labels, never arbitrary digest text.
# One *APK signer identity* may legitimately appear once per signing scheme.
CERT_RE = re.compile(
    r'^(?:Signer #(?P<old_number>[0-9]+)'
    r'|(?P<scheme>V(?:1|2|3(?:\.[0-9]+)?|4)) Signer'
    r'(?: #(?P<new_number>[0-9]+))?:)'
    r' certificate SHA-256 digest: (?P<digest>[0-9a-fA-F]{64})$'
)
SIGNER_COUNT_RE = re.compile(r'^Number of signers: ([0-9]+)$')
SCHEME_RE = re.compile(r'^Verified using v([123]) scheme(?: \([^\r\n]*?\))?: (true|false)$', re.M)
MAX_APKS_ZIP_ENTRIES = 4096
MAX_SPLIT_SIZE = 512 * 1024 * 1024

class Refused(Exception):
    pass


def check(ok, msg):
    if not ok:
        raise Refused(msg)


def cmd(*args, timeout=300, allow_fail=False):
    r = subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=timeout)
    if r.returncode and not allow_fail:
        raise Refused('command failed '+str(args[:3])+': '+r.stderr[-1300:])
    return r


def filehash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def signed_schemes(text):
    parsed = {}
    for scheme, state in SCHEME_RE.findall(text):
        if scheme in parsed: raise Refused('duplicate apksigner scheme evidence v'+scheme)
        parsed[scheme] = state == 'true'
    return parsed


def single_signer(text):
    """Require one identity across old/new apksigner certificate presentations.

    SDK 37 prints a digest for EACH scheme (e.g. V2 Signer / V3.0 Signer),
    and those lines can repeat the SAME cert. That does not mean the APK has
    multiple signers. Reject a second signer, an unknown/truncated digest line,
    a duplicate scheme record or different cert digests across schemes.
    Cryptographic verification is still independently required for each APK.
    """
    entries = {}
    counts = []
    for raw in text.splitlines():
        line = raw.strip()
        count = SIGNER_COUNT_RE.fullmatch(line)
        if count is not None:
            counts.append(int(count.group(1)))
        if 'certificate SHA-256 digest:' not in line:
            continue
        match = CERT_RE.fullmatch(line)
        check(match is not None,
              'apksigner must prove exactly one certificate SHA-256 digest: '
              'unrecognized certificate signer label')
        number = match.group('old_number') or match.group('new_number')
        check(number is None or number == '1',
              'apksigner must prove exactly one certificate SHA-256 digest: '
              'multiple signer identities')
        label = match.group('scheme') or 'legacy'
        check(label not in entries,
              'apksigner must prove exactly one certificate SHA-256 digest: '
              'duplicate signer certificate line')
        entries[label] = match.group('digest').lower()
    check(len(counts) <= 1 and (not counts or counts[0] == 1),
          'apksigner must prove exactly one certificate SHA-256 digest: '
          'signer count was not one')
    check(bool(entries),
          'apksigner must prove exactly one certificate SHA-256 digest: missing certificate')
    check(len(set(entries.values())) == 1,
          'apksigner must prove exactly one certificate SHA-256 digest: '
          'different certificates across signing schemes')
    return next(iter(entries.values()))


def run_apksigner(apksigner, apk, *, minimum=None, maximum=None, label='default'):
    command = [str(apksigner), 'verify', '--verbose', '--print-certs']
    if minimum is not None:
        command += ['--min-sdk-version',str(minimum)]
    if maximum is not None:
        command += ['--max-sdk-version',str(maximum)]
    command.append(str(apk))
    outcome = cmd(*command, timeout=90, allow_fail=True)
    stdout = outcome.stdout or ''
    # Scheme/certificate lines contain no secrets. Avoid copying whole stderr,
    # keystore inputs or APK data into CI logs and public artifacts.
    schemes = signed_schemes(stdout)
    summary = 'rc='+str(outcome.returncode)+' schemes='+repr(schemes)
    check(outcome.returncode == 0, 'apksigner '+label+' refused '+apk.name+' '+summary+
          ' stderr='+(' '.join((outcome.stderr or '').split()))[-500:])
    return schemes, single_signer(stdout)


def archive_apk_index(archive):
    """Map archive entry basename to verified (member name, SHA) tuples."""
    index = {}
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        check(len(members) <= MAX_APKS_ZIP_ENTRIES, 'bundletool archive unusually large')
        names = [entry.filename for entry in members]
        check(len(names)==len(set(names)), 'bundletool archive has duplicate member names')
        for entry in members:
            name = entry.filename
            check(not name.startswith('/') and '\\' not in name and
                  '..' not in Path(name).parts, 'bundletool archive unsafe member path')
            if not name.lower().endswith('.apk'): continue
            check(0 < entry.file_size <= MAX_SPLIT_SIZE,
                  'bundletool archive APK size invalid: '+name)
            h = hashlib.sha256()
            size = 0
            with bundle.open(entry) as source:
                for block in iter(lambda: source.read(1024*1024), b''):
                    size += len(block)
                    check(size<=MAX_SPLIT_SIZE, 'bundletool archive APK expanded too far')
                    h.update(block)
            check(size == entry.file_size, 'bundletool archive APK size drift')
            index.setdefault(Path(name).name, []).append((name, h.hexdigest()))
    check(index, 'bundletool signed archive contains no APK payloads')
    return index


def verify_extracted_apk(apksigner, apk, index, signer_expected=None):
    """Verify unchanged archive bytes, actual API36, v2 and signer continuity."""
    apk = Path(apk)
    check(apk.is_file() and not apk.is_symlink(), 'missing/unsafe extracted APK '+apk.name)
    check(0<apk.stat().st_size<=MAX_SPLIT_SIZE, 'extracted APK size invalid '+apk.name)
    digest_before = filehash(apk)
    matches = [(name, digest) for name, digest in index.get(apk.name, [])
               if digest == digest_before]
    check(len(matches)==1, 'missing/modified/ambiguous archive origin for '+apk.name)
    # Default verifies the APK's declared supported SDK range. The explicit
    # API36 check is the actual device qualification. The 24-27 window is a
    # separate proof of v2 bytes even when v3 supersedes v2 in default output.
    default, cert_default = run_apksigner(apksigner,apk,label='declared-range')
    api36, cert36 = run_apksigner(apksigner,apk,minimum=36,maximum=36,label='API36')
    v2_window, cert_v2 = run_apksigner(apksigner,apk,minimum=24,maximum=27,
                                      label='v2-API24-27')
    check(v2_window.get('2') is True,
          'v2 signing not cryptographically proven for '+apk.name+
          ' default='+repr(default)+' api36='+repr(api36)+
          ' v2_window='+repr(v2_window))
    check(api36.get('2') is True or api36.get('3') is True,
          'no valid APK v2/v3 scheme for API36 in '+apk.name)
    check(cert_default==cert36==cert_v2,
          'APK certificate changes across SDK verification windows '+apk.name)
    if signer_expected is not None:
        check(cert_default == signer_expected,
              'split signer differs from other selected APKs '+apk.name)
    check(filehash(apk)==digest_before, 'APK bytes changed during signing verification '+apk.name)
    return {'name':apk.name,'archive_member':matches[0][0],
            'sha256':digest_before,'signer_sha256':cert_default,
            'v2_api24_27_verified':True,'api36_verified':True,
            'declared_sdk_range_verified':True,
            'default_reported_schemes':default,'api36_reported_schemes':api36}


def qualifies_variant(reference, candidate):
    """Never count REFUSED, unsigned, unchanged, or wrong-signer selections."""
    return (reference.get('status') == 'SIGNED' and
            candidate.get('status') == 'SIGNED' and
            reference.get('signer_sha256') == candidate.get('signer_sha256') and
            isinstance(candidate.get('verified_apks'),list) and
            len(candidate['verified_apks'])==len(candidate.get('apks',[]))>0 and
            all(p.get('v2_api24_27_verified') is True and
                p.get('api36_verified') is True and
                p.get('signer_sha256') == candidate.get('signer_sha256')
                for p in candidate['verified_apks']) and
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
    bundle=Path(args.bundle);jar=Path(args.bundletool_jar)
    check(bundle.is_file() and jar.is_file(), 'real AAB or bundletool jar missing')
    check(args.bundletool_sha256.lower() == OFFICIAL_SHA and
          filehash(jar) == OFFICIAL_SHA, 'official bundletool binary SHA-256 mismatch')
    check(bundle.suffix.lower()=='.aab', 'expected a real AAB')
    check(cmd('adb','shell','getprop','ro.build.version.sdk').stdout.strip()=='36',
          'API36 emulator/device required')
    sdk=Path(os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT') or '')
    versions=sorted((sdk/'build-tools').glob('*'),reverse=True)
    versions=[t for t in versions if (t/'apksigner').is_file()]
    check(versions,'Android build tools/apksigner missing')
    apksigner=versions[0]/'apksigner'
    with tempfile.TemporaryDirectory(prefix='aurora-bundletool-matrix-',
            dir=os.environ.get('RUNNER_TEMP') or os.environ.get('TMPDIR') or None) as td:
        tmp=Path(td)
        # The short-lived PKCS12 key remains ONLY inside this private scratch dir.
        password='r3c06-matrix-only';ks=tmp/'fixture.p12'
        cmd('keytool','-genkeypair','-noprompt','-alias','fixture',
            '-keyalg','RSA','-keysize','2048','-validity','2','-storetype','PKCS12',
            '-dname','CN=R3C06 Matrix Test,O=Local CI',
            '-keystore',ks,'-storepass',password,'-keypass',password)
        cert_pem=cmd('keytool','-exportcert','-rfc','-alias','fixture',
                     '-storetype','PKCS12','-keystore',ks,'-storepass',password).stdout
        fixture_cert=hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert_pem)).hexdigest()
        base=['java','-jar',str(jar)]
        specfile=tmp/'device.json'
        cmd(*base,'get-device-spec','--output='+str(specfile),timeout=180)
        spec=json.loads(specfile.read_text())
        check(all(k in spec for k in ('sdkVersion','screenDensity','supportedAbis','supportedLocales')),
              'bundletool device-spec incomplete')
        check(spec['sdkVersion']==36, 'bundletool device spec must describe API36')
        archive=tmp/'fixture.apks'
        cmd(*base,'build-apks','--bundle='+str(bundle),'--output='+str(archive),
            '--ks='+str(ks),'--ks-pass=pass:'+password,
            '--ks-key-alias=fixture','--key-pass=pass:'+password,timeout=600)
        index=archive_apk_index(archive)
        baseline_signer=fixture_cert
        def extract(label,device,modules=None):
            nonlocal baseline_signer
            target=tmp/(label+'.json');target.write_text(json.dumps(device))
            out=tmp/label;out.mkdir()
            command=base+['extract-apks','--apks='+str(archive),
                          '--device-spec='+str(target),'--output-dir='+str(out)]
            if modules:command+=['--modules='+','.join(modules)]
            result=cmd(*command,allow_fail=True,timeout=240)
            if result.returncode:
                return {'status':'REFUSED','apks':[], 'sha256':[],
                        'error_type':'bundletool refused targeting'}
            packages=sorted(out.rglob('*.apk'))
            check(packages, 'bundletool returned no APKs for '+label)
            signed=[];cert=None
            for apk in packages:
                proof=verify_extracted_apk(apksigner,apk,index,cert or baseline_signer)
                cert=proof['signer_sha256']
                signed.append(proof)
            check(cert is not None, 'no signer proved for '+label)
            if baseline_signer is None: baseline_signer=cert
            check(cert == baseline_signer, 'selection signer disagrees with baseline')
            return {'status':'SIGNED','signer_sha256':cert,
                    'apks':[p['name'] for p in signed],
                    'sha256':[p['sha256'] for p in signed], 'verified_apks':signed}
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
        all_covered=all(coverage.get(k,False) for k in ('abi','density','locale','sdk')) and bool(args.feature) and \
            all(coverage.get('feature-'+f,False) for f in args.feature)
        if args.strict_dimensions:
            check(all_covered, 'fixture does not cover every requested targeting/feature dimension')
        receipt={'overall':'PASS' if all_covered else 'PARTIAL',
                 'bundle_sha256':filehash(bundle),'bundletool_sha256':filehash(jar),
                 'signed_archive_sha256':filehash(archive),
                 'fixture_certificate_sha256':fixture_cert,
                 'refused_targeting_does_not_count_as_coverage':True,
                 'source_sha':os.environ.get('GITHUB_SHA',''),
                 'run_id':os.environ.get('GITHUB_RUN_ID',''),
                 'android_api':36,'device_spec':spec,'coverage':coverage,
                 'results':results,'publisher_authenticated':False,
                 'aurora_install_qualified':False,'physical_qualified':False}
        output=Path(args.receipt);output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
        print('R3C06_BUNDLETOOL_'+receipt['overall']+' receipt='+str(output))

if __name__=='__main__':
    try: main()
    except (Refused,subprocess.TimeoutExpired,OSError,ValueError,zipfile.BadZipFile) as error:
        print('R3C06_BUNDLETOOL_REFUSED: '+str(error),file=sys.stderr)
        raise SystemExit(2)
