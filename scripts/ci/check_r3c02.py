#!/usr/bin/env python3
"""R3C-02: honest version-picker display and conservative exact-version selection."""
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
def source(path):
    return (ROOT / path).read_text(encoding='utf-8')

manual = source('app/src/main/java/com/aurora/store/compose/ui/details/ManualDownloadScreen.kt')
picker = source('app/src/main/java/com/aurora/store/compose/ui/sheets/VersionPickerSheet.kt')
policy = source('app/src/main/java/com/aurora/store/data/model/HistoricalAvailabilityPolicy.kt')
foundation = source('.github/workflows/aurora-foundation.yml')
strings = ROOT / 'app/src/main/res/values/strings_r3c.xml'
resource = ET.parse(strings).getroot()
values = {entry.attrib['name']: (entry.text or '') for entry in resource.findall('string')}
assert resource.tag == 'resources'
assert set(values) == {'r3c_picker_unverified', 'r3c_selected_version_unverified'}
assert all('unverified' in value.lower() or 'not verified' in value.lower() for value in values.values())
assert 'HistoricalAvailabilityPolicy.assess(' in manual
assert 'HistoricalAvailabilityPolicy.assess(' in picker
assert 'currentListingVersion = currentVersionCode' in manual
assert 'currentListingVersion = currentListingVersionCode' in picker
assert 'installedVersion = installedNow' in manual
assert 'downgradeConsent = true' in manual
assert 'HistoricalVersionPolicy.mayConfirmDowngrade(' in manual
assert 'metadataReady && !state.inProgress() && mayRequestSelection' in manual
assert 'HistoricalAvailabilityPolicy.Decision.DOWNGRADE_CONSENT_REQUIRED' in manual
assert 'HistoricalAvailabilityPolicy.Decision.MAY_REQUEST_EXACT_DELIVERY' in manual
assert 'reports.any { report ->' in manual
assert 'historicalReportVersion = version' in picker
assert 'assessment.delivery == HistoricalAvailabilityPolicy.Delivery.UNKNOWN' in picker
assert 'assessment.compatibility == HistoricalAvailabilityPolicy.Compatibility.UNKNOWN' in picker
assert 'R.string.r3c_picker_unverified' in picker
assert 'R.string.r3c_selected_version_unverified' in manual
# No client-side claim based on stale Play listing or an Exodus entry.
for file in (manual, picker):
    assert 'verifiedApkVersion =' not in file
    assert 'unavailableVersion =' not in file
    assert 'manifestVersion =' not in file
    assert 'manifestMinSdk =' not in file
assert 'evidence.verifiedApkVersion == version' in policy
assert foundation.count('python3 -B scripts/ci/check_r3c02.py') == 1
assert len(re.findall(r'@Test\s+fun ', source('app/src/test/java/com/aurora/store/data/model/HistoricalAvailabilityPolicyTest.kt'))) >= 13
print('R3C02_SOURCE_CONTRACT_PASS: manual+picker evidence, honest unknown UI, 13 policy tests')
