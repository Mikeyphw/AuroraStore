#!/usr/bin/env python3
"""Negative mutation cases for the R3A/R3C manual downgrade consent guard."""
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import re
from r3a_downgrade_guard import assert_downgrade_guard

ROOT = Path(__file__).resolve().parents[2]
SCREEN = ROOT / 'app/src/main/java/com/aurora/store/compose/ui/details/ManualDownloadScreen.kt'
original = SCREEN.read_text(encoding='utf-8')


def once(old: str, new: str, data: str = original) -> str:
    # Kotlin layout is intentionally ignored when locating a mutation site.
    tokens = re.findall(r'[A-Za-z_][A-Za-z0-9_]*|->|&&|\|\||\?\.|==|[^\s]', old)
    pattern = r'\s*'.join(re.escape(token) for token in tokens)
    matches = list(re.finditer(pattern, data))
    if len(matches) != 1:
        raise AssertionError(f'fixture marker count is not one: {old!r}, count={len(matches)}')
    return data[:matches[0].start()] + new + data[matches[0].end():]


def in_button(old: str, new: str) -> str:
    cut = re.search(r'selectedVersion\s*\?\.\s*let\s*\{\s*code\s*->', original)
    assert cut, 'missing install callback'
    return original[:cut.end()] + once(old, new, original[cut.end():])


def rejected(name: str, mutated: str) -> None:
    try:
        assert_downgrade_guard(mutated)
    except ValueError as error:
        assert str(error).startswith('R3A_DOWNGRADE_REFUSED:'), str(error)
        print('R3A_MUTATION_REJECTED:', name)
        return
    raise AssertionError('unsafe downgrade mutation accepted: ' + name)


# The checked-in real implementation and either Kotlin call formatting must pass.
assert_downgrade_guard(original)
multiline = 'HistoricalVersionPolicy.isDowngrade(code, installedNow)'
assert_downgrade_guard(once(multiline, 'HistoricalVersionPolicy.isDowngrade(code, installedNow)'))
assert_downgrade_guard(once(multiline, 'HistoricalVersionPolicy.isDowngrade(\n    code,\n    installedNow\n)'))

rejected('wrong requested version', once(multiline, 'HistoricalVersionPolicy.isDowngrade(0L, installedNow)'))
rejected('wrong installed version', once(multiline, 'HistoricalVersionPolicy.isDowngrade(code, 0L)'))
rejected('consent always true', once(
    'val needsConsent = live.decision == Decision.DOWNGRADE_CONSENT_REQUIRED',
    'val needsConsent = true'))
rejected('consent inverted', once('if (isDowngradeNow && needsConsent)',
                                  'if (isDowngradeNow && !needsConsent)'))
rejected('consent omitted', once('if (isDowngradeNow && needsConsent)',
                                 'if (isDowngradeNow)'))
rejected('consent optional', once('if (isDowngradeNow && needsConsent)',
                                  'if (isDowngradeNow || needsConsent)'))
rejected('unconditional direct install', once('} else if (live.mayAttemptExactDelivery) {',
                                               '} else {'))
rejected('unconditional direct policy', once('} else if (live.mayAttemptExactDelivery) {',
                                             '} else if (true) {'))
rejected('stale installed version on click', in_button('installedVersion = installedNow,',
                                                      'installedVersion = installedVersionCode,'))
rejected('wrong requested version in live assessment', once('requestedVersion = code,',
                                                            'requestedVersion = currentVersionCode,'))
rejected('wrong consent dialog snapshot', once('pendingDowngrade = code to installedNow',
                                               'pendingDowngrade = code to 0L'))
rejected('confirmation without recheck', once('HistoricalVersionPolicy.mayConfirmDowngrade(',
                                             'HistoricalVersionPolicy.isDowngrade('))
rejected('confirmation without policy', once(') && assessment.mayAttemptExactDelivery',
                                              ') || assessment.mayAttemptExactDelivery'))
rejected('confirmation wrong request', once('onRequestInstall(requested)',
                                             'onRequestInstall(requested + 1L)'))
rejected('pregranted consent', in_button('deviceSdk = Build.VERSION.SDK_INT',
                                           'deviceSdk = Build.VERSION.SDK_INT, downgradeConsent = true'))
rejected('explicit consent removed', once('downgradeConsent = true', 'downgradeConsent = false'))
rejected('comment masquerading as a consent guard', once(
    'val needsConsent = live.decision == Decision.DOWNGRADE_CONSENT_REQUIRED',
    '// val needsConsent = live.decision == Decision.DOWNGRADE_CONSENT_REQUIRED'))
rejected('duplicate unguarded callback', once('onRequestInstall(code)',
                                               'onRequestInstall(code); onRequestInstall(code)'))
print('R3A_DOWNGRADE_NEGATIVE_TESTS_PASS: positive source + formatting + 18 negative mutations')
