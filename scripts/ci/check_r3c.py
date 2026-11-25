#!/usr/bin/env python3
"""R3C-01 conservative evidence policy; not live Play availability certification."""
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
policy = (ROOT / 'app/src/main/java/com/aurora/store/data/model/HistoricalAvailabilityPolicy.kt').read_text()
tests = (ROOT / 'app/src/test/java/com/aurora/store/data/model/HistoricalAvailabilityPolicyTest.kt').read_text()
doc = (ROOT / 'docs/R3C_HISTORICAL_AVAILABILITY_AND_COMPATIBILITY.md').read_text()
workflow = (ROOT / '.github/workflows/aurora-foundation.yml').read_text()
previous = (ROOT / 'scripts/ci/check_r3.py').read_text()
assert 'fun assess(evidence: Evidence)' in policy
assert 'evidence.unavailableVersion == version' in policy
assert 'evidence.verifiedApkVersion == version' in policy
assert 'evidence.manifestVersion == version' in policy
assert 'downgrade && !evidence.downgradeConsent' in policy
assert 'Delivery.UNKNOWN' in policy and 'SDK_BOUNDS_PASSED' in policy
assert 'mayAttemptExactDelivery' in policy and 'MAY_REQUEST_EXACT_DELIVERY' in policy
assert len(re.findall(r'@Test\s+fun ', tests)) >= 12
assert 'exodusHistoryDoesNotProvePlayDelivery' in tests
assert 'currentPlayMetadataCannotProveHistoricalCompatibility' in tests
assert 'consentPermitsAttemptButNeverGuaranteesDowngrade' in tests
assert 'python3 -B scripts/ci/check_r3c.py' in workflow
assert 'no automatic uninstall' in (ROOT / 'docs/R3_HISTORICAL_VERSIONS_AND_DOWNGRADES.md').read_text()
assert 'Exodus' in doc and 'does not' in doc and 'UNKNOWN' in doc
assert 'mayConfirmDowngrade' in previous
print('R3C01_SOURCE_CONTRACT_PASS tests=13')
