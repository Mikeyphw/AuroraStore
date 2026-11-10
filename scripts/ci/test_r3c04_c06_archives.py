#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""C04-06 source/security contract. Runtime ZIP negatives execute in API36 lane."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "app/src/main/java/com/aurora/store/data/artifact"
TESTS = ROOT / "app/src/test/java/com/aurora/store/data/artifact"
DEVICE = ROOT / "app/src/androidTest/java/com/aurora/store/data/artifact"
RUNNER = ROOT / "scripts/ci/r3c03_c02_emulator_ci.sh"

def source(path):
    assert path.is_file(), f"C04_06_HF04_REFUSED: missing {path}"
    return path.read_text(encoding="utf-8")

policy = source(ART / "ArtifactArchivePolicy.kt")
preflight = source(ART / "ArtifactZipPreflight.kt")
stage = source(ART / "ArtifactPrivateStager.kt")
unit = source(TESTS / "ArtifactZipPreflightTest.kt")
device = source(DEVICE / "ArtifactPrivateStagerDeviceTest.kt")
runner = source(RUNNER)
for token in ('end of central directory', 'count > ArtifactArchivePolicy.MAX_ITEMS',
              'symbolic link or special file', 'local/central entry name mismatch',
              'overlapping local entries', 'ZIP64 extra field', 'compressed entry',
              'total expanded data'):
    assert token in preflight, f"C04_06_HF04_REFUSED: preflight {token}"
assert stage.index('ArtifactZipPreflight.inspect(copied.file)') < stage.index('ZipFile(copied.file)')
for token in ('entry.crc != expected.crc', 'crc.update(buffer, 0, n)',
              'verifyMetadata(stream, entry.size, entry.crc, cancelled)',
              'copied.file.delete()', 'directory.deleteRecursively()',
              'Archive entry checksum mismatch', 'entryCount != inspected.size'):
    assert token in stage, f"C04_06_HF04_REFUSED: stage {token}"
assert '"pb" -> if (name == "toc.pb")' in policy
assert "if (copied.byteCount > ArtifactArchivePolicy.MAX_APK_BYTES)" in stage
assert unit.count('@Test') >= 8
assert device.count('@Test') == 17, f"C04_06_HF04_REFUSED: got {device.count('@Test')} Android tests"
assert "^OK \\(17 tests\\)" in runner, 'C04_06_HF04_REFUSED: emulator test count mismatch'
assert 'ArtifactPrivateStagerDeviceTest' in runner
assert 'PlayVerifiedEvidenceStore' not in (stage + preflight)
print('R3C04_C06_HF04_ARCHIVE_CONTRACT_PASS: pre-index central bounds, symlinks, CRC, metadata, API36 17-case staging lane including C04-02')
