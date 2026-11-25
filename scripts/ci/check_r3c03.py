#!/usr/bin/env python3
"""R3C-03/01 exact-version evidence reducer source contract (no live Play claims)."""
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import re

root = Path(__file__).resolve().parents[2]
model = (root / 'app/src/main/java/com/aurora/store/data/model/PlayExactVersionOutcomePolicy.kt').read_text()
tests = (root / 'app/src/test/java/com/aurora/store/data/model/PlayExactVersionOutcomePolicyTest.kt').read_text()
workflow = (root / '.github/workflows/aurora-foundation.yml').read_text()
doc = (root / 'docs/R3C03_EXACT_PLAY_OUTCOME_FOUNDATION.md').read_text()

def compact_code(text):
    # Formatting must not turn safe Kotlin line wrapping into a false failure.
    without_comments = re.sub(r'//[^\n]*|/\*[\s\S]*?\*/', '', text)
    return re.sub(r'\s+', '', without_comments)


normalized = compact_code(model)
for marker in (
    'data class RequestKey(',
    'val packageName: String',
    'val versionCode: Long',
    'val attemptGeneration: Long',
    'val accountBinding: String?',
    'val variant: String?',
    'Source.GOOGLE_PLAY',
    'fun reduce(active: RequestKey, previous: Snapshot?, event: Event): Snapshot?',
    'event.key != active',
    'previous.key != active',
    'State.EXACT_VERSION_UNAVAILABLE',
    'State.URLS_RESOLVED_NOT_VERIFIED',
    'State.BYTES_DOWNLOADED_NOT_VERIFIED',
    'State.VERIFIED_SET',
    'UnavailabilityProof.EXPLICIT_EXACT_VERSION_DELIVERY_REFUSAL',
    'event.refusedVersion != version',
    'current.state == State.VERIFIED_SET',
    'event.resolvedVersion != version',
    'event.downloadedVersion != version',
    'current.resolvedFileCount != event.fileCount',
    'current.state != State.BYTES_DOWNLOADED_NOT_VERIFIED',
    'event.verifiedVersion != version',
    'current.resolvedFileCount != event.verifiedFileCount',
    'current.verifiedApkVersion != version',
):
    assert compact_code(marker) in normalized, f'R3C03_REFUSED: missing {marker}'

for marker in (
    'staleAttemptGenerationIsDropped',
    'changedAccountAndVariantAreDropped',
    'timeoutNeverProvesUnavailable',
    'rateLimitAndAuthErrorsNeverProveUnavailable',
    'ambiguousPlayRejectionIsNotUnavailable',
    'onlyExactVersionRefusalCreatesUnavailableEvidence',
    'bytesCannotSkipResolvedUrls',
    'verificationCannotSkipDownloadOrUseOtherVersion',
    'verifiedSetIsOnlyReachedAfterExactSequence',
    'refusalCannotOverrideVerifiedSet',
):
    assert marker in tests, f'R3C03_REFUSED: missing regression {marker}'
assert len(re.findall(r'@Test\s+fun\s+', tests)) >= 20
assert workflow.count('python3 -B scripts/ci/check_r3c03.py') == 1
assert workflow.count('python3 -B scripts/ci/test_r3c03_contract.py') == 1
assert 'not wired to DownloadWorker' in doc
assert 'R3B' in doc and 'no live Play proof' in doc
print('R3C03_01_SOURCE_PASS: exact generation/account/variant, 20+ JVM regressions, no false live claims')
