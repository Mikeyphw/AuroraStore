#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""HF10 host-only signer-output compatibility and signing/provenance negatives; no Android SDK or live install."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('matrix_oracle',HERE/'r3c06_bundletool_matrix.py')
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
CERT_A='a'*64
CERT_B='b'*64

def signer_output(*,v1=True,v2=True,v3=True,cert=CERT_A):
    return '\n'.join([
        'Verifies',
        'Verified using v1 scheme (JAR signing): '+str(v1).lower(),
        'Verified using v2 scheme (APK Signature Scheme v2): '+str(v2).lower(),
        'Verified using v3 scheme (APK Signature Scheme v3): '+str(v3).lower(),
        'Signer #1 certificate SHA-256 digest: '+cert])+'\n'

class MatrixSecurityTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)
        self.apk=self.path/'base-en_3.apk'
        self.apk.write_bytes(b'unsigned test bytes - content cryptography mocked separately')
        self.zip=self.path/'signed.apks'
        with zipfile.ZipFile(self.zip,'w') as out:
            out.writestr('splits/base-en_3.apk',self.apk.read_bytes())
        self.index=m.archive_apk_index(self.zip)

    def mock_verifier(self, sequence=None):
        seq=sequence or [signer_output()]*3
        seen=[]
        def fake(*args,**kwargs):
            seen.append(args)
            value=seq.pop(0)
            if isinstance(value,Exception): raise value
            if isinstance(value,tuple): rc,stdout=value
            else: rc,stdout=0,value
            return subprocess.CompletedProcess(args,rc,stdout,'')
        return fake,seen

    def test_proves_exact_archive_bytes_api36_v2_and_matching_single_signer(self):
        fake,seen=self.mock_verifier()
        with patch.object(m,'cmd',side_effect=fake):
            proof=m.verify_extracted_apk('apksigner',self.apk,self.index)
        self.assertTrue(proof['v2_api24_27_verified'])
        self.assertTrue(proof['api36_verified'])
        self.assertEqual(proof['signer_sha256'],CERT_A)
        self.assertEqual(proof['archive_member'],'splits/base-en_3.apk')
        self.assertIn('--min-sdk-version',seen[1])
        self.assertIn('36',seen[1]);self.assertIn('24',seen[2]);self.assertIn('27',seen[2])

    def test_missing_archive_member_is_refused_before_signature_invocation(self):
        fake,seen=self.mock_verifier()
        with patch.object(m,'cmd',side_effect=fake):
            with self.assertRaisesRegex(m.Refused,'missing/modified/ambiguous'):
                m.verify_extracted_apk('apksigner',self.apk,{})
        self.assertEqual(seen,[])

    def test_modified_split_is_refused_before_signature_invocation(self):
        self.apk.write_bytes(self.apk.read_bytes()+b' tampered')
        fake,seen=self.mock_verifier()
        with patch.object(m,'cmd',side_effect=fake):
            with self.assertRaisesRegex(m.Refused,'missing/modified/ambiguous'):
                m.verify_extracted_apk('apksigner',self.apk,self.index)
        self.assertEqual(seen,[])

    def test_missing_extracted_file_is_refused(self):
        self.apk.unlink()
        with self.assertRaisesRegex(m.Refused,'missing/unsafe extracted'):
            m.verify_extracted_apk('apksigner',self.apk,self.index)

    def test_unsigned_output_is_refused(self):
        fake,_=self.mock_verifier([(1,'DOES NOT VERIFY\n')])
        with patch.object(m,'cmd',side_effect=fake):
            with self.assertRaisesRegex(m.Refused,'declared-range refused'):
                m.verify_extracted_apk('apksigner',self.apk,self.index)

    def test_v3_only_even_if_api36_passes_is_refused_without_v2_proof(self):
        fake,_=self.mock_verifier([signer_output(v2=False),signer_output(v2=False),signer_output(v2=False)])
        with patch.object(m,'cmd',side_effect=fake):
            with self.assertRaisesRegex(m.Refused,'v2 signing not cryptographically proven'):
                m.verify_extracted_apk('apksigner',self.apk,self.index)

    def test_v2_reported_false_by_default_is_not_a_v2_negative(self):
        fake,_=self.mock_verifier([signer_output(v2=False),signer_output(v2=False),signer_output(v2=True)])
        with patch.object(m,'cmd',side_effect=fake):
            proof=m.verify_extracted_apk('apksigner',self.apk,self.index)
        self.assertFalse(proof['default_reported_schemes']['2'])
        self.assertTrue(proof['v2_api24_27_verified'])

    def test_api36_signature_absent_is_refused(self):
        fake,_=self.mock_verifier([signer_output(),signer_output(v2=False,v3=False),signer_output()])
        with patch.object(m,'cmd',side_effect=fake):
            with self.assertRaisesRegex(m.Refused,'no valid APK v2/v3 scheme for API36'):
                m.verify_extracted_apk('apksigner',self.apk,self.index)

    def test_api36_nonzero_refused_despite_v2_positive(self):
        fake,_=self.mock_verifier([signer_output(),(2,'DOES NOT VERIFY\n')])
        with patch.object(m,'cmd',side_effect=fake):
            with self.assertRaisesRegex(m.Refused,'API36 refused'):
                m.verify_extracted_apk('apksigner',self.apk,self.index)

    def test_inconsistent_cert_across_windows_refused(self):
        fake,_=self.mock_verifier([signer_output(),signer_output(cert=CERT_B),signer_output()])
        with patch.object(m,'cmd',side_effect=fake):
            with self.assertRaisesRegex(m.Refused,'certificate changes'):
                m.verify_extracted_apk('apksigner',self.apk,self.index)

    def test_split_signer_mismatch_refused(self):
        fake,_=self.mock_verifier([signer_output()]*3)
        with patch.object(m,'cmd',side_effect=fake):
            with self.assertRaisesRegex(m.Refused,'split signer differs'):
                m.verify_extracted_apk('apksigner',self.apk,self.index,CERT_B)

    def test_missing_cert_fingerprint_is_refused(self):
        fake,_=self.mock_verifier([signer_output().split('Signer #1')[0]])
        with patch.object(m,'cmd',side_effect=fake):
            with self.assertRaisesRegex(m.Refused,'exactly one certificate'):
                m.verify_extracted_apk('apksigner',self.apk,self.index)

    def test_multiple_cert_fingerprints_refused(self):
        fake,_=self.mock_verifier([signer_output()+'Signer #2 certificate SHA-256 digest: '+CERT_B+'\n'])
        with patch.object(m,'cmd',side_effect=fake):
            with self.assertRaisesRegex(m.Refused,'exactly one certificate'):
                m.verify_extracted_apk('apksigner',self.apk,self.index)

    def test_duplicate_scheme_lines_refused(self):
        with self.assertRaisesRegex(m.Refused,'duplicate'):
            m.signed_schemes(signer_output()+signer_output())

    def test_duplicate_archive_member_refused(self):
        with zipfile.ZipFile(self.zip,'a') as z:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',UserWarning)
                z.writestr('splits/base-en_3.apk',b'other')
        with self.assertRaisesRegex(m.Refused,'duplicate member'):
            m.archive_apk_index(self.zip)

    def test_archive_traversal_refused(self):
        with zipfile.ZipFile(self.zip,'a') as z:
            z.writestr('../evil.apk',b'bad')
        with self.assertRaisesRegex(m.Refused,'unsafe member path'):
            m.archive_apk_index(self.zip)

    def test_duplicate_target_origin_refused(self):
        duplicate={'base-en_3.apk':[("splits/a.apk",m.filehash(self.apk)),
                                         ("splits/b.apk",m.filehash(self.apk))]}
        with self.assertRaisesRegex(m.Refused,'ambiguous archive origin'):
            m.verify_extracted_apk('apksigner',self.apk,duplicate)

    def test_refused_target_cannot_count_as_coverage(self):
        reference={'status':'SIGNED','signer_sha256':CERT_A,'apks':['base.apk'],'sha256':['1'*64]}
        candidate={'status':'REFUSED','apks':[]}
        self.assertFalse(m.qualifies_variant(reference,candidate))

    def test_signed_without_split_proof_cannot_count_as_coverage(self):
        reference={'status':'SIGNED','signer_sha256':CERT_A,'apks':['base.apk'],'sha256':['1'*64]}
        candidate={'status':'SIGNED','signer_sha256':CERT_A,'apks':['base-other.apk'],
                   'sha256':['2'*64]}
        self.assertFalse(m.qualifies_variant(reference,candidate))

    def test_changed_signed_split_with_wrong_signer_cannot_count(self):
        reference={'status':'SIGNED','signer_sha256':CERT_A,'apks':['base.apk'],'sha256':['1'*64]}
        candidate={'status':'SIGNED','signer_sha256':CERT_B,'apks':['base-other.apk'],
                   'sha256':['2'*64], 'verified_apks':[{'v2_api24_27_verified':True,
                   'api36_verified':True,'signer_sha256':CERT_B}]}
        self.assertFalse(m.qualifies_variant(reference,candidate))


    # HF10: Android Build Tools 37 changed the apksigner output labels. Real
    # cryptographic rc=0 verification, v2 and API36 windows are still mandatory.
    def test_sdk37_single_v2_scheme_certificate_parses(self):
        self.assertEqual(m.single_signer('V2 Signer: certificate SHA-256 digest: '+CERT_A+'\n'),CERT_A)

    def test_sdk37_single_v30_scheme_certificate_parses(self):
        self.assertEqual(m.single_signer('V3.0 Signer: certificate SHA-256 digest: '+CERT_A+'\n'),CERT_A)

    def test_sdk37_multiple_scheme_lines_same_signer_pass(self):
        output=('Number of signers: 1\n'
                'V2 Signer: certificate SHA-256 digest: '+CERT_A+'\n'
                'V3.0 Signer: certificate SHA-256 digest: '+CERT_A.upper()+'\n')
        self.assertEqual(m.single_signer(output),CERT_A)

    def test_sdk37_realistic_three_window_selection_is_signed(self):
        def output(label):
            return ('Verifies\nNumber of signers: 1\n'
                    'Verified using v1 scheme (JAR signing): false\n'
                    'Verified using v2 scheme (APK Signature Scheme v2): true\n'
                    'Verified using v3 scheme (APK Signature Scheme v3): true\n'
                    +label+': certificate SHA-256 digest: '+CERT_A+'\n')
        fake,seen=self.mock_verifier([output('V3.0 Signer'),output('V3.0 Signer'),output('V2 Signer')])
        with patch.object(m,'cmd',side_effect=fake):
            proof=m.verify_extracted_apk('apksigner',self.apk,self.index,signer_expected=CERT_A)
        self.assertTrue(proof['v2_api24_27_verified'])
        self.assertTrue(proof['api36_verified'])
        self.assertEqual(proof['signer_sha256'],CERT_A)
        self.assertEqual(len(seen),3)

    def test_sdk37_multiple_scheme_signers_disagree_refused(self):
        with self.assertRaisesRegex(m.Refused,'different certificates'):
            m.single_signer('V2 Signer: certificate SHA-256 digest: '+CERT_A+'\n'
                            'V3.0 Signer: certificate SHA-256 digest: '+CERT_B+'\n')

    def test_sdk37_extra_signer_number_refused(self):
        with self.assertRaisesRegex(m.Refused,'multiple signer identities'):
            m.single_signer('V2 Signer #2: certificate SHA-256 digest: '+CERT_A+'\n')

    def test_sdk37_two_signers_count_refused_even_if_one_digest(self):
        with self.assertRaisesRegex(m.Refused,'signer count was not one'):
            m.single_signer('Number of signers: 2\n'
                            'V2 Signer: certificate SHA-256 digest: '+CERT_A+'\n')

    def test_sdk37_multiple_schemes_same_certificate_but_count_two_refused(self):
        with self.assertRaisesRegex(m.Refused,'signer count was not one'):
            m.single_signer('Number of signers: 2\n'
                            'V2 Signer: certificate SHA-256 digest: '+CERT_A+'\n'
                            'V3.0 Signer: certificate SHA-256 digest: '+CERT_A+'\n')

    def test_sdk37_duplicate_cert_scheme_line_refused(self):
        with self.assertRaisesRegex(m.Refused,'duplicate signer certificate'):
            m.single_signer(('V2 Signer: certificate SHA-256 digest: '+CERT_A+'\n')*2)

    def test_sdk37_duplicate_signer_count_refused(self):
        with self.assertRaisesRegex(m.Refused,'signer count was not one'):
            m.single_signer('Number of signers: 1\nNumber of signers: 1\n'
                            'V2 Signer: certificate SHA-256 digest: '+CERT_A+'\n')

    def test_sdk37_unknown_certificate_label_not_accepted(self):
        with self.assertRaisesRegex(m.Refused,'unrecognized certificate signer label'):
            m.single_signer('Unverified Signer: certificate SHA-256 digest: '+CERT_A+'\n')

    def test_sdk37_truncated_certificate_digest_refused(self):
        with self.assertRaisesRegex(m.Refused,'unrecognized certificate signer label'):
            m.single_signer('V2 Signer: certificate SHA-256 digest: '+CERT_A[:-1]+'\n')

    def test_sdk37_public_key_sha256_not_accepted_as_signing_certificate(self):
        with self.assertRaisesRegex(m.Refused,'missing certificate'):
            m.single_signer('V2 Signer: public key SHA-256 digest: '+CERT_A+'\n')

    def test_sdk37_wrong_scheme_certificate_consistency_refused_in_full_probe(self):
        def fmt(cert):
            return ('Verifies\nVerified using v2 scheme (APK Signature Scheme v2): true\n'
                    'Verified using v3 scheme (APK Signature Scheme v3): true\n'
                    'V2 Signer: certificate SHA-256 digest: '+cert+'\n')
        fake,_=self.mock_verifier([fmt(CERT_A),fmt(CERT_B),fmt(CERT_A)])
        with patch.object(m,'cmd',side_effect=fake):
            with self.assertRaisesRegex(m.Refused,'certificate changes'):
                m.verify_extracted_apk('apksigner',self.apk,self.index)

    def test_sdk37_api36_invalid_signature_rc_still_refused(self):
        def fmt():
            return ('Verifies\nVerified using v2 scheme (APK Signature Scheme v2): true\n'
                    'V2 Signer: certificate SHA-256 digest: '+CERT_A+'\n')
        fake,_=self.mock_verifier([fmt(),(1,fmt())])
        with patch.object(m,'cmd',side_effect=fake):
            with self.assertRaisesRegex(m.Refused,'API36 refused'):
                m.verify_extracted_apk('apksigner',self.apk,self.index)

    def test_sdk37_v2_missing_on_24_27_still_refused(self):
        def fmt(v2):
            return ('Verifies\nVerified using v2 scheme (APK Signature Scheme v2): '
                    +str(v2).lower()+'\n'
                    'Verified using v3 scheme (APK Signature Scheme v3): true\n'
                    'V3.0 Signer: certificate SHA-256 digest: '+CERT_A+'\n')
        fake,_=self.mock_verifier([fmt(True),fmt(True),fmt(False)])
        with patch.object(m,'cmd',side_effect=fake):
            with self.assertRaisesRegex(m.Refused,'v2 signing not cryptographically proven'):
                m.verify_extracted_apk('apksigner',self.apk,self.index)

    def test_sdk37_mixed_old_new_same_cert_allowed_and_distinct_cert_refused(self):
        ok=('Signer #1 certificate SHA-256 digest: '+CERT_A+'\n'
            'V2 Signer: certificate SHA-256 digest: '+CERT_A+'\n')
        self.assertEqual(m.single_signer(ok),CERT_A)
        with self.assertRaisesRegex(m.Refused,'different certificates'):
            m.single_signer(ok.replace('V2 Signer: certificate SHA-256 digest: '+CERT_A,
                                       'V2 Signer: certificate SHA-256 digest: '+CERT_B))

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(MatrixSecurityTest)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():raise SystemExit(1)
    print('R3C06_HF10_BUNDLETOOL_SECURITY_PASS='+str(result.testsRun))
