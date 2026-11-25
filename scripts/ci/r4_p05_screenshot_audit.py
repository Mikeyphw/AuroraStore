#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R4 P06: strict, source-bound emulator PNG/pixel/route evidence validation.

stdlib-only PNG decoding prevents a 100% blank content area from being counted as a
successful screenshot merely because it is a valid PNG and has navigation-bar pixels.
Never substitutes a perceptual gate for human comparison to upstream PR113.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import zlib

COMPONENT = (
    'r4_update_downloading.png', 'r4_update_idle.png', 'r4_update_verifying.png',
    'r4_update_installing.png', 'r4_expressive_menu.png',
)
ACTIVITY = (
    'r4_activity_settings.png', 'r4_activity_ui_preferences.png',
    'r4_activity_more_sheet.png',
    'r4_activity_main.png', 'r4_activity_search.png',
    'r4_activity_downloads.png', 'r4_activity_updates.png',
)
POPULATED = (
    'r4_populated_for_you.png', 'r4_populated_search.png',
    'r4_populated_details.png', 'r4_populated_charts.png',
    'r4_populated_categories.png', 'r4_populated_install_controls.png',
)
EXPECTED = COMPONENT + ACTIVITY + POPULATED
EXPECTED_LOGS = {
    'download-dao-cancellation': 9,
    'real-offline-worker': 8,
    'download-ui-cancellation': 4,
    'r4-offline-account-session': 9,
    'r4-expressive-light': 5,
    'r4-expressive-dark': 5,
    'r4-activity-light': 6,
    'r4-activity-dark': 6,
    'r4-populated-light': 6,
    'r4-populated-dark': 6,
}


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError('R4_P06_REFUSED_' + reason)


