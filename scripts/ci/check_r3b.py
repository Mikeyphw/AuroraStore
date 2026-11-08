#!/usr/bin/env python3
"""R3B source checks; real signed APK acceptance runs in the hosted emulator."""
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]

def source(name):
    path = ROOT / name
    assert path.is_file(), f'R3B_MISSING_SOURCE: {name}'
    return path.read_text()

installer = source('app/src/main/java/com/aurora/store/data/installer/base/InstallerBase.kt')
verifier = source('app/src/main/java/com/aurora/store/data/installer/verification/ApkSetVerifier.kt')
manifest = source('app/src/main/java/com/aurora/store/data/installer/verification/BinaryApkManifest.kt')
policy = source('app/src/main/java/com/aurora/store/data/installer/verification/ApkSetPolicy.kt')
worker = source('app/src/main/java/com/aurora/store/data/work/DownloadWorker.kt')
model = source('app/src/main/java/com/aurora/store/data/room/download/Download.kt')
ci = source('.github/workflows/aurora-r2d-install-emulator.yml')
emulator = source('scripts/ci/r2d_emulator_ci.sh')
fixtures = source('scripts/ci/r3b_build_fixtures.sh')
android_test = source(
    'app/src/androidTest/java/com/aurora/store/data/installer/verification/ApkSetVerifierDeviceTest.kt'
)
jvm = source('app/src/test/java/com/aurora/store/data/installer/verification/ApkSetPolicyTest.kt')

checks = {
    'all backends use a staged allowlist instead of enumerating directories':
        'ApkSetVerifier.prepare(context, download)' in installer and
        'return snapshot.filesFor(sharedLibPackageName)' in installer and
        'downloadDir.listFiles' not in installer,
    'worker rejects mismatched APKs before completed state':
        worker.index('ApkSetVerifier.verify(context, download)') <
        worker.index('notifyStatus(DownloadStatus.COMPLETED)'),
    'metadata binds exact package and version to real APK manifest':
        'BinaryApkManifest.read(path)' in verifier and
        'ApkSetPolicy.check(packageName' in verifier and
        'entry.versionCode != expectedVersion' in policy and
        'entry.packageName != expectedPackage' in policy,
    'APK signatures verified by OS before backend handoff':
        'PackageManager.getVerifiedSigningInfo(' in verifier and
        'SigningInfo.VERSION_SIGNING_BLOCK_V2' in verifier and
        'SigningInfo.VERSION_JAR' not in verifier and
        'signingDigests(info)' in verifier,
    'split, stale cache and transient files fail closed':
        'it.name !in declared' in verifier and
        'File(entry.original.absolutePath + ".tmp").exists()' in verifier and
        'entry.metadata.type == AppFile.Type.BASE' in verifier and
        'entry.signerDigests != baseSigners' in policy,
    'snapshot is private unique and verified again after copying':
        'UUID.randomUUID()' in verifier and
        'verifyEntries(context, entries, { false }) { copied.getValue(it) }' in verifier and
        'file.setReadOnly()' in verifier,
    'cancelled attempts cannot start installation':
        'download.status !in DownloadStatus.installable + DownloadStatus.INSTALLING' in verifier and
        'if (interrupted())' in verifier,
    'all installer implementations gate the same snapshot':
        all('super.install(download)' in source(
            f'app/src/main/java/com/aurora/store/data/installer/{name}Installer.kt'
        ) for name in ('Native','AM','Root','Service','Session','Shizuku','MicroG')),
    'unsupported single-APK and external backends reject incomplete dependency sets':
        'files.size != 1' in source(
            'app/src/main/java/com/aurora/store/data/installer/NativeInstaller.kt'
        ) and all('requireNoPendingLibraries()' in source(
            f'app/src/main/java/com/aurora/store/data/installer/{name}Installer.kt'
        ) for name in ('Native','Service','MicroG')),
    'Android binary manifest parser handles 16-byte AAPT2 node headers':
        'header != 16 || size < 36' in manifest and
        'validCompiledManifestWithStandardHeaderIsParsed' in android_test,
    'Android binary manifest parser rejects malformed files':
        'APK manifest has invalid chunk bounds' in manifest and
        'APK manifest exceeds safe size limit' in manifest and
        'APK manifest attributes exceed chunk' in manifest,
    'JVM and instrumented Android tests and signed fixture building are wired':
        '@Test' in jvm and android_test.count('@Test') >= 16 and
        'scripts/ci/r3b_build_fixtures.sh' in ci and
        'python3 -B scripts/ci/check_r3b.py' in ci and
        'validSignedSplitsRequireMatchingManifestAndSigner' in emulator and
        'installedPackageWithDifferentSignerIsRejected' in emulator and
        'alteredSigningBlockIsRejectedEvenWithUpdatedDownloadHash' in emulator and
        'tampered-v2-v3.apk' in android_test and
        'R3B_SIGNING_BLOCK_MUTATION_NEGATIVE_PASS' in fixtures and
        '0x7109871a' in fixtures and
        '0xf05368c0' in fixtures and
        'need v2 and v3 signers' in fixtures and
        'apksigner" verify' in fixtures,
}
for description, ok in checks.items():
    assert ok, f'R3B_CONTRACT_FAIL: {description}'
    print('R3B_CONTRACT_PASS:', description)
print(f'R3B_SOURCE_CONTRACT_PASS checks={len(checks)}')
