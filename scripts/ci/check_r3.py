#!/usr/bin/env python3
"""R3A fail-closed source acceptance: historical selections are not Play APK archives."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
def source(p):
    return (ROOT / p).read_text(encoding="utf-8")

def require(path, markers):
    s = source(path)
    for marker in markers:
        if marker not in s:
            raise SystemExit(f"R3A_REFUSED: {path} missing {marker}")
    print("R3A_SOURCE_PASS", path)
    return s

policy = require("app/src/main/java/com/aurora/store/data/model/HistoricalVersionPolicy.kt", (
    'value.toLongOrNull()', 'it > 0L', 'distinct().sortedDescending()',
    'installedVersion > requestedVersion', 'canonicalVersionCode',
    'mayConfirmDowngrade', 'currentInstalledVersion',
))
unit = require("app/src/test/java/com/aurora/store/data/model/HistoricalVersionPolicyTest.kt", (
    'rejectsInvalidAndOverflowedVersionCodes', 'versionHistoryIsNumericDeduplicatedAndSorted',
    'onlyAnOlderVersionOfAnInstalledAppIsADowngrade',
    'historySelectionUsesCanonicalPositiveCodes',
    'downgradeConsentRejectsChangedSelectionOrInstalledVersion',
))
manual = require("app/src/main/java/com/aurora/store/compose/ui/details/ManualDownloadScreen.kt", (
    'HistoricalVersionPolicy.parseVersionCode(versionCode.text)',
    'HistoricalVersionPolicy.isDowngrade(code, installedNow)',
    'HistoricalVersionPolicy.mayConfirmDowngrade(',
    'metadataReady && !state.inProgress()',
    'remember(currentVersionCode)',
    'canonicalVersionCode(report.versionCode)',
    'pendingDowngrade', 'r3_downgrade_warning', 'r3_downgrade_try',
    'fileList = emptyList()', 'dependentLibraries = emptyList()',
    'PackageUtil.getInstalledVersionCode(context, packageName)',
))
if 'versionCode.text.toLong()' in manual or 'lib.copy(versionCode = versionCode)' in manual:
    raise SystemExit('R3A_REFUSED: unsafe unparsed code or fabricated library version')
picker = require("app/src/main/java/com/aurora/store/compose/ui/sheets/VersionPickerSheet.kt", (
    'HistoricalVersionPolicy.parseVersionCode(report.versionCode)',
    '.distinctBy { it.first }', '.sortedByDescending { it.first }',
    'r3_history_source_warning', 'r3_history_older',
))
require("app/src/main/java/com/aurora/store/data/installer/InstallRecoveryPolicy.kt", (
    'installedVersion == targetVersion',
))
require("app/src/main/java/com/aurora/store/data/installer/InstallerBackendPolicy.kt", (
    'installedVersion == expectedVersion',
))
require("app/src/main/java/com/aurora/store/data/helper/DownloadHelper.kt", (
    'if (installedVersion != current.versionCode) return@onEach',
))
vm = require("app/src/main/java/com/aurora/store/viewmodel/details/AppDetailsViewModel.kt", (
    'Version history lookup failed for $packageName',
    '_versionLookupInProgress.value = false',
    'lookupVersions()',
    '_exodusReport.value = reports.firstOrNull()',
    'catch (cancelled: CancellationException)',
))
if 'private fun fetchExodusPrivacyReport' in vm:
    raise SystemExit('R3A_REFUSED: unsafe duplicate Exodus fetch path')
if 'app!!' in manual:
    raise SystemExit('R3A_REFUSED: nullable app metadata force-unwrapped')
require("app/src/main/res/values/strings_r3.xml", (
    'name="r3_downgrade_warning"', 'Aurora will not uninstall',
    'name="r3_history_source_warning"',
))
require(".github/workflows/aurora-foundation.yml", (
    'python3 -B scripts/ci/check_r3.py', 'testVanillaDebugUnitTest',
))
require("docs/R3_HISTORICAL_VERSIONS_AND_DOWNGRADES.md", (
    'Exodus', 'Play', 'no automatic uninstall', 'API 36',
))
from xml.etree import ElementTree
ElementTree.parse(ROOT / 'app/src/main/res/values/strings_r3.xml')
subprocess.run(['git','diff','--check'], cwd=ROOT,check=True)
print('R3A_SOURCE_CONTRACT_PASS')
