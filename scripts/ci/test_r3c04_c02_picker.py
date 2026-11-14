#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""C04-02 actual SAF/UI/cleanup inventory contract. Does not claim emulator execution."""
from pathlib import Path
root=Path(__file__).resolve().parents[2]
art=root/'app/src/main/java/com/aurora/store/data/artifact'
unit=root/'app/src/test/java/com/aurora/store/data/artifact'
device=root/'app/src/androidTest/java/com/aurora/store/data/artifact'
source=lambda p: p.read_text(encoding='utf-8')
activity=source(art/'ArtifactImportActivity.kt')
stage=source(art/'ArtifactPrivateStager.kt')
policy=source(art/'ArtifactPickerPolicy.kt')
lease=source(art/'ArtifactCopyCancellation.kt')
runner=source(root/'scripts/ci/r3c03_c02_emulator_ci.sh')
for token in ('ActivityResultContracts.OpenDocument()', 'picker.launch(arrayOf("*/*"))',
              'invalidateCurrentImport(', 'preserveBrowserClaim = true', 'cancellation.cancel()', 'active?.discard()',
              'ArtifactPickerPolicy.acceptsPickerScheme(uri.scheme)', 'worker.execute {',
              'val name = selectedFilename(uri)', 'ArtifactPrivateStager.stage(this, uri, name, ticket)',
              'serial != requestSerial', 'closeWorker.execute'):
    assert token in activity, 'C04_02_HF07_REFUSED: missing activity boundary '+token
assert activity.index('val name = selectedFilename(uri)') > activity.index('worker.execute {'),     'C04_02_HF07_REFUSED: provider metadata query moved back to UI thread'
assert activity.index('invalidateCurrentImport("Choose a file') < activity.index('picker.launch('),     'C04_02_HF07_REFUSED: picker does not revoke old verified receipt before launch'
for token in ('MAX_SOURCE_BYTES','MAX_APK_BYTES','MAX_TOTAL_APK_BYTES',
              'directory.deleteRecursively()', 'sourceCancellation?.attach(stream)',
              'sourceCancellation?.detach(stream)', 'checkActive(cancelled)',
              'output.fd.sync()', 'if (n == 0)', 'File(directory, "selected-source.bin")'):
    assert token in stage, 'C04_02_HF07_REFUSED: missing staging boundary '+token
for token in ('AtomicBoolean', 'AtomicReference', 'fun cancel()', 'fun attach(', 'fun detach('):
    assert token in lease, 'C04_02_HF07_REFUSED: missing cancellation '+token
assert 'acceptsPickerScheme' in policy and 'safeDocumentName' in policy
assert source(unit/'ArtifactCopyCancellationTest.kt').count('@Test')==4
assert source(unit/'ArtifactPickerPolicyTest.kt').count('@Test')==7
assert source(device/'ArtifactPrivateStagerDeviceTest.kt').count('@Test')==17
assert '^OK \\(17 tests\\)' in runner, 'C04_02_HF07_REFUSED: stale 13-test runner'
assert 'PlayVerifiedEvidenceStore' not in (activity + stage + lease)
assert activity.count('if (!preserveBrowserClaim) lastBrowserLaunch = null') == 1, \
    'C04_02_HF07_REFUSED: browser handoff claim lost upon opening document picker'
print('R3C04_C02_HF07_SOURCE_PASS: SAF, UI-safe metadata, cancellation lease, private cleanup, 17-case API36 lane')
