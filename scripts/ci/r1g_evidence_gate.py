#!/usr/bin/env python3
"""Fail-closed, source-bound emulator receipt (NOT a physical/release certification)."""
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import zlib


def refuse(message):
    raise SystemExit('R1G_EVIDENCE_REFUSED: ' + message)


def read_receipt(root, folder, name, sha, run):
    p = root / folder / name
    if not p.is_file():
        refuse(f'missing {p}')
    result = json.loads(p.read_text(encoding='utf-8'))
    if (result.get('overall') != 'PASS' or result.get('source_sha') != sha or
            result.get('run_id') != run):
        refuse(f'unverified source, run or outcome in {name}')
    if result.get('physical_device_qualified') is not False:
        refuse(f'unexpected physical qualification in {name}')
    if result.get('release_qualified') is not False:
        refuse(f'unexpected release qualification in {name}')
    return result


def validate_png(path):
    data = path.read_bytes()
    if len(data) < 100 or data[:8] != b'\x89PNG\r\n\x1a\n':
        refuse(f'invalid or empty screenshot {path}')
    off, got_header, got_end, width, height = 8, False, False, 0, 0
    while off < len(data):
        if len(data) - off < 12:
            refuse(f'truncated screenshot {path}')
        length = struct.unpack_from('>I', data, off)[0]
        if length > len(data) - off - 12:
            refuse(f'impossible PNG chunk length {path}')
        kind = data[off + 4:off + 8]
        payload = data[off + 8:off + 8 + length]
        actual = struct.unpack_from('>I', data, off + 8 + length)[0]
        if zlib.crc32(kind + payload) & 0xffffffff != actual:
            refuse(f'CRC mismatch {path}')
        if not got_header:
            if kind != b'IHDR' or length != 13:
                refuse(f'first PNG chunk must be IHDR {path}')
            width, height = struct.unpack_from('>II', payload)
            if not 100 <= width <= 8000 or not 100 <= height <= 8000:
                refuse(f'invalid screenshot dimensions {path}')
            got_header = True
        if kind == b'IEND':
            if length != 0 or off + 12 != len(data):
                refuse(f'invalid PNG trailer {path}')
            got_end = True
        off += 12 + length
    if not got_header or not got_end:
        refuse(f'PNG missing required chunks {path}')
    return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
            'width': width, 'height': height}


def main(root):
    sha = os.environ.get('GITHUB_SHA', '')
    run = os.environ.get('GITHUB_RUN_ID', '')
    if not re.fullmatch(r'[0-9a-f]{40}', sha) or not re.fullmatch(r'[0-9]+', run):
        refuse('missing GitHub source identity or run ID')
    specs = [
        ('aurora-r1d-emulator', 'R1D_EMULATOR_RECEIPT.json', 14),
        ('aurora-r1d2-emulator', 'R1D2_EMULATOR_RECEIPT.json', 24),
        ('aurora-r1e-emulator', 'R1E_EMULATOR_RECEIPT.json', 32),
        ('aurora-r1f-emulator', 'R1F_EMULATOR_RECEIPT.json', 36),
    ]
    files = {}
    for folder, receipt_name, total in specs:
        result = read_receipt(root, folder, receipt_name, sha, run)
        if result.get('total_device_tests', result.get('android_device_tests')) != total:
            refuse(f'wrong accumulated test count in {receipt_name}')
        files[receipt_name] = hashlib.sha256((root / folder / receipt_name).read_bytes()).hexdigest()
    r1f = read_receipt(root, 'aurora-r1f-emulator', 'R1F_EMULATOR_RECEIPT.json', sha, run)
    if r1f.get('real_emulator_screenshots') != 3:
        refuse('R1F screenshot evidence not qualified')
    if not (root / 'aurora-r1g-emulator' / 'r1g-ui.txt').is_file():
        refuse('missing R1G device test log')
    log = (root / 'aurora-r1g-emulator' / 'r1g-ui.txt').read_text(encoding='utf-8')
    if 'FAILURES!!!' in log or not re.search(r'^OK \(4 tests\)', log, re.MULTILINE):
        refuse('four Compose tests not proven')
    shots = {}
    for folder, names in [
        ('aurora-r1f-emulator', ['r1f_queued.png', 'r1f_downloading.png', 'r1f_failed.png']),
        ('aurora-r1g-emulator', ['r1g_awaiting_retry.png', 'r1g_cancelled.png']),
    ]:
        for name in names:
            shots[name] = validate_png(root / folder / name)
    receipt = {
        'overall': 'PASS',
        'source_sha': sha, 'run_id': run,
        'emulator_api': 36,
        'device_tests': 40,
        'previous_device_tests': 36,
        'new_compose_device_tests': 4,
        'compose_screenshots': shots,
        'prior_receipt_sha256': files,
        'build_scope': 'vanillaDebug API36 synthetic/offline',
        'actual_google_play_delivery_qualified': False,
        'actual_package_installation_qualified': False,
        'physical_device_qualified': False,
        'release_signed': False,
        'release_qualified': False,
    }
    dest = root / 'aurora-r1g-emulator' / 'R1G_QUALIFICATION_RECEIPT.json'
    dest.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print('R1G_EVIDENCE_PASS: 40 tests, 5 CRC-verified PNGs, all source-bound receipts')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        refuse('usage: r1g_evidence_gate.py RUNNER_TEMP')
    main(Path(sys.argv[1]))
