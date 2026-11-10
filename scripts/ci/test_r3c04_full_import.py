#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""C04-02..08 fail-closed structural checks; not a substitute for host Android tests."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'app/src/main/java/com/aurora/store/data/artifact'


def read(name):
    path = BASE / name
    assert path.is_file(), 'R3C04_FULL_REFUSED: missing ' + name
    return path.read_text()


def require(ok, why):
    if not ok:
        raise SystemExit('R3C04_FULL_REFUSED: ' + why)

stage = read('ArtifactPrivateStager.kt')
verify = read('ArtifactApkVerifier.kt')
archive = read('ArtifactArchivePolicy.kt')
url = read('ArtifactSourceHandoff.kt')
install = read('ArtifactInstallSession.kt')
receiver = read('ArtifactInstallStatusReceiver.kt')
activity = read('ArtifactImportActivity.kt')
review = read('ArtifactImportDecision.kt')
play = (ROOT / 'app/src/main/java/com/aurora/store/data/room/play/PlayVerifiedEvidenceStore.kt').read_text()
existing_gate = (ROOT / 'app/src/main/java/com/aurora/store/data/installer/verification/ApkSetPolicy.kt').read_text()
manifest = (ROOT / 'app/src/main/AndroidManifest.xml').read_text()
settings = (ROOT / 'app/src/main/java/com/aurora/store/compose/ui/preferences/SettingsScreen.kt').read_text()
unit_dir = ROOT / 'app/src/test/java/com/aurora/store/data/artifact'
device = ROOT / 'app/src/androidTest/java/com/aurora/store/data/artifact/ArtifactPrivateStagerDeviceTest.kt'

for label, src, needles in (
    ('SAF and private staging', stage, ['context.contentResolver.openInputStream(uri)', 'context.cacheDir',
                                     'FileOutputStream', 'output.fd.sync()', 'MAX_SOURCE_BYTES',
                                     'MAX_APK_BYTES', 'MAX_TOTAL_APK_BYTES', 'directory.deleteRecursively()',
                                     'UUID.randomUUID()', 'stage(', 'ZipFile']),
    ('real manifest/signer verification', verify, ['BinaryApkManifest.read(', 'ApkSetPolicy.check(',
                                           'getVerifiedSigningInfo(', 'signingCertificateHistory',
                                           'safeSize' if False else 'signature']),
    ('per-APK rehash', verify, ['ArtifactPrivateStager.sha256(', 'part.sha256', 'signerFor(',
                               'compatibleInstalledSigners(', 'ArtifactTrustTier.INSTALLED_SIGNER_CONTINUITY',
                               'ArtifactTrustTier.APK_SIGNER_VALID_PUBLISHER_UNANCHORED']),
    ('source isolation', url, ['"https"', 'rawUserInfo', 'rawQuery', 'APKPURE_OPT_IN',
                               'apkPureOptIn', 'github.com', 'apkmirror.com', 'f-droid.org']),
    ('archive safety', archive, ['MAX_RATIO', 'MAX_ITEMS', 'MAX_APKS', 'MAX_APK_BYTES',
                                 '"obb"' if False else '"apk"', '".."', 'MAX_SOURCE_BYTES']),
    ('Android final install authority', install, ['PackageInstaller.SessionParams',
                                    'USER_ACTION_REQUIRED', 'PACKAGE_SOURCE_LOCAL_FILE',
                                    'session.openWrite(', 'session.fsync(',
                                    'ArtifactApkVerifier.revalidateForInstall(', 'PendingIntent.getBroadcast(',
                                    'PackageInstaller.SessionParams.MODE_FULL_INSTALL']),
    ('source-bound receipt', receiver, ['recordStatus(', 'STATUS_PENDING_USER_ACTION',
                                        'startActivity(', 'Intent.EXTRA_INTENT']),
    ('user-visible consent/picker', activity, ['ActivityResultContracts.OpenDocument()',
                   'unknownPublisherConsent', 'downgradeConsent', 'installConsent',
                   'selectButton', 'cancelled.set(true)', 'review.text', 'openSourceInBrowser()']),
    ('separate review blockers', review, ['SIGNER_MISMATCH', 'DOWNGRADE_CONSENT_REQUIRED',
                                          'UNANCHORED_PUBLISHER_CONSENT_REQUIRED',
                                          'EXPLICIT_INSTALL_CONSENT_REQUIRED']),
):
    for needle in needles:
        require(needle in src, f'{label}: missing {needle}')
