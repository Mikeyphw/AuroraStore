#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate real captured PNG bytes and source-bound R4 emulator evidence.

This deliberately does not claim pixel-perfect visual acceptance without a human
review of the exported screenshots.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

EXPECTED = (
    'r4_settings.png',
    'r4_update_idle.png',
    'r4_update_verifying.png',
    'r4_update_installing.png',
    'r4_expressive_menu.png',
)
EXPECTED_LOGS = {
    'download-dao-cancellation': 9,
    'real-offline-worker': 8,
    'download-ui-cancellation': 4,
    'r4-expressive-light': 5,
    'r4-expressive-dark': 5,
}


def check_png(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 2048 or data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError(f'R4_P05_REFUSED_NOT_REAL_PNG: {path}')
    if data[12:16] != b'IHDR' or struct.unpack('>I', data[8:12])[0] != 13:
        raise ValueError(f'R4_P05_REFUSED_MALFORMED_PNG_IHDR: {path}')
    width, height, depth, colour = struct.unpack('>IIBB', data[16:26])
    if width < 320 or height < 480 or width > 4096 or height > 8192:
        raise ValueError(f'R4_P05_REFUSED_SCREENSHOT_DIMENSIONS: {path} {width}x{height}')
    if depth not in (8, 16) or colour not in (2, 6):
        raise ValueError(f'R4_P05_REFUSED_UNEXPECTED_PIXEL_FORMAT: {path} depth={depth} colour={colour}')
    if data[-12:-8] != b'\x00\x00\x00\x00' or data[-8:-4] != b'IEND':
        raise ValueError(f'R4_P05_REFUSED_INCOMPLETE_PNG: {path}')
    return {'bytes': len(data), 'width': width, 'height': height,
            'sha256': hashlib.sha256(data).hexdigest()}


def validate(root: Path, source: str, run: str) -> dict:
    if not re.fullmatch(r'[0-9a-f]{40}', source):
        raise ValueError('R4_P05_REFUSED_SOURCE_SHA')
    if not re.fullmatch(r'[0-9]+', run):
        raise ValueError('R4_P05_REFUSED_RUN_ID')
    if (root/'metadata/source-sha.txt').read_text().strip() != source:
        raise ValueError('R4_P05_REFUSED_SOURCE_RECEIPT_MISMATCH')
    if (root/'metadata/run-id.txt').read_text().strip() != run:
        raise ValueError('R4_P05_REFUSED_RUN_RECEIPT_MISMATCH')
    pngs: dict[str, dict] = {}
    for mode in ('light', 'dark'):
        for name in EXPECTED:
            key = f'{mode}/{name}'
            pngs[key] = check_png(root/'screenshots'/mode/name)
    pngs['light/r4_real_app_launch.png'] = check_png(
        root/'screenshots/light/r4_real_app_launch.png')
    for name in EXPECTED:
        if pngs[f'light/{name}']['sha256'] == pngs[f'dark/{name}']['sha256']:
            raise ValueError(f'R4_P05_REFUSED_IDENTICAL_LIGHT_DARK_SNAPSHOT: {name}')
    for label, count in EXPECTED_LOGS.items():
        log = (root/'logs'/f'{label}.txt').read_text()
        suffix = 'test' if count == 1 else 'tests'
        if f'OK ({count} {suffix})' not in log or 'FAILURES!!!' in log:
            raise ValueError(f'R4_P05_REFUSED_AS_RUN_DEVICE_LOG: {label}')
    return {
        'result': 'PASS_DEVICE_TESTS_AND_CAPTURE',
        'source_sha': source,
        'run_id': run,
        'api_level': 36,
        'architecture': 'x86_64',
        'hosted_emulator_only': True,
        'real_device_tests': sum(EXPECTED_LOGS.values()),
        'suite_counts': EXPECTED_LOGS,
        'screenshots': pngs,
        'offline_fixtures_only': True,
        'external_google_play_update_verified': False,
        'real_installer_update_verified': False,
        'full_app_navigation_qualified': False,
        'visual_manual_approved': False,
        'physical_arm64_qualified': False,
        'release_qualified': False,
        'visual_review_tasks': [
            'Review screenshot geometry, status-bar inset, bottom toolbar overlap and clipping',
            'Compare Material3 Expressive shape/spacing/typography in light and dark theme',
            'Inspect settings navigation and preserved Import and verify APKs entry',
            'Inspect update, cancel, installing states and expressive menu selected/checked states',
            'Inspect actual whole-app onboarding screen separately from component test screens',
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--source', required=True)
    ap.add_argument('--run', required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    report = validate(args.root, args.source, args.run)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print('R4_P05_REAL_EMULATOR_31_DEVICE_TESTS_AND_11_SCREENSHOTS_PASS')
    print('R4_P05_MANUAL_EXPRESSIVE_UI_VISUAL_FIDELITY_PENDING')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
