#!/usr/bin/env python3
"""Negative source mutations for the C02 boundary; no live Play required."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
files = {
    'proof': ROOT / 'app/src/main/java/com/aurora/store/data/installer/verification/R3bVerifiedProof.kt',
    'store': ROOT / 'app/src/main/java/com/aurora/store/data/room/play/PlayVerifiedEvidenceStore.kt',
    'worker': ROOT / 'app/src/main/java/com/aurora/store/data/work/DownloadWorker.kt',
    'receiver': ROOT / 'app/src/main/java/com/aurora/store/data/receiver/BaseInstallerStatusReceiver.kt',
}
sources = {key: path.read_text() for key, path in files.items()}
checks = [
    ('proof', 'private constructor(', 'constructor('),
    ('proof', 'ApkSetVerifier.verify(context, download, interrupted)', 'Unit'),
    ('proof', 'if (interrupted())', 'if (false)'),
    ('proof', 'MessageDigest.getInstance(algorithm)', 'SHA256_UNCHECKED'),
    ('store', 'database.withTransaction', 'run {'),
    ('store', 'evidenceDao.currentProcessingAttempt(', 'evidenceDao.latest('),
    ('store', 'evidenceDao.selectedAccountIdentity(key.packageName) != selectedAccount', 'false'),
    ('store', 'current.status != DownloadStatus.VERIFYING', 'false'),
    ('store', 'existing.key() != key', 'false'),
    ('store', 'Event.BytesDownloaded(', 'Event.UrlsResolved('),
    ('store', 'Event.R3bVerifiedSet(', 'Event.UrlsResolved('),
    ('store', 'Event.VerifiedManifestSdkIncompatible(', 'Event.InstallFailed('),
    ('store', 'evidence.verifiedApkVersion != versionCode', 'false'),
    ('store', 'key.accountBinding != fingerprint', 'false'),
    ('worker', '            recordC02Bytes()', '            // deleted bytes evidence call'),
    ('worker', '            recordC02Verified(proof)', '            // deleted verified evidence call'),
    ('worker', '                recordC02SdkIncompatible(proof)', '                // deleted sdk evidence call'),
    ('worker', 'R3bVerifiedProof.verify(context, download) { isStopped }',
     'ApkSetVerifier.verify(context, download) { isStopped }'),
    ('receiver', 'status != PackageInstaller.STATUS_FAILURE_ABORTED', 'true'),
]

def guards(source):
    def has(name, fragment):
        return fragment in source[name]

    proof = source['proof']
    store = source['store']
    worker = source['worker']
    receiver = source['receiver']
    return all((
        has('proof', 'private constructor('),
        has('proof', 'ApkSetVerifier.verify(context, download, interrupted)'),
        has('proof', 'if (interrupted())'),
        has('proof', 'MessageDigest.getInstance(algorithm)'),
        has('store', 'database.withTransaction'),
        has('store', 'evidenceDao.currentProcessingAttempt('),
        has('store', 'evidenceDao.selectedAccountIdentity(key.packageName) != selectedAccount'),
        has('store', 'current.status != DownloadStatus.VERIFYING'),
        has('store', 'existing.key() != key'),
        has('store', 'Event.BytesDownloaded('),
        has('store', 'Event.R3bVerifiedSet('),
        has('store', 'Event.VerifiedManifestSdkIncompatible('),
        has('store', 'evidence.verifiedApkVersion != versionCode'),
        has('store', 'key.accountBinding != fingerprint'),
        has('worker', '            recordC02Bytes()'),
        has('worker', '            recordC02Verified(proof)'),
        has('worker', '                recordC02SdkIncompatible(proof)'),
        has('worker', 'R3bVerifiedProof.verify(context, download) { isStopped }'),
        has('receiver', 'status != PackageInstaller.STATUS_FAILURE_ABORTED'),
    ))

assert guards(sources)
for name, old, replacement in checks:
    assert old in sources[name], (name, old)
    candidate = dict(sources)
    candidate[name] = candidate[name].replace(old, replacement)
    if guards(candidate):
        raise AssertionError('R3C03_C02_NEGATIVE_REFUSED: unsafe mutation accepted: ' + old)
print(f'R3C03_C02_SECURITY_PASS: {len(checks)} unsafe mutations rejected')
