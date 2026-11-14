#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R3C07 P02A: exact-source API36 signed-document read-only UI evidence.

This verifies an *actual* instrumented test log; it never submits an install,
claims browser publisher proof, or promotes source tests into Android evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

COUNT = 4
SHA = re.compile(r'[0-9a-f]{40}\Z')

class Refused(ValueError):
    pass


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def verify_log(raw: bytes) -> dict:
    if not raw or len(raw) > 3_000_000:
        raise Refused('empty or oversized Android instrumentation log')
    try:
        text = raw.decode('utf-8')
    except UnicodeError as error:
        raise Refused('non-UTF8 Android instrumentation log') from error
    if any(marker in text for marker in ('FAILURES!!!', 'INSTRUMENTATION_FAILED',
                                        'Process crashed', 'INSTRUMENTATION_CODE: 0')):
        raise Refused('Android instrumentation reported a failure')
    if len(re.findall(r'^INSTRUMENTATION_STATUS_CODE: 0\s*$', text, flags=re.M)) != COUNT:
        raise Refused('wrong successful Android test event count')
    if len(re.findall(r'^OK \(4 tests\)\s*$', text, flags=re.M)) != 1:
        raise Refused('actual four-test JUnit OK banner missing or duplicated')
    if len(re.findall(r'^INSTRUMENTATION_CODE: -1\s*$', text, flags=re.M)) != 1:
        raise Refused('Android instrumentation final code missing')
    if 'ArtifactReviewP02DeviceTest' not in text:
        raise Refused('actual P02A test class not identified in instrumentation log')
    return {'actual_instrumentation_tests': COUNT, 'log_sha256': digest(raw)}


def seal(log: Path, output: Path, sha: str, run: str) -> dict:
    if not SHA.fullmatch(sha) or not run.isdecimal() or int(run) <= 0:
        raise Refused('missing exact GitHub source SHA or run ID')
    if not log.is_file() or log.is_symlink():
        raise Refused('missing actual hosted Android instrumentation log')
    result = verify_log(log.read_bytes())
    receipt = {
        'overall': 'PASS', 'phase': 'R3C07_P02A', 'source_sha': sha, 'run_id': run,
        'android_api': 36, **result,
        'signed_document_content_uri_review': True,
        'read_only_ui': True,
        'installation_qualified': False,
        'publisher_authenticated': False,
        'physical_device_qualified': False,
        'release_qualified': False,
        'actual_talkback_service_qualified': False,
        'device_font_scale_changed': False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, sort_keys=True, indent=2)+'\n', encoding='utf-8')
    return receipt


def selftest() -> None:
    cls = 'com.aurora.store.data.artifact.ArtifactReviewP02DeviceTest'
    good = ('INSTRUMENTATION_STATUS: class='+cls+'\n'
            + 'INSTRUMENTATION_STATUS_CODE: 0\n' * COUNT
            + 'Time: 4.00\nOK (4 tests)\nINSTRUMENTATION_CODE: -1\n').encode()
    assert verify_log(good)['actual_instrumentation_tests'] == COUNT
    bad = {
        'missing class': good.replace(cls.encode(), b'other'),
        'one fewer success': good.replace(b'INSTRUMENTATION_STATUS_CODE: 0\n', b'', 1),
        'duplicate success': good + b'INSTRUMENTATION_STATUS_CODE: 0\n',
        'JUnit false count': good.replace(b'OK (4 tests)', b'OK (3 tests)'),
        'missing terminal': good.replace(b'INSTRUMENTATION_CODE: -1', b''),
        'Android failure': good + b'FAILURES!!!\n',
        'duplicate banner': good + b'OK (4 tests)\n',
        'no log': b'',
    }
    for name, case in bad.items():
        try:
            verify_log(case)
        except Refused:
            pass
        else:
            raise AssertionError('negative instrumentation log accepted: '+name)
    with tempfile.TemporaryDirectory(prefix='aurora-r3c07-p02a-') as tmp:
        directory = Path(tmp)
        source, output = directory/'real-log.txt', directory/'receipt.json'
        source.write_bytes(good)
        data = seal(source, output, 'a'*40, '12345')
        assert json.loads(output.read_text()) == data
        assert data['log_sha256'] == digest(good)
        assert data['installation_qualified'] is False
        assert output.read_bytes().endswith(b'\n')
        try:
            seal(source, output, 'invalid', '12345')
        except Refused:
            pass
        else:
            raise AssertionError('invalid GitHub SHA accepted')
    print('R3C07_P02A_RECEIPT_REGRESSION_PASS: 1 positive, 9 negatives')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--log', type=Path)
    parser.add_argument('--output', type=Path)
    options = parser.parse_args()
    if options.selftest:
        selftest()
        return
    if options.log is None or options.output is None:
        parser.error('both --log and --output required')
    receipt = seal(options.log, options.output,
                   os.environ.get('GITHUB_SHA', ''), os.environ.get('GITHUB_RUN_ID', ''))
    print('R3C07_P02A_API36_SIGNED_CONTENT_UI_PASS: tests=4 log_sha256='+receipt['log_sha256'])


if __name__ == '__main__':
    try:
        main()
    except (Refused, OSError) as error:
        print('R3C07_P02A_RECEIPT_REFUSED: '+str(error), file=sys.stderr)
        raise SystemExit(1)
