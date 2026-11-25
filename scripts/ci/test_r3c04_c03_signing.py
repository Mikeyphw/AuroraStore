#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""C04-03 HF08 source contracts; no simulated signature proof or device execution."""
from pathlib import Path
root = Path(__file__).resolve().parents[2]
base = root / "app/src/main/java/com/aurora/store/data/artifact"
tests = root / "app/src/test/java/com/aurora/store/data/artifact/ArtifactApkIdentityPolicyTest.kt"
device = root / "app/src/androidTest/java/com/aurora/store/data/artifact/ArtifactApkVerifierDeviceTest.kt"
verify = (base / "ArtifactApkVerifier.kt").read_text()
policy = (base / "ArtifactApkIdentityPolicy.kt").read_text()
unit = tests.read_text()
actual_device = device.read_text()
play = (root / "app/src/main/java/com/aurora/store/data/room/play/PlayVerifiedEvidenceStore.kt").read_text()
runner = (root / "scripts/ci/r3c03_c02_emulator_ci.sh").read_text()

def need(ok, why):
    if not ok: raise SystemExit('R3C04_C03_HF08_REFUSED: '+why)

for marker in ('private fun signedManifest(', 'entry.name == "AndroidManifest.xml"',
               'manifestCount != 1', 'BinaryApkManifest.read(file)',
               'ArtifactApkIdentityPolicy.requireManifestIdentity(',
               'ArtifactApkIdentityPolicy.requirePlatformAgreement(',
               'ArtifactApkIdentityPolicy.installedSignerStatus(',
               'getVerifiedSigningInfo(', 'SigningInfo.VERSION_SIGNING_BLOCK_V2',
               'Build.VERSION.SDK_INT < 36', 'ArtifactPrivateStager.sha256(',
               'Verified APK bytes changed during inspection',
               'Verified APK bytes changed before session creation'):
    need(marker in verify, 'missing verifier contract '+marker)
need(verify.count('ArtifactApkIdentityPolicy.requireUniqueSplitNames(') == 2,
     'initial and install-time split-set validation must match')
need(verify.count('signedManifest(part.file)') == 2, 'verification/revalidation manifest parity lost')
need(verify.count('signerFor(manager, part.file,') == 2,
     'verification/revalidation signer/platform parity lost')
need('compatibleInstalledSigners(' not in verify, 'history-only Play compatibility leaked into local imports')
need('get() = false' in verify and 'PlayVerifiedEvidenceStore' not in verify,
     'source-independent verifier cannot mint Play evidence')
for marker in ('ACTIVE_MATCH', 'HISTORY_ONLY_UNVERIFIED', 'MISMATCH',
               'candidate == installedActive', 'fun requireUniqueSplitNames(', 'candidate.single() in installedHistory',
               'packageName != platformPackage || versionCode != platformVersion',
               'isBase && platformPackage == null', 'splitName == "base"'):
    need(marker in policy, 'missing conservative identity decision '+marker)
need(unit.count('@Test') >= 15, 'C04-03 policy negative JVM matrix too small')
need(actual_device.count('@Test') == 7, 'expected exactly seven signing/identity device tests')
need(r"grep -Eq '^OK \(7 tests\)'" in runner and
     'ArtifactApkVerifierDeviceTest' in runner,
     'real signing/identity instrumentation not wired to seven-case API36 gate')
need('PlayExactVersionOutcomePolicy.Source.GOOGLE_PLAY' in play,
     'Play evidence gate regressed')
print('R3C04_C03_HF08_SOURCE_PASS: exact manifest, Android archive identity, v2 signing, split/signature, active installed signer and API36 gate')
