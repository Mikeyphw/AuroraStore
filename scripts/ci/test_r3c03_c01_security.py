#!/usr/bin/env python3
"""Negative source-security mutations: omissions must fail closed."""
from pathlib import Path
from r3c03_c01_security import validate_sources

ROOT = Path(__file__).resolve().parents[2]
paths = {
    'worker': 'app/src/main/java/com/aurora/store/data/work/DownloadWorker.kt',
    'classifier': 'app/src/main/java/com/aurora/store/data/model/PlayDeliveryFailureClassifier.kt',
    'dao': 'app/src/main/java/com/aurora/store/data/room/play/PlayDeliveryEvidenceDao.kt',
    'fingerprint': 'app/src/main/java/com/aurora/store/data/model/PlayAccountFingerprint.kt',
    'migration': 'app/src/main/java/com/aurora/store/data/room/MigrationHelper.kt',
}
originals = {name: (ROOT / rel).read_text() for name, rel in paths.items()}


def check(sources):
    return validate_sources(**sources)


assert check(originals)
mutations = [
    ('worker', 'is PlayException.RateLimited,', 'is Exception,'),
    ('worker', 'is PlayException.ServerError,', ''),
    ('worker', 'PlayAccountFingerprint.hmacHex(key, id)', 'id'),
    ('worker', 'deliveryClient === noAuthPlayClient -> "anonymous"',
     'deliveryClient === noAuthPlayClient -> "authenticated"'),
    ('worker', 'selectedKey.copy(variant = "${selectedKey.variant};lane:$route")',
     'selectedKey'),
    ('worker', 'selectedAccount = selectedPlayAccount ?: return',
     'selectedAccount = "unbound"'),
    ('worker', 'storePlayOutcome("URLS_RESOLVED", resolved.size)',
     'storePlayOutcome("VERIFIED_SET", resolved.size)'),
    ('worker', 'PlayDeliveryFailureClassifier.classify(exception)', 'null'),
    ('worker', 'R.string.r3c03_delivery_not_proven_unavailable',
     'R.string.download_version_unavailable'),
    ('classifier', 'is PlayException.RateLimited ->',
     'is PlayException.Unknown ->'),
    ('classifier', 'is PlayException.ServerError ->',
     'is PlayException.Unknown ->'),
    ('classifier', 'is PlayException.AppNotSupported,', 'is PlayException.RateLimited,'),
    ('classifier', 'PlayExactVersionOutcomePolicy.Failure.AMBIGUOUS_PLAY_REJECTION',
     'PlayExactVersionOutcomePolicy.Failure.RATE_LIMITED'),
    ('dao', '@Transaction', ''),
    ('dao', 'downloadedAt = :attemptGeneration', 'downloadedAt != :attemptGeneration'),
    ('dao', 'currentProcessingAttempt(packageName, versionCode, attemptGeneration) != 1',
     'currentProcessingAttempt(packageName, versionCode, attemptGeneration) != 0'),
    ('dao', 'selectedAccountIdentity(packageName) != selectedAccount',
     'selectedAccountIdentity(packageName) == selectedAccount'),
    ('dao', 'stored.key() != key', 'stored.key() == key'),
    ('dao', 'PlayExactVersionOutcomePolicy.reduce(key, prior, event)',
     'PlayExactVersionOutcomePolicy.reduce(key, null, event)'),
    ('fingerprint', 'require(secret.size == 32)', 'require(secret.isNotEmpty())'),
    ('fingerprint', 'Mac.getInstance("HmacSHA256")', 'Mac.getInstance("HmacSHA1")'),
    ('migration', 'val MIGRATION_15_16 = object : Migration(15, 16)',
     'val MIGRATION_16_17 = object : Migration(16, 17)'),
    ('migration', 'CREATE TABLE IF NOT EXISTS `play_delivery_evidence`',
     'CREATE TABLE IF NOT EXISTS `arbitrary`'),
]
for name, before, after in mutations:
    assert before in originals[name], (name, before)
    altered = dict(originals)
    altered[name] = altered[name].replace(before, after, 1)
    try:
        check(altered)
    except ValueError:
        pass
    else:
        raise AssertionError('C01_SECURITY_TEST_REFUSED: accepted unsafe mutation: ' + before)
print(f'R3C03_C01_NEGATIVE_SECURITY_PASS: {len(mutations)} mutations rejected')
