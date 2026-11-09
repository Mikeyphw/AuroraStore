#!/usr/bin/env python3
"""Fail-closed static source guard. Hosted Kotlin/Room tests remain mandatory."""
from pathlib import Path
from r3c03_c01_security import validate_sources
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]


def code(path):
    return (ROOT / path).read_text(encoding='utf-8')


def require(path, markers):
    source = code(path)
    compact = re.sub(r'\s+', '', source)
    for marker in markers:
        if re.sub(r'\s+', '', marker) not in compact:
            raise SystemExit(f'R3C03_C01_REFUSED: {path} missing {marker}')
    return source


worker = require('app/src/main/java/com/aurora/store/data/work/DownloadWorker.kt', (
    'private val playDeliveryEvidenceDao: PlayDeliveryEvidenceDao',
    'playEvidenceKey = PlayExactVersionOutcomePolicy.RequestKey(',
    'attemptGeneration = download.downloadedAt',
    'accountBinding = privateAccountTag(selected)',
    'selectedAccount = selectedPlayAccount ?: return',
    'SecureRandom().nextBytes(generated)',
    'PlayAccountFingerprint.hmacHex(key, id)',
    'selectedKey.copy(variant = "${selectedKey.variant};lane:$route")',
    'storePlayOutcome("URLS_RESOLVED", resolved.size)',
    'PlayDeliveryFailureClassifier.classify(exception)',
    'R.string.r3c03_delivery_not_proven_unavailable',
    'R.string.r3c03_delivery_requires_account',
    'R3bVerifiedProof.verify(context, download) { isStopped }',
    'if (BuildConfig.DEBUG && R1EOfflineGate.enabled(inputData))',
))
if 'R.string.download_version_unavailable' in worker:
    raise SystemExit('R3C03_C01_REFUSED: ambiguous Play rejection still claims unavailable')
if worker.count('storePlayOutcome("URLS_RESOLVED", resolved.size)') != 1:
    raise SystemExit('R3C03_C01_REFUSED: unbounded URL-success evidence')
if not worker.index('if (BuildConfig.DEBUG && R1EOfflineGate.enabled(inputData))') < worker.index(
    'playEvidenceKey = PlayExactVersionOutcomePolicy.RequestKey('
):
    raise SystemExit('R3C03_C01_REFUSED: fixture path may contaminate real Play evidence')

entity = require('app/src/main/java/com/aurora/store/data/room/play/PlayDeliveryEvidence.kt', (
    '@Entity(tableName = "play_delivery_evidence")',
    '@PrimaryKey val packageName: String',
    'val versionCode: Long',
    'val attemptGeneration: Long',
    'val accountBinding: String',
    'val variant: String',
    'val verifiedApkVersion: Long?',
    'val unavailableVersion: Long?',
))
if re.search(r'\b(token|password|email|url)\s*:', entity, flags=re.I):
    raise SystemExit('R3C03_C01_REFUSED: sensitive evidence field')

dao = require('app/src/main/java/com/aurora/store/data/room/play/PlayDeliveryEvidenceDao.kt', (
    '@Transaction', 'downloadedAt = :attemptGeneration',
    'selectedAccountIdentity(packageName) != selectedAccount',
    'stored.key() != key', 'PlayExactVersionOutcomePolicy.reduce(key, prior, event)',
    'PlayExactVersionOutcomePolicy.Event.UrlsResolved(',
    'PlayExactVersionOutcomePolicy.Event.Failed(',
))
if 'ExactVersionRefused(' in dao or 'R3bVerifiedSet(' in dao:
    raise SystemExit('R3C03_C01_REFUSED: C01 cannot manufacture verification or refusal')
require('app/src/main/java/com/aurora/store/data/room/AuroraDatabase.kt', (
    'version = 16', 'PlayDeliveryEvidence::class',
    'abstract fun playDeliveryEvidenceDao(): PlayDeliveryEvidenceDao',
))
require('app/src/main/java/com/aurora/store/data/room/RoomModule.kt', (
    'MIGRATION_15_16', 'providesPlayDeliveryEvidenceDao(',
))
require('app/src/main/java/com/aurora/store/data/room/MigrationHelper.kt', (
    'val MIGRATION_15_16 = object : Migration(15, 16)',
    'CREATE TABLE IF NOT EXISTS `play_delivery_evidence`',
    'PRIMARY KEY(`packageName`)',
))
classification = require('app/src/main/java/com/aurora/store/data/model/PlayDeliveryFailureClassifier.kt', (
    'is PlayException.AppNotSupported,',
    'Failure.AMBIGUOUS_PLAY_REJECTION',
    'is PlayException.RequiresAccount ->', 'Failure.ACCOUNT_REQUIRED',
    'is PlayException.AppNotPurchased ->', 'Failure.ACCESS_DENIED',
    'is PlayException.RateLimited ->', 'Failure.RATE_LIMITED',
    'is PlayException.ServerError ->', 'Failure.TEMPORARY_SERVER_ERROR',
    'is IOException ->', 'Failure.NETWORK_TIMEOUT',
))
if 'EXACT_VERSION_UNAVAILABLE' in classification:
    raise SystemExit('R3C03_C01_REFUSED: failure mapper forged unavailable proof')
resource = ROOT / 'app/src/main/res/values/strings_r3c03_c01.xml'
ET.parse(resource)
workflow = require('.github/workflows/aurora-foundation.yml', (
    'python3 -B scripts/ci/check_r3c03_c01.py',
    'python3 -B scripts/ci/test_r3c03_c01_sql.py',
    'python3 -B scripts/ci/test_r3c03_c01_security.py',
    'sha256sum --check -',
    'https://api.github.com/repos/ktlint/ktlint/releases/assets/316074525',
))
if workflow.count('python3 -B scripts/ci/check_r3c03_c01.py') != 1:
    raise SystemExit('R3C03_C01_REFUSED: CI contract not unique')
fingerprint = require('app/src/main/java/com/aurora/store/data/model/PlayAccountFingerprint.kt', (
    'Mac.getInstance("HmacSHA256")', 'require(secret.size == 32)',
))
migration = code('app/src/main/java/com/aurora/store/data/room/MigrationHelper.kt')
validate_sources(worker, classification, dao, fingerprint, migration)
print('R3C03_C01_SOURCE_CONTRACT_PASS: Play-only evidence, Room CAS, safe failure labels')