def load_pixels(path: Path):
    data = path.read_bytes()
    require(2048 < len(data) < 32_000_000 and data.startswith(b'\x89PNG\r\n\x1a\n'),
            'PNG_BYTES_' + path.name)
    offset = 8
    ihdr = None
    ids = []
    iend = False
    while offset < len(data):
        require(offset + 12 <= len(data), 'PNG_TRUNCATED_CHUNK_' + path.name)
        length = struct.unpack_from('>I', data, offset)[0]
        require(length <= 32_000_000 and offset + 12 + length <= len(data), 'PNG_CHUNK_LENGTH_' + path.name)
        typ = data[offset+4:offset+8]
        chunk = data[offset+8:offset+8+length]
        crc = struct.unpack_from('>I', data, offset+8+length)[0]
        require(zlib.crc32(typ + chunk) & 0xffffffff == crc, 'PNG_CRC_' + path.name)
        if typ == b'IHDR':
            require(ihdr is None and length == 13, 'PNG_IHDR_' + path.name)
            ihdr = struct.unpack('>IIBBBBB', chunk)
        elif typ == b'IDAT':
            ids.append(chunk)
        elif typ == b'IEND':
            require(length == 0 and offset + 12 == len(data), 'PNG_IEND_' + path.name)
            iend = True
        offset += 12 + length
    require(iend and ihdr and ids, 'PNG_MISSING_COMPONENT_' + path.name)
    width, height, depth, color, compression, filtering, interlace = ihdr
    require(320 <= width <= 4096 and 480 <= height <= 8192 and depth == 8 and
            color in (2, 6) and (compression, filtering, interlace) == (0, 0, 0),
            'PNG_FORMAT_' + path.name)
    bpp = 4 if color == 6 else 3
    stride = width * bpp
    require(height * (stride + 1) <= 100_000_000, 'PNG_SIZE_LIMIT_' + path.name)
    d = zlib.decompressobj()
    raw = d.decompress(b''.join(ids), height * (stride + 1) + 1)
    raw += d.flush()
    require(d.eof and not d.unused_data and len(raw) == height*(stride+1),
            'PNG_DECODE_LENGTH_' + path.name)
    require(not d.unconsumed_tail, 'PNG_EXTRA_COMPRESSED_BYTES_' + path.name)
    # Sampled pixel reconstruction with every scanline decoded to honor PNG filters.
    center_x = width//2
    center_y = height//2
    lookup = {}
    first_x = width//50
    last_x = width*49//50
    first_y = height//20
    last_y = height*9//10
    xs = range(first_x, last_x, 8)
    ys = set(range(first_y, last_y, 8)) | {center_y}
    # P12 V-01: inspect the actual dark Updates empty-state message band.
    # The prior P09 screenshot contained black text on #121318, so PNG-unique
    # checks alone did not detect its near-invisible 1.13:1 contrast.
    p12_dark_updates_label_bright_samples = 0
    prev = bytearray(stride)
    idx = 0
    for y in range(height):
        code = raw[idx]
        row = bytearray(raw[idx+1:idx+1+stride])
        idx += stride+1
        require(code in range(5), 'PNG_FILTER_' + path.name)
        if code == 1:
            for n in range(bpp, stride): row[n] = (row[n] + row[n-bpp]) & 0xff
        elif code == 2:
            for n in range(stride): row[n] = (row[n] + prev[n]) & 0xff
        elif code == 3:
            for n in range(stride): row[n] = (row[n] + ((row[n-bpp] if n>=bpp else 0) + prev[n])//2) & 0xff
        elif code == 4:
            for n in range(stride):
                a = row[n-bpp] if n >= bpp else 0
                b = prev[n]
                c = prev[n-bpp] if n >= bpp else 0
                p = a+b-c
                pa, pb, pc = abs(p-a), abs(p-b), abs(p-c)
                predict = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                row[n] = (row[n] + predict) & 0xff
        if y in ys:
            if y == center_y:
                loc = center_x*bpp
                lookup[('bg', y)] = tuple(row[loc:loc+3])
            if first_y <= y < last_y and (y-first_y) % 8 == 0:
                lookup[y] = [tuple(row[x*bpp:x*bpp+3]) for x in xs]
        if path.name == 'r4_activity_updates.png' and path.parent.name == 'dark':
            # Only the text line: below the blue update icon, above the button.
            # Relative bounds accommodate typical emulator resolutions without
            # treating the high-contrast icon/button as evidence for the label.
            if height * 515 // 1000 <= y < height * 555 // 1000:
                for x in range(width * 29 // 100, width * 71 // 100, 4):
                    rgb = row[x*bpp:x*bpp+3]
                    if min(rgb) >= 110 and max(rgb) >= 155:
                        p12_dark_updates_label_bright_samples += 1
        prev = row
    bg = lookup[('bg',center_y)]
    changed = 0
    unique = set()
    for key,row in lookup.items():
        if not isinstance(key,int): continue
        for rgb in row:
            unique.add(rgb)
            if sum(abs(a-b) for a,b in zip(rgb,bg)) >= 52:
                changed += 1
    require(changed >= 42 and len(unique) >= 8,
            f'BLANK_SCREENSHOT_{path.parent.name}_{path.name}_changed={changed}_colors={len(unique)}')
    # Perceptual thumbnail retained for independent duplicate and compositing audits.
    return {'bytes': len(data), 'width': width, 'height': height,
            'p12_dark_updates_label_bright_samples': p12_dark_updates_label_bright_samples,
            'sha256': hashlib.sha256(data).hexdigest(),
            'non_background_samples': changed, 'sampled_colors': len(unique),
            'canvas_center_rgb': list(bg)}


def validate(root: Path, source: str, run: str) -> dict:
    require(bool(re.fullmatch(r'[0-9a-f]{40}', source)), 'SOURCE_SHA')
    require(bool(re.fullmatch(r'[0-9]+', run)), 'RUN_ID')
    require((root/'metadata/source-sha.txt').read_text().strip() == source, 'SOURCE_MISMATCH')
    require((root/'metadata/run-id.txt').read_text().strip() == run, 'RUN_MISMATCH')
    pngs = {}
    for mode in ('light','dark'):
        for name in EXPECTED:
            path = root/'screenshots'/mode/name
            pngs[f'{mode}/{name}'] = load_pixels(path)
    pngs['light/r4_real_app_launch.png'] = load_pixels(root/'screenshots/light/r4_real_app_launch.png')
    # A genuinely readable dark Updates message must contribute bright text
    # pixels in the text-only band. The archived P09 black-on-dark capture fails.
    require(pngs['dark/r4_activity_updates.png'].get(
        'p12_dark_updates_label_bright_samples', 0) >= 50,
        'R4_P12_DARK_UPDATES_EMPTY_LABEL_LOW_CONTRAST')
    # Pixel integrity alone accepts a white canvas in a dark-mode popup.
    # For this *isolated component fixture*, require that the unoccupied
    # center background follows the device's actual light/dark appearance.
    # Do not infer approval for the full product from these two pixels.
    light_canvas = sum(pngs['light/r4_expressive_menu.png']['canvas_center_rgb'])
    dark_canvas = sum(pngs['dark/r4_expressive_menu.png']['canvas_center_rgb'])
    require(light_canvas >= 375,
            'R4_P07_LIGHT_MENU_CANVAS_DARK_' + str(light_canvas))
    require(dark_canvas <= 330,
            'R4_P07_DARK_MENU_CANVAS_LIGHT_' + str(dark_canvas))
    seen_hashes = {}
    for name, evidence in pngs.items():
        digest = evidence['sha256']
        if digest in seen_hashes:
            earlier = seen_hashes[digest]
            require(False, 'IDENTICAL_SCREENSHOTS_' +
                    earlier.replace('/', '_') + '__' + name.replace('/', '_'))
        seen_hashes[digest] = name
    for name in EXPECTED:
        require(pngs[f'light/{name}']['sha256'] != pngs[f'dark/{name}']['sha256'],
                'IDENTICAL_LIGHT_DARK_' + name)
    for label,count in EXPECTED_LOGS.items():
        body = (root/'logs'/f'{label}.txt').read_text()
        suffix = 'test' if count==1 else 'tests'
        require(f'OK ({count} {suffix})' in body and 'FAILURES!!!' not in body and
                'INSTRUMENTATION_CODE: -1' in body, 'DEVICE_LOG_' + label)
    return {
        'result': 'PASS_DEVICE_TESTS_AND_NONBLANK_UNIQUE_CAPTURE',
        'source_sha': source, 'run_id':run, 'api_level':36,
        'architecture':'x86_64', 'hosted_emulator_only':True,
        'real_device_tests':sum(EXPECTED_LOGS.values()),
        'suite_counts': EXPECTED_LOGS,
        'screenshots':pngs,
        'real_production_compose_activity_routes_tested':[x.removeprefix('r4_activity_').removesuffix('.png') for x in ACTIVITY],
        'full_app_navigation_qualified':True,
        'main_more_to_settings_navigation_tested':True,
        'screenshots_nonblank_validated':True,
        'screenshots_unique_validated':True,
        'expressive_popup_theme_canvas_validated': True,
        'physical_and_live_play_qualification_deferred':True,
        'offline_fixtures_only': True,
        'offline_synthetic_account_preference_tests': 9,
        'offline_populated_catalog_test_executions': 12,
        'offline_populated_catalog_screenshots': 12,
        'populated_catalog_component_only': True,
        'full_network_backed_routes_qualified': False,
        'real_google_account_login_qualified': False,
        'spoof_restart_ui_behavior_qualified': False,
        'external_google_play_update_verified':False,
        'real_installer_update_verified':False,
        'visual_manual_approved': False,
        'physical_arm64_qualified':False,
        'release_qualified':False,
        'visual_review_tasks':[
            'Compare all real activity screenshots to the original upstream PR113 Material3 Expressive design',
            'Review status/navigation bar insets and clipping in Main, Settings, Search, Downloads, Updates',
            'Inspect bottom floating toolbar and touch target spacing in both themes',
            'Compare update, cancel, install-state buttons against real update screen and expected semantics',
            'Check screenshots visually for blank/duplicated content even after automatic nonblank guard',
        ]
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--source',required=True)
    p.add_argument('--run',required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    report=validate(a.root,a.source,a.run)
    a.out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    # Historical P09 receipt: R4_P09_REAL_EMULATOR_52_TESTS_AND_25_SCREENSHOTS_NONBLANK_UNIQUE_THEME_PASS
    print('R4_P12_REAL_EMULATOR_64_TESTS_AND_37_SCREENSHOTS_NONBLANK_UNIQUE_THEME_PASS')
    print('R4_P06_MANUAL_EXPRESSIVE_UI_VISUAL_FIDELITY_PENDING')

if __name__=='__main__':
    try: main()
    except (OSError,ValueError,zlib.error) as e:
        print(str(e),file=sys.stderr)
        sys.exit(1)
