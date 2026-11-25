#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R3C06 P4: measured, exact-source API36 *read-only* acceptance receipt.

The optional, explicitly authorized live install and real-world AAB matrix have
separate receipts and are not implied by this PASS. This module does not install
or uninstall anything and never modifies Play evidence.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

SPECS = {
    'c04_private_import.txt': (17, 'C04_STAGING'),
    'c04_real_apk_signer.txt': (7, 'C04_SIGNER'),
    'c04_real_session_consent.txt': (5, 'C04_SESSION_NONINSTALLING'),
    'c04_07_review_ui.txt': (3, 'C04_REVIEW_UI'),
    'r3c05_provider_discovery_ui.txt': (3, 'C05_PROVIDER_UI'),
    'r3c06_split_targeting.txt': (4, 'C06_SPLIT_TARGETING'),
    'r3c06_archive_descriptors.txt': (6, 'C06_ARCHIVE_DESCRIPTORS'),
    'r3c06_real_signed_archives.txt': (6, 'C06_SIGNED_ARCHIVES'),
}
EXPECTED_COUNT = sum(tests for tests, _ in SPECS.values())
FAILURE = re.compile(r'FAILURES!!!|INSTRUMENTATION_FAILED|INSTRUMENTATION_STATUS_CODE:\s*-[12]|\bFAILURE\b')
SOURCE_SHA = re.compile(r'^[0-9a-f]{40}$')
RUN_ID = re.compile(r'^[1-9][0-9]*$')

class Refused(Exception):
    pass

def require(ok, reason):
    if not ok:
        raise Refused(reason)

def measure(logs: Path, source_sha: str, run_id: str, android_api: int):
    require(SOURCE_SHA.fullmatch(source_sha) is not None, 'missing exact 40-character commit SHA')
    require(RUN_ID.fullmatch(run_id) is not None, 'missing positive Actions run id')
    require(android_api == 36, 'actual API36 runtime required')
    require(logs.is_dir() and not logs.is_symlink(), 'missing real instrumentation log directory')
    suites = {}
    for name, (count, label) in SPECS.items():
        p = logs / name
        require(p.is_file() and not p.is_symlink(), 'missing test log: ' + name)
        require(0 < p.stat().st_size <= 2 * 1024 * 1024, 'unbounded/empty test log: ' + name)
        data = p.read_bytes()
        lines = data.decode('utf-8', errors='replace')
        ok = re.findall(r'^OK \((\d+) tests?\)\s*$', lines, re.MULTILINE)
        require(ok == [str(count)], f'wrong or repeated success line in {name}: {ok!r}')
        require(not FAILURE.search(lines), 'failure marker in ' + name)
        suites[label] = {'tests_executed': count, 'log_sha256': hashlib.sha256(data).hexdigest(),
                         'log_file': name}
    return {
        'overall': 'PASS', 'qualification_scope': 'API36_READONLY_DEVICE_TESTS_ONLY',
        'source_sha': source_sha, 'run_id': run_id, 'android_api': 36,
        'suite_count': len(suites), 'executed_tests': EXPECTED_COUNT,
        'suites': suites,
        'real_signed_apk_wrapped_fixture_tests': SPECS['r3c06_real_signed_archives.txt'][0],
        'real_world_apkm_xapk_dialect_qualified': False,
        'bundletool_device_matrix_qualified': False,
        'real_android_installation_performed_by_this_gate': False,
        'real_android_installation_qualified': False,
        'google_play_evidence_qualified_by_this_gate': False,
        'physical_device_qualified': False, 'release_qualified': False,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--logs', required=True, type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    args = parser.parse_args()
    sha = os.environ.get('GITHUB_SHA', '')
    run_id = os.environ.get('GITHUB_RUN_ID', '')
    current = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, timeout=15)
    require(current.returncode == 0 and current.stdout.strip() == sha,
            'checkout differs from exact GitHub Actions source commit')
    api = subprocess.run(['adb', 'shell', 'getprop', 'ro.build.version.sdk'],
                         capture_output=True, text=True, timeout=30)
    require(api.returncode == 0 and api.stdout.strip() == '36', 'real API36 device missing')
    receipt = measure(args.logs, sha, run_id, 36)
    require(not args.receipt.is_symlink(), 'refusing symlinked receipt')
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.receipt.with_name(args.receipt.name + '.tmp')
    require(not tmp.exists() and not tmp.is_symlink(), 'receipt temporary path exists')
    try:
        tmp.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n', encoding='utf-8')
        tmp.replace(args.receipt)
    finally:
        if tmp.exists(): tmp.unlink()
    print('R3C06_P4_API36_READONLY_PASS exact_sha=' + sha +
          ' tests=' + str(EXPECTED_COUNT) + ' receipt=' + str(args.receipt))

if __name__ == '__main__':
    try:
        main()
    except (Refused, subprocess.TimeoutExpired, OSError, ValueError) as e:
        print('R3C06_P4_READONLY_REFUSED: ' + str(e), file=sys.stderr)
        raise SystemExit(2)
