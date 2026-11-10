#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Negative regression tests for P5 host receipts; no emulator required."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT=Path(__file__).with_name('r3c06_p5_manual_receipt.py')
spec=importlib.util.spec_from_file_location('p5_receipt',SCRIPT)
p5=importlib.util.module_from_spec(spec)
spec.loader.exec_module(p5)
SHA='a'*40
RUN='123'


def good_live():
    return dict(overall='PASS',source_sha=SHA,run_id=RUN,android_api=36,
                fixture_package=p5.PACKAGE,signed_v2_verified=True,fixture_sha256='b'*64,
                private_app_uid_staging_verified=True,private_fixture_cleanup_verified=True,
                instrumentation_status_proof_verified=True,
                emulator_unknown_sources_preprovisioned=True,
                emulator_unknown_sources_effective_verified=True,
                results=[dict(outcome=o,system_consent_ui_verified=True,android_callback_verified=True,
                              instrumentation_status_verified=True,foreground_activity_verified=True)
                         for o in ('DENY','ACCEPT')],physical_device_qualified=False,
                release_qualified=False)


def good_matrix():
    return dict(overall='PASS',source_sha=SHA,run_id=RUN,android_api=36,
                bundletool_sha256=p5.OFFICIAL_BUNDLETOOL_SHA256,bundle_sha256='c'*64,
                publisher_authenticated=False,aurora_install_qualified=False,
                physical_qualified=False,refused_targeting_does_not_count_as_coverage=True,
                coverage={'abi':True,'density':True,'locale':True,'sdk':True,'feature-camera':True})


class P5EvidenceTests(unittest.TestCase):
    def test_missing_foreground_or_emulator_pregrant_cannot_claim_live_success(self):
        for field in ('foreground_activity_verified',):
            doc=good_live()
            doc['results'][0].pop(field)
            with self.assertRaises(p5.QualificationRefused):
                p5.validate_live(doc,SHA,RUN)
        for value in (None,False):
            doc=good_live()
            doc['emulator_unknown_sources_preprovisioned']=value
            with self.assertRaises(p5.QualificationRefused):
                p5.validate_live(doc,SHA,RUN)

    def test_missing_effective_permission_attestation_refuses_live_pass(self):
        for value in (None, False, 'allow', 'ALLOWED'):
            doc = good_live()
            if value is None:
                del doc['emulator_unknown_sources_effective_verified']
            else:
                doc['emulator_unknown_sources_effective_verified'] = value
            with self.subTest(value=value), self.assertRaises(p5.QualificationRefused):
                p5.validate_live(doc, SHA, RUN)

    def test_valid_os_denial_then_acceptance(self):
        self.assertTrue(p5.validate_live(good_live(),SHA,RUN))
    def test_missing_app_uid_stage_receipt_refused(self):
        doc=good_live();doc['private_app_uid_staging_verified']=False
        with self.assertRaises(p5.QualificationRefused):p5.validate_live(doc,SHA,RUN)
    def test_missing_private_cleanup_proof_refused(self):
        doc=good_live();doc['private_fixture_cleanup_verified']=False
        with self.assertRaises(p5.QualificationRefused):p5.validate_live(doc,SHA,RUN)
    def test_missing_structured_instrumentation_receipt_refused(self):
        doc=good_live();doc['instrumentation_status_proof_verified']=False
        with self.assertRaises(p5.QualificationRefused):p5.validate_live(doc,SHA,RUN)
    def test_missing_os_case_instrumentation_status_refused(self):
        doc=good_live();doc['results'][0]['instrumentation_status_verified']=False
        with self.assertRaises(p5.QualificationRefused):p5.validate_live(doc,SHA,RUN)
    def test_missing_os_denial_refused(self):
        doc=good_live();doc['results']=doc['results'][1:]
        with self.assertRaises(p5.QualificationRefused):p5.validate_live(doc,SHA,RUN)
    def test_missing_android_ui_refused(self):
        doc=good_live();doc['results'][0]['system_consent_ui_verified']=False
        with self.assertRaises(p5.QualificationRefused):p5.validate_live(doc,SHA,RUN)
    def test_forged_commit_refused(self):
        with self.assertRaises(p5.QualificationRefused):p5.validate_live(good_live(),'0'*40,RUN)
    def test_pinned_bundletool_full_pass(self):
        self.assertTrue(p5.validate_bundletool(good_matrix(),SHA,RUN)[0])
    def test_refused_variant_cannot_claim_full_pass(self):
        doc=good_matrix();doc['coverage']['abi']=False
        with self.assertRaises(p5.QualificationRefused):p5.validate_bundletool(doc,SHA,RUN)
    def test_honest_partial_matrix(self):
        doc=good_matrix();doc['coverage']['abi']=False;doc['overall']='PARTIAL'
        self.assertFalse(p5.validate_bundletool(doc,SHA,RUN)[0])
    def test_no_dynamic_feature_never_counts_as_full_matrix(self):
        doc=good_matrix();del doc['coverage']['feature-camera'];doc['overall']='PARTIAL'
        self.assertFalse(p5.validate_bundletool(doc,SHA,RUN)[0])
    def test_wrong_bundletool_digest_refused(self):
        doc=good_matrix();doc['bundletool_sha256']='0'*64
        with self.assertRaises(p5.QualificationRefused):p5.validate_bundletool(doc,SHA,RUN)
    def test_missing_live_receipt_fails(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(p5.QualificationRefused):p5.attest(Path(td),SHA,RUN,True,False)
    def test_empty_optional_run_cannot_pass(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(p5.QualificationRefused):p5.attest(Path(td),SHA,RUN,False,False)
    def test_mixed_success_and_partial_is_partial(self):
        import json
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)
            (a/'R3C06_P3_LIVE_OS_INSTALL_RECEIPT.json').write_text(json.dumps(good_live()))
            m=good_matrix();m['coverage']['locale']=False;m['overall']='PARTIAL'
            (a/'R3C06_P3_BUNDLETOOL_MATRIX_RECEIPT.json').write_text(json.dumps(m))
            d=p5.attest(a,SHA,RUN,True,True)
            self.assertEqual(d['overall'],'PARTIAL')
            self.assertTrue(d['live_install_qualified'])
            self.assertFalse(d['bundletool_full_matrix_qualified'])

if __name__=='__main__':
    unittest.main(verbosity=2)
