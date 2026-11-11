#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R3C06 P6 additive source & negative gate. Not an API36 runtime PASS."""
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
FIX=ROOT/'scripts/ci/fixtures/r3c06_feature_bundle'
RUNNER=(ROOT/'scripts/ci/r3c03_c02_emulator_ci.sh').read_text()
WORKFLOW=(ROOT/'.github/workflows/aurora-r1d-emulator.yml').read_text()
AGGREGATE=(ROOT/'scripts/ci/test_r3c04_full_import.py').read_text()
COMPOSITE=(ROOT/'scripts/ci/r3c06_p6_composite_receipt.py').read_text()
INSPECT=(ROOT/'scripts/ci/r3c06_p6_feature_aab.py').read_text()
MATRIX=(ROOT/'scripts/ci/r3c06_bundletool_matrix.py').read_text()

for path in ('settings.gradle.kts','build.gradle.kts','gradle.properties',
             'app/build.gradle.kts','app/src/main/AndroidManifest.xml',
             'featureproof/build.gradle.kts','featureproof/src/main/AndroidManifest.xml',
             'featureproof/src/main/res/values/strings.xml',
             'featureproof/src/main/assets/qualification.marker'):
    assert (FIX/path).is_file(), 'P6 missing independent fixture file: '+path
assert 'com.android.dynamic-feature' in (FIX/'build.gradle.kts').read_text()
assert 'com.android.dynamic-feature' in (FIX/'featureproof/build.gradle.kts').read_text()
assert 'dynamicFeatures.add(":featureproof")' in (FIX/'app/build.gradle.kts').read_text()
assert 'implementation(project(":app"))' in (FIX/'featureproof/build.gradle.kts').read_text()
assert 'com.aurora.r3c06.featurefixture' in (FIX/'app/build.gradle.kts').read_text()
assert 'com.aurora.store' not in (FIX/'app/build.gradle.kts').read_text()
assert '9.4.1' in (FIX/'build.gradle.kts').read_text(), 'AGP fixture pin changed'
ns='{http://schemas.android.com/apk/distribution}'
xml=ET.parse(FIX/'featureproof/src/main/AndroidManifest.xml').getroot()
module=xml.find(ns+'module')
assert module is not None and module.find(ns+'delivery/'+ns+'on-demand') is not None
assert module.find(ns+'delivery/'+ns+'install-time') is None
assert module.find(ns+'fusing').get(ns+'include')=='false'
assert (FIX/'featureproof/src/main/assets/qualification.marker').read_bytes() == b'R3C06_FEATUREPROOF_ON_DEMAND_FIXTURE_ONLY\n'

for token in ('r3c06_feature_matrix:', 'default: false',
              'R3C06_P6_FEATURE_AAB=', 'bundletool-all-1.18.3.jar',
              'r3c06_p6_composite_receipt.py', 'r3c06_p6_feature_aab.py',
              'R3C06_P6_PRODUCTION_REQUESTED', 'R3C06_P6_MATRIX_REQUIRED'):
    assert token in WORKFLOW or token in RUNNER or token in (WORKFLOW+RUNNER), 'P6 source/CI wiring missing '+token
assert 'if: ${{ inputs.r3c06_feature_matrix == true }}' in WORKFLOW
assert ':app:bundleDebug' in WORKFLOW
assert 'r3c06_live_install=false' in WORKFLOW or 'R3C06_ALLOW_LIVE_INSTALL' in WORKFLOW
assert 'R3C06_P6_FEATURE_AAB' in RUNNER and '--feature featureproof' in RUNNER
assert 'r3c06_p6_composite_receipt.py' in WORKFLOW
assert 'test_r3c06_p6_source.py' in AGGREGATE
assert 'r3c06_p5_manual_receipt' in COMPOSITE
for token in ('same_aab_all_five_dimensions_qualified','production_dynamic_feature_qualified',
              'on_demand','physical_device_qualified','release_qualified','publisher_authenticated',
              "require(set(feature['coverage'])==set(DIMS)|{FEATURE_KEY}"):
    assert token in COMPOSITE, 'P6 scope/truth guard missing '+token
for token in ('dist:module','module','on_demand', 'feature_marker_verified',
              'bundletool', 'featureproof/assets/qualification.marker'):
    assert token in INSPECT or token in (FIX/'featureproof/src/main/AndroidManifest.xml').read_text()
assert '--feature' in MATRIX and 'verify_extracted_apk(' in MATRIX
assert "'dump','manifest'" in INSPECT and "'--output='" not in INSPECT, 'bundletool dump manifest has no --output flag'
assert 'PlayVerifiedEvidenceStore' not in COMPOSITE + INSPECT
assert 'install-apks' not in WORKFLOW + RUNNER
assert 'git push' not in COMPOSITE + INSPECT
# Actual post-change Python negatives, not just counted test names.
r=subprocess.run([sys.executable,'-B','scripts/ci/test_r3c06_p6_composite.py'],
                 cwd=ROOT,capture_output=True,text=True,timeout=60)
assert r.returncode==0, 'P6 negative suite failed: '+(r.stdout+r.stderr)[-5000:]
assert 'Ran 19 tests' in r.stderr, 'P6 negative count stale'
print('R3C06_P6_SOURCE_AND_19_NEGATIVES_PASS: dynamic-feature CI wired, no false production feature claim')
