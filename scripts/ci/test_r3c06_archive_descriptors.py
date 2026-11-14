#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R3C06 phase 2 source-contract audit; not a substitute for API36 instrumentation."""
from pathlib import Path
root=Path(__file__).resolve().parents[2]
art=root/'app/src/main/java/com/aurora/store/data/artifact'
test=root/'app/src/test/java/com/aurora/store/data/artifact'
device=root/'app/src/androidTest/java/com/aurora/store/data/artifact'
read=lambda p:p.read_text(encoding='utf-8')
def guard(cond,msg):
    if not cond:raise SystemExit('R3C06_P2_REFUSED: '+msg)
paths={n:art/n for n in ('ArtifactArchivePolicy.kt','ArtifactArchiveDescriptorPolicy.kt',
  'ArtifactArchiveDescriptorParser.kt','ArtifactPrivateStager.kt','ArtifactApkVerifier.kt')}
for name,path in paths.items():guard(path.is_file(),'missing '+name)
policy=read(paths['ArtifactArchiveDescriptorPolicy.kt'])
parser=read(paths['ArtifactArchiveDescriptorParser.kt'])
stage=read(paths['ArtifactPrivateStager.kt'])
verify=read(paths['ArtifactApkVerifier.kt'])
archive=read(paths['ArtifactArchivePolicy.kt'])
for part in ('allowsMetadata(', 'checkMemberLayout(', 'checkAgainstSignedApks(',
             'ids.keys != archiveEntryNames.toSet()', 'Incomplete APKM outer signature metadata',
             'Unsigned archive metadata contradicts signed APK identity',
             'XAPK split ID contradicts signed manifest'):
    guard(part in policy,'missing fail-closed descriptor constraint '+part)
for part in ('MAX_INDEX_BYTES', 'CodingErrorAction.REPORT', 'versionText.toLongOrNull()',
             'json.optJSONArray("split_apks")', 'json.optJSONArray("expansions")',
             'Duplicate XAPK split index path'):
    guard(part in parser,'missing bounded parser guard '+part)
for part in ('"META-INF/MANIFEST.MF"', '"META-INF/APKMIRRO.SF"',
             '"META-INF/APKMIRRO.RSA"', '"APKM_installer.url"'):
    guard(part in archive,'missing explicit APKMirror safe-metadata name '+part)
for part in ('verifyMetadata(stream, entry.size, entry.crc, cancelled, index)',
             'checkMemberLayout(format, metadataPaths)',
             'ArtifactArchiveDescriptorParser.parse(format, rawDescriptor)',
             'sourceCancellation?.attach(stream)', 'directory.deleteRecursively()',
             'archiveApkEntryNames.add(entry.name)', 'copied.file.delete()'):
    guard(part in stage,'missing bounded staging and cleanup '+part)
guard(verify.count('ArtifactArchiveDescriptorPolicy.checkAgainstSignedApks(')==2,
      'descriptor-veto must be checked both at verification and before installation')
for banned in ('PlayVerifiedEvidenceStore', 'matchesPlayDigest(', 'R3bVerifiedProof'):
    guard(banned not in (policy+parser+stage+archive),
          'non-Play archive code references '+banned)
unit=test/'ArtifactArchiveDescriptorPolicyTest.kt'
android=device/'ArtifactArchiveDescriptorDeviceTest.kt'
legacy=device/'ArtifactPrivateStagerDeviceTest.kt'
runner=root/'scripts/ci/r3c03_c02_emulator_ci.sh'
for file in (unit,android,legacy,runner):guard(file.is_file(),'missing '+str(file))
guard(read(unit).count('@Test')>=12,'insufficient real JVM contract tests')
guard(read(android).count('@Test')==6,'API36 archive descriptor six-case suite missing')
guard(read(legacy).count('@Test')==17,'stale count for existing staging device suite')
guard('"metadata/manifest.json"' in read(legacy),
      'CRC regression test no longer exercises format-permitted metadata')
guard('relabel-' in read(legacy), 'stale toc.pb relabel acceptance regression')
guard('ArtifactArchiveDescriptorDeviceTest' in read(runner) and
      r'^OK \(6 tests\)' in read(runner), 'new API36 six-case gate missing')
guard(r'^OK \(17 tests\)' in read(runner),'old API36 staging gate weakened')
guard('ArtifactSplitCompatibilityDeviceTest' in read(runner),'R3C06 phase 1 gate removed')
print('R3C06_P2_ARCHIVE_DESCRIPTOR_SOURCE_PASS: bounded metadata-only veto, no publisher trust, staging and API36 negatives')
