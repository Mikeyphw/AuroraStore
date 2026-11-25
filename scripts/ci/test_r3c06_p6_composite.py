#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Adversarial P6 receipt tests; source- and receipt-level, never Android emulator proofs."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import r3c06_p6_composite_receipt as p6
import r3c06_p5_manual_receipt as p5

SHA='b'*40
RUN='98765'
SIG1='a'*64
SIG2='b'*64
SPEC={'sdkVersion':36,'supportedAbis':['x86_64'],'supportedLocales':['en-US'],
      'screenDensity':420}

def apk(name,signer,hex_digest):
    return dict(name=name,sha256=hex_digest,archive_member='splits/'+name,
        signer_sha256=signer,v2_api24_27_verified=True,api36_verified=True,
        declared_sdk_range_verified=True,
        api36_reported_schemes={'3':True},default_reported_schemes={'3':True})

def result(parts,signer):
    return dict(status='SIGNED',apks=[x['name'] for x in parts],
                sha256=[x['sha256'] for x in parts],
                signer_sha256=signer,verified_apks=parts)

def matrix(is_feature=False):
    signer=SIG2 if is_feature else SIG1
    baseline=result([apk('base-master.apk',signer,'1'*64)],signer)
    variants={}
    for i,key in enumerate(p6.DIMS,2):
        variants[key]=result([apk('base-'+key+'.apk',signer,str(i)*64)],signer) if not is_feature else baseline
    cov={key:not is_feature for key in p6.DIMS}
    if is_feature:
        variants['feature-featureproof']=result([
            apk('base-master.apk',signer,'1'*64),
            apk('featureproof-master.apk',signer,'9'*64)],signer)
        cov['feature-featureproof']=True
    return dict(overall='PARTIAL',source_sha=SHA,run_id=RUN,android_api=36,
                bundletool_sha256=p5.OFFICIAL_BUNDLETOOL_SHA256,
                bundle_sha256=('3' if is_feature else '2')*64,
                signed_archive_sha256=('5' if is_feature else '4')*64,
                fixture_certificate_sha256=signer,device_spec=copy.deepcopy(SPEC),
                publisher_authenticated=False,aurora_install_qualified=False,
                physical_qualified=False,refused_targeting_does_not_count_as_coverage=True,
                coverage=cov,results={'device':baseline,**variants})

def manifest():
    return dict(overall='PASS',source_sha=SHA,run_id=RUN,android_api=36,
                module='featureproof',on_demand=True,fusing_disabled=True,
                feature_marker_verified=True,fixture_package='com.aurora.r3c06.featurefixture',
                bundle_sha256='3'*64,bundletool_sha256=p5.OFFICIAL_BUNDLETOOL_SHA256,
                production_aab_modified=False,publisher_authenticated=False,
                aurora_install_qualified=False,physical_device_qualified=False,
                release_qualified=False)

