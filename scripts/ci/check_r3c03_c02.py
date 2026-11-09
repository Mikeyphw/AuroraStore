#!/usr/bin/env python3
"""R3C-03 C02 production-path source requirements. Not a substitute for Android tests."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def get(path):
    return (ROOT / path).read_text(encoding='utf-8')


def compact(s):
    return re.sub(r'\s+', '', re.sub(r'/\*[\s\S]*?\*/|//[^\n]*', '', s))


def require(file, marker):
    source = compact(get(file))
    if compact(marker) not in source:
        raise SystemExit(f'R3C03_C02_SOURCE_REFUSED: {file} missing {marker}')
    return source

worker = 'app/src/main/java/com/aurora/store/data/work/DownloadWorker.kt'
receiver = 'app/src/main/java/com/aurora/store/data/receiver/BaseInstallerStatusReceiver.kt'
store = 'app/src/main/java/com/aurora/store/data/room/play/PlayVerifiedEvidenceStore.kt'
proof = 'app/src/main/java/com/aurora/store/data/installer/verification/R3bVerifiedProof.kt'

for marker in (
    'private val verifiedPlayEvidenceStore: PlayVerifiedEvidenceStore',
    'recordC02Bytes()',
    'R3bVerifiedProof.verify(context, download) { isStopped }',
    'recordC02Verified(proof)',
    'recordC02SdkIncompatible(proof)',
    'VerifiedSdkIncompatibleException()',
    'if (BuildConfig.DEBUG && R1EOfflineGate.enabled(inputData))',
):
    require(worker, marker)
for marker in (
    'ApkSetVerifier.verify(context, download, interrupted)',
    'private constructor(',
    'throw ApkVerificationException("APK verification was cancelled")',
    'context.packageManager.getPackageArchiveInfo(file.absolutePath, 0)',
    'MessageDigest.getInstance(algorithm)',
):
    require(proof, marker)
for marker in (
    'database.withTransaction',
    'evidenceDao.currentProcessingAttempt(',
    'evidenceDao.selectedAccountIdentity(key.packageName) != selectedAccount',
    'current.status != DownloadStatus.VERIFYING',
    'existing.key() != key',
    'Event.BytesDownloaded(',
    'Event.R3bVerifiedSet(',
    'Event.InstallFailed(',
    'Event.VerifiedManifestSdkIncompatible(',
    'minSdk <= Build.VERSION.SDK_INT',
    'evidence.verifiedApkVersion != versionCode',
    'PlayAccountFingerprint.hmacHex(secretBytes, selected)',
):
    require(store, marker)
for marker in (
    'fun playVerifiedEvidenceStore(): PlayVerifiedEvidenceStore',
    'playVerifiedEvidenceStore().installerFailed(',
    'status != PackageInstaller.STATUS_FAILURE_ABORTED',
):
    require(receiver, marker)

raw = get(worker)
# Check call-sites in the *real download method*, not earlier helper declarations.
transfer = raw.index('for (file in files) {')
verifying = raw.index('if (!notifyStatus(DownloadStatus.VERIFYING))', transfer)
bytes_call = raw.index('            recordC02Bytes()', verifying)
proof_call = raw.index('R3bVerifiedProof.verify(context, download) { isStopped }', bytes_call)
verified_call = raw.index('            recordC02Verified(proof)', proof_call)
sdk_call = raw.index('                recordC02SdkIncompatible(proof)', verified_call)
completed = raw.index('if (!notifyStatus(DownloadStatus.COMPLETED))', sdk_call)
if not (transfer < verifying < bytes_call < proof_call < verified_call < sdk_call < completed):
    raise SystemExit('R3C03_C02_SOURCE_REFUSED: evidence transitions are out of order')
# Fixture is a separate earlier return, so cannot mint live Play evidence.
fixture = raw.index('if (BuildConfig.DEBUG && R1EOfflineGate.enabled(inputData))')
if fixture >= transfer:
    raise SystemExit('R3C03_C02_SOURCE_REFUSED: fixture not isolated from Play evidence')
if 'Event.R3bVerifiedSet' in get('app/src/main/java/com/aurora/store/data/room/play/PlayDeliveryEvidenceDao.kt'):
    raise SystemExit('R3C03_C02_SOURCE_REFUSED: C01 Play result DAO was weakened')
print('R3C03_C02_SOURCE_PASS: production R3B proof, generation/account CAS, installer receipt')

require('app/src/main/res/values/strings_r3c03_c02.xml', 'r3c03_c02_verified_sdk_incompatible')
