#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""C04-01 source and negative-proof gate. No mocked Play/network or Android installation."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / 'app/src/main/java/com/aurora/store/data/artifact'
POLICY = ARTIFACT / 'ArtifactAttemptPolicy.kt'
SOURCE = ARTIFACT / 'ArtifactProvenance.kt'
VERIFIED = ARTIFACT / 'VerifiedApkSet.kt'
TESTS = ROOT / 'app/src/test/java/com/aurora/store/data/artifact/ArtifactAttemptPolicyTest.kt'
PLAY = ROOT / 'app/src/main/java/com/aurora/store/data/room/play/PlayVerifiedEvidenceStore.kt'
DOC = ROOT / 'docs/R3C04_SOURCE_BOUNDARY.md'


def require(condition, message):
    if not condition:
        raise SystemExit('R3C04_C01_SOURCE_REFUSED: ' + message)


for p in (SOURCE, POLICY, VERIFIED, TESTS, PLAY, DOC):
    require(p.is_file(), 'missing ' + str(p.relative_to(ROOT)))
source, policy, verified = (p.read_text() for p in (SOURCE, POLICY, VERIFIED))
tests, play, doc = (p.read_text() for p in (TESTS, PLAY, DOC))

for value in ('LOCAL_DOCUMENT', 'DEVELOPER_WEBSITE', 'GITHUB_RELEASE',
              'APKMIRROR_BROWSER_HANDOFF', 'FDROID_REPOSITORY', 'APKPURE_OPT_IN'):
    require(value in source, 'missing non-Play origin ' + value)
require('GOOGLE_PLAY' not in source, 'non-Play origin masquerades as Google Play')
require('isVerifiedPlayDelivery' in source and 'get() = false' in source,
        'candidate metadata might imply verified Play evidence')
require('APK_SIGNER_VALID_PUBLISHER_UNANCHORED' in source and
        'VERIFIED_PUBLISHER_IDENTITY' in source, 'signing and publisher trust conflated')
require('content://' not in source and 'ACTION_OPEN_DOCUMENT' not in source,
        'source model improperly binds Android URI permissions')
require('private constructor(' in verified and 'companion object' not in verified,
        'verified APK set can be minted without real verifier')
require('get() = false' in verified, 'non-Play verified type claims Play evidence')
require('private val SHA256_PATTERN' in policy and 'sizeBytes <= 0L' in policy,
        'copy-digest bounds missing')
require('event.attempt != active' in policy and 'previous.attempt != active' in policy,
        'stale/foreign generation check missing')
require('current.stage == Stage.FAILED || current.stage == Stage.CANCELLED' in policy,
        'terminal states can resume')
require('current.stage != Stage.USER_SELECTED_DOCUMENT' in policy,
        'unselected bytes can be accepted')
require('VERIFIED_SET' not in policy and 'PLAY_VERIFIED' not in policy,
        'attempt stages must not encode verified or Play status')
require(play.count('R3bVerifiedProof') >= 2 and 'PlayExactVersionOutcomePolicy.Source.GOOGLE_PLAY' in play,
        'existing Play-only proof boundary missing')
require(tests.count('@Test') >= 12 and 'noPublicVerifiedApkSetConstructorOrFactory' in tests,
        'negative JVM tests missing')
require('C04-03' in doc and 'not an installer' in doc.lower(), 'roadmap disclaimer missing')
print('R3C04_C01_SOURCE_BOUNDARY_PASS: non-Play model, unmintable proof, stale-generation and provenance tests')

# C04-01 HF06: the old unmintable placeholder is not the real C04-03 producer.
# Audit the actual verifier/import path rather than trusting an old comment.
exec(compile((ROOT / "scripts/ci/test_r3c04_c01_origin.py").read_text(),
             "test_r3c04_c01_origin.py", "exec"))
