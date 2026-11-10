#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R3C06 P3 fail-closed source contract; never mislabels compiled tests as executed."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ART=ROOT/'app/src/main/java/com/aurora/store/data/artifact'
TEST=ROOT/'app/src/androidTest/java/com/aurora/store/data/artifact'
UNIT=ROOT/'app/src/test/java/com/aurora/store/data/artifact'
RUNNER=ROOT/'scripts/ci/r3c03_c02_emulator_ci.sh'

def read(path):
    assert path.is_file(), 'R3C06_P3_REFUSED missing '+str(path)
    return path.read_text(encoding='utf-8')

verifier=read(ART/'ArtifactApkVerifier.kt')
policy=read(ART/'ArtifactFeatureDependencyPolicy.kt')
reader=read(ART/'ArtifactSignedManifestDependencies.kt')
unit=read(UNIT/'ArtifactFeatureDependencyPolicyTest.kt')
signed=read(TEST/'ArtifactRealSignedArchiveDeviceTest.kt')
install=read(TEST/'ArtifactActualInstallAcceptanceDeviceTest.kt')
runner=read(RUNNER)
script=read(ROOT/'scripts/ci/r3c06_api36_live_install.py')
oracle=read(ROOT/'scripts/ci/r3c06_bundletool_matrix.py')
for token in ('ArtifactFeatureDependencyPolicy.check(',
              'ArtifactSignedManifestDependencies.read(',
              'freshFeatureDependencies != imported.signedFeatureDependencies',
              'signedFeatureDependencies.toList()'):
    assert token in verifier, 'R3C06_P3_REFUSED missing in verifier: '+token
for token in ('dep !in present','Cyclic feature split dependencies','id == null',
              '".config." in dep','requiredSplit.size'):
    assert token in policy, 'R3C06_P3_REFUSED weakened feature checks: '+token
for token in ('ANDROID_NS','"uses-split"','CodingErrorAction.REPORT',
              'MAX = 2 * 1024 * 1024','read(file: File)'):
    assert token in reader, 'R3C06_P3_REFUSED signed manifest reader: '+token
assert unit.count('@Test') >= 12
assert signed.count('@Test') == 6
assert install.count('@Test') == 1
assert "^OK \\(6 tests\\)" in runner and 'ArtifactRealSignedArchiveDeviceTest' in runner
assert 'R3C06_ALLOW_LIVE_INSTALL' in runner and 'r3c06_api36_live_install.py' in runner
assert 'R3C06_ALLOW_LIVE_INSTALL' in script and 'com.aurora.r3c06.fixture' in script
assert 'system_consent_ui_verified' in script and "'android_callback_verified':True" in script
assert 'R3C06_BUNDLETOOL' in oracle and "'PARTIAL'" in oracle
assert "'--bundletool-sha256'" in oracle and 'apksigner' in oracle
assert 'PlayVerifiedEvidenceStore' not in (verifier+reader+policy+script+oracle)
assert 'matchesPlayDigest' not in (reader+policy)
assert 'git push' not in script and 'adb uninstall' not in script
print('R3C06_P3_ACCEPTANCE_CONTRACT_PASS: signed manifest deps, bounded signed APKM/XAPK, explicit live API36 OS consent, bundletool oracle; execution still separate')
