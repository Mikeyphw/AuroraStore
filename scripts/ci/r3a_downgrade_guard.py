#!/usr/bin/env python3
"""Fail-closed R3A/R3C downgrade UI source guard.

This deliberately matches *control flow*, not Kotlin line formatting. It is a
source-level regression gate, not a substitute for compiled or device tests.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import re

_KOTLIN_TOKENS = re.compile(
    r'"""[\s\S]*?"""|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*[\s\S]*?\*/|//[^\n]*'
)


def _compact_code(source: str) -> str:
    # Ignore comments as proof; preserve literal text and operators.
    without_comments = _KOTLIN_TOKENS.sub(
        lambda m: ' ' if m.group().startswith(('//', '/*')) else m.group(), source
    )
    return re.sub(r'\s+', '', without_comments)


def assert_downgrade_guard(source: str) -> None:
    """Reject absent, stale or bypassed consent/attempt guards in ManualDownloadScreen."""
    code = _compact_code(source)

    def refuse(reason: str) -> None:
        raise ValueError('R3A_DOWNGRADE_REFUSED: ' + reason)

    def require(needle: str, reason: str, where: str = '') -> None:
        if _compact_code(needle) not in (where or code):
            refuse(reason)

    # Limit the guards to the actual confirmation dialog and install button.
    dialog_start = code.find('pendingDowngrade?.let{(requested,installedAtConfirmation)->')
    dialog_end = code.find('if(showVersionPicker)', dialog_start)
    button_start = code.find('selectedVersion?.let{code->', dialog_end)
    if min(dialog_start, dialog_end, button_start) < 0 or not (
        dialog_start < dialog_end < button_start
    ):
        refuse('downgrade confirmation dialog and live install button must both exist')
    dialog = code[dialog_start:dialog_end]
    button = code[button_start:]

    require('enabled = metadataReady && !state.inProgress() && mayRequestSelection',
            'the install button must require a valid selection and idle metadata')
    require(
        'val mayRequestSelection = when (selectionAssessment?.decision) { '
        'HistoricalAvailabilityPolicy.Decision.MAY_REQUEST_EXACT_DELIVERY, '
        'HistoricalAvailabilityPolicy.Decision.DOWNGRADE_CONSENT_REQUIRED -> true '
        'else -> false }',
        'the request button must fail closed except for delivery or consent decisions'
    )

    require('val installedNow = installedVersionProvider()',
            're-read installed version at the install click', button)
    require('val live = HistoricalAvailabilityPolicy.assess(',
            're-assess live policy at the install click', button)
    require('requestedVersion = code, currentListingVersion = currentVersionCode, '
            'installedVersion = installedNow, deviceSdk = Build.VERSION.SDK_INT',
            'live request must bind exact selected and installed version', button)
    require('val isDowngradeNow = HistoricalVersionPolicy.isDowngrade(code, installedNow)',
            'fresh downgrade comparison must use exact requested and installed code', button)
    require('val needsConsent = live.decision == Decision.DOWNGRADE_CONSENT_REQUIRED',
            'downgrade consent must use the policy decision', button)
    require('if (isDowngradeNow && needsConsent) { '
            'pendingDowngrade = code to installedNow '
            '} else if (live.mayAttemptExactDelivery) { onRequestInstall(code)',
            'downgrade must open consent; non-consent request must be policy-gated', button)

    require('val installedNow = installedVersionProvider()',
            're-read installed version when consent is confirmed', dialog)
    require('requestedVersion = requested, currentListingVersion = currentVersionCode, '
            'installedVersion = installedNow, deviceSdk = Build.VERSION.SDK_INT, '
            'downgradeConsent = true',
            'confirmation must reassess exact request with explicit consent', dialog)
    require('if (HistoricalVersionPolicy.mayConfirmDowngrade('
            'requested, installedAtConfirmation, installedNow, versionCode.text'
            ') && assessment.mayAttemptExactDelivery) { onRequestInstall(requested)',
            'consent must revalidate selected code, installed code and live policy', dialog)

    # Do not accept copied markers, duplicate unguarded callbacks or accidental
    # use of a consent flag on the initial non-consensual request path.
    for call, expected in (
        ('HistoricalVersionPolicy.isDowngrade(', 1),
        ('HistoricalVersionPolicy.mayConfirmDowngrade(', 1),
        ('onRequestInstall(code)', 1),
        ('onRequestInstall(requested)', 1),
        ('downgradeConsent=true', 1),
        ('pendingDowngrade=code to installedNow', 1),
    ):
        if code.count(_compact_code(call)) != expected:
            refuse('unexpected count for ' + call)
    if 'downgradeConsent=true' in button:
        refuse('non-consensual click must never pregrant downgrade consent')
    if 'onRequestInstall(code)' in dialog or 'onRequestInstall(requested)' in button:
        refuse('incorrect callback placement')