require('PlayVerifiedEvidenceStore' not in (stage + verify + archive + url + install + receiver + activity),
        'local importer must not write Google Play result store')
require('matchesPlayDigest(' not in verify, 'non-Play digests must never masquerade as Play proof')
require('PlayExactVersionOutcomePolicy.Source.GOOGLE_PLAY' in play, 'Play-only receipt gate regressed')
require('entry.signerDigests != baseSigners' in existing_gate, 'existing R3B signature check weakened')
require('android:exported="false"' in manifest and '.data.artifact.ArtifactImportActivity' in manifest,
        'importer activity must not be exported')
require('.data.artifact.ArtifactInstallStatusReceiver' in manifest, 'private result receiver missing')
require('ArtifactImportActivity::class.java' in settings, 'importer must be discoverable in Settings')
require(device.is_file() and device.read_text().count('@Test') >= 5,
        'API36 bounded staging adversarial instrumentation missing')
for name in ('ArtifactImportDecisionTest.kt', 'ArtifactArchivePolicyTest.kt',
             'ArtifactSourceHandoffTest.kt'):
    p = unit_dir / name
    require(p.is_file() and p.read_text().count('@Test') >= 5, 'JVM negative tests missing: ' + name)
print('R3C04_TARGETED_SOURCE_PASS: picker, bounded ZIP, exact signer, installed identity, consent, OS session, source handoff, negatives')

# HF01 regression: exact-APK session stream, bounded central-directory enumeration,
# pre-36 fail-closed signing, untrusted provider names and stale UI callbacks.
for label, condition in (
    ('bounded archive entries before allocation', 'val items = archive.entries()' in stage and 'archive.entries().toList()' not in stage and 'entryCount > ArtifactArchivePolicy.MAX_ITEMS' in stage),
    ('API 36 verified signing only', 'Build.VERSION.SDK_INT < 36' in verify and 'getVerifiedSigningInfo(' in verify and 'Independent APK signature verification requires Android API 36' in verify),
    ('repeat content digest after signature check', 'Verified APK bytes changed during inspection' in verify),
    ('session write hashes exact bytes', 'writtenHash.update(buffer, 0, n)' in install and 'APK changed while writing Android session' in install and 'written != file.byteCount' in install),
    ('SAF display filename sanitized', 'ArtifactPickerPolicy.safeDisplayLabel(name)' in activity),
    ('stale background callbacks refused', 'serial != requestSerial' in activity and 'serial == requestSerial' in activity),
    ('unbounded ZIP metadata is not materialized', '.entries().toList()' not in stage),
):
    require(condition, 'HF01 ' + label)

picker_policy = read('ArtifactPickerPolicy.kt')
require('safeDisplayLabel' in picker_policy and 'Char::isISOControl' in picker_policy,
        'HF01 safe display-name policy missing')
require((unit_dir / 'ArtifactPickerPolicyTest.kt').is_file(),
        'HF01 picker negative tests missing')
print('R3C04_HF01_SOURCE_SECURITY_PASS')

# C04-04: installation layer is independently gated by security negatives.
exec(compile((ROOT / "scripts/ci/test_r3c04_c04_install.py").read_text(), "test_r3c04_c04_install.py", "exec"))

# C04-05: provider handoffs are display-only claims and cannot survive source/opt-in changes.
exec(compile((ROOT / "scripts/ci/test_r3c04_c05_handoff.py").read_text(),
             "test_r3c04_c05_handoff.py", "exec"))
