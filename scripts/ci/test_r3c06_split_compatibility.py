#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R3C06 fail-closed split targeting contract. Source checks; API36 tests are separate."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / 'app/src/main/java/com/aurora/store/data/artifact'
UNIT = ROOT / 'app/src/test/java/com/aurora/store/data/artifact/ArtifactSplitCompatibilityPolicyTest.kt'
DEVICE = ROOT / 'app/src/androidTest/java/com/aurora/store/data/artifact/ArtifactSplitCompatibilityDeviceTest.kt'
RUNNER = ROOT / 'scripts/ci/r3c03_c02_emulator_ci.sh'
POLICY = ART / 'ArtifactSplitCompatibilityPolicy.kt'
VERIFY = ART / 'ArtifactApkVerifier.kt'
PLAY = ROOT / 'app/src/main/java/com/aurora/store/data/room/play/PlayVerifiedEvidenceStore.kt'
def guard(ok, reason):
    if not ok: raise SystemExit('R3C06_SPLIT_REFUSED: '+reason)
for p in (UNIT,DEVICE,RUNNER,POLICY,VERIFY,PLAY): guard(p.is_file(),f'missing {p}')
p=POLICY.read_text(); v=VERIFY.read_text(); d=DEVICE.read_text(); r=RUNNER.read_text()
for needle in ('Multiple APK variant targets need an authenticated split selector',
               'APK set targets an unsupported device ABI',
               'Unqualified split targeting requires verified bundletool selection',
               'owner !in names', 'featureDependenciesUnverified',
               'installabilityConfirmed: Boolean = false'):
    guard(needle in p, 'missing safety behavior: '+needle)
guard(v.count('ArtifactSplitCompatibilityPolicy.check(')==2, 'missing fresh verify/revalidate topology checks')
guard('val abiSplits =' not in v, 'stale substring ABI heuristic still present')
guard('PlayVerifiedEvidenceStore' not in p+v, 'non-Play topology uses Play proof')
guard(UNIT.read_text().count('@Test')>=15, 'insufficient Kotlin negative tests')
guard(d.count('@Test')==4 and 'Build.SUPPORTED_ABIS' in d, 'API36 device negatives missing')
guard('ArtifactSplitCompatibilityDeviceTest' in r and r.count('^OK \\(4 tests\\)')>=1,
      'R1D API36 exact-four test gate not wired')
guard('PlayExactVersionOutcomePolicy.Source.GOOGLE_PLAY' in PLAY.read_text(), 'Play isolation drift')
print('R3C06_SPLIT_TARGETING_SOURCE_PASS: no blind multiple-variant selection, exact ABI, fresh recheck and API36 lane')