class CompositeNegatives(unittest.TestCase):
    def setUp(self):
        self.prod,self.feature,self.m=matrix(),matrix(True),manifest()

    def check(self):
        return p6.attest(self.prod,self.feature,self.m,SHA,RUN)

    def test_genuine_independent_composite(self):
        receipt=self.check()
        self.assertEqual(receipt['overall'],'PASS')
        self.assertFalse(receipt['same_aab_all_five_dimensions_qualified'])
        self.assertFalse(receipt['aurora_production_dynamic_feature_qualified'])
        self.assertEqual(receipt['feature_apk_names'],['featureproof-master.apk'])

    def test_wrong_sha_run(self):
        for sha,run in [('0'*40,RUN),(SHA,'88'),('bad',RUN),(SHA,'not-run')]:
            with self.subTest(sha=sha,run=run),self.assertRaises(p6.Refused):
                p6.attest(self.prod,self.feature,self.m,sha,run)

    def test_missing_production_dimension(self):
        for dim in p6.DIMS:
            p=copy.deepcopy(self.prod);p['coverage'][dim]=False
            with self.subTest(dim=dim),self.assertRaises(p6.Refused):
                p6.attest(p,self.feature,self.m,SHA,RUN)

    def test_production_extra_feature_fake(self):
        self.prod['coverage']['feature-featureproof']=True
        with self.assertRaises(p6.Refused):self.check()

    def test_missing_requested_feature(self):
        self.feature['coverage'].pop('feature-featureproof')
        self.feature['results'].pop('feature-featureproof')
        with self.assertRaises(p6.Refused):self.check()

    def test_unrequested_feature_identity(self):
        chosen=self.feature['results']['feature-featureproof']
        chosen['apks'][1]='otherfeature-master.apk'
        chosen['verified_apks'][1]['name']='otherfeature-master.apk'
        chosen['verified_apks'][1]['archive_member']='splits/otherfeature-master.apk'
        self.feature['coverage']['feature-featureproof']=False
        with self.assertRaises(p6.Refused):self.check()

    def test_feature_must_be_on_demand(self):
        self.feature['results']['device']=copy.deepcopy(self.feature['results']['feature-featureproof'])
        with self.assertRaises(p6.Refused):self.check()

    def test_feature_module_real_signing_proof(self):
        for key in ('api36_verified','v2_api24_27_verified','declared_sdk_range_verified'):
            f=copy.deepcopy(self.feature)
            f['results']['feature-featureproof']['verified_apks'][1][key]=False
            with self.subTest(key=key),self.assertRaises(p6.Refused):
                p6.attest(self.prod,f,self.m,SHA,RUN)

    def test_cross_signer_module_refuses(self):
        self.feature['results']['feature-featureproof']['verified_apks'][1]['signer_sha256']=SIG1
        with self.assertRaises(p6.Refused):self.check()

    def test_feature_manifest_must_match_exact_aab(self):
        self.m['bundle_sha256']='f'*64
        with self.assertRaises(p6.Refused):self.check()

    def test_feature_manifest_flags_cannot_claim_unsupported_scope(self):
        for key in ('on_demand','fusing_disabled','feature_marker_verified'):
            m=copy.deepcopy(self.m);m[key]=False
            with self.subTest(key=key),self.assertRaises(p6.Refused):
                p6.attest(self.prod,self.feature,m,SHA,RUN)
        for key in ('publisher_authenticated','production_aab_modified',
                    'aurora_install_qualified','release_qualified','physical_device_qualified'):
            m=copy.deepcopy(self.m);m[key]=True
            with self.subTest(key=key),self.assertRaises(p6.Refused):
                p6.attest(self.prod,self.feature,m,SHA,RUN)

    def test_same_aab_refuses_independence(self):
        self.feature['bundle_sha256']=self.prod['bundle_sha256']
        self.m['bundle_sha256']=self.prod['bundle_sha256']
        with self.assertRaises(p6.Refused):self.check()

    def test_same_certificate_refuses_independence(self):
        sig=SIG1
        self.feature['fixture_certificate_sha256']=sig
        for entry in self.feature['results'].values():
            entry['signer_sha256']=sig
            for proof in entry['verified_apks']:proof['signer_sha256']=sig
        with self.assertRaises(p6.Refused):self.check()

    def test_unmatched_device_spec(self):
        self.feature['device_spec']['screenDensity']=160
        with self.assertRaises(p6.Refused):self.check()

    def test_forged_feature_coverage(self):
        self.feature['coverage']['feature-featureproof']=True
        self.feature['results']['feature-featureproof']['apks'].pop()
        with self.assertRaises(p6.Refused):self.check()

    def test_missing_archive_provenance(self):
        self.feature['results']['feature-featureproof']['verified_apks'][1]['archive_member']='wrong.apk'
        with self.assertRaises(p6.Refused):self.check()

    def test_extra_unexpected_feature(self):
        self.feature['coverage']['feature-evil']=True
        with self.assertRaises(p6.Refused):self.check()

    def test_skipped_install_cannot_promote_publisher(self):
        self.prod['publisher_authenticated']=True
        with self.assertRaises(p6.Refused):self.check()

    def test_feature_aab_xml_requires_on_demand(self):
        import r3c06_p6_feature_aab as fixture
        ns='http://schemas.android.com/apk/distribution'
        good=f'''<manifest xmlns:dist="{ns}"><dist:module><dist:delivery><dist:on-demand/></dist:delivery><dist:fusing dist:include="false"/></dist:module></manifest>'''
        self.assertTrue(fixture.check_xml(good))
        for bad in (good.replace('on-demand','install-time'),
                    good.replace('dist:include="false"','dist:include="true"'),
                    '<manifest/>'):
            with self.subTest(bad=bad),self.assertRaises(fixture.Refused):
                fixture.check_xml(bad)

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(CompositeNegatives)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():raise SystemExit(1)
    print('R3C06_P6_COMPOSITE_NEGATIVES_PASS='+str(result.testsRun))
