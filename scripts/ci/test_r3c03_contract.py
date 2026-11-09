#!/usr/bin/env python3
"""Adversarial static mutations of the R3C03 reducer; JVM tests run hosted."""
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import re

root = Path(__file__).resolve().parents[2]
source = (root / 'app/src/main/java/com/aurora/store/data/model/PlayExactVersionOutcomePolicy.kt').read_text()


def compact(s):
    # Source contract is deliberately formatting-insensitive for Kotlin conditions.
    return re.sub(r'\s+', '', re.sub(r'//[^\n]*|/\*[\s\S]*?\*/', '', s))


def predicate(code):
    s = compact(code)
    guards = (
        'event.key!=active||(previous!=null&&previous.key!=active)',
        'event.refusedVersion!=version',
        'event.proof!=UnavailabilityProof.EXPLICIT_EXACT_VERSION_DELIVERY_REFUSAL',
        'current.state==State.VERIFIED_SET',
        'event.resolvedVersion!=version||event.fileCount<=0',
        'event.downloadedVersion!=version',
        'current.state!=State.URLS_RESOLVED_NOT_VERIFIED',
        'current.resolvedFileCount!=event.fileCount',
        'event.verifiedVersion!=version',
        'current.state!=State.BYTES_DOWNLOADED_NOT_VERIFIED',
        'current.resolvedFileCount!=event.verifiedFileCount',
        'current.verifiedApkVersion!=version',
    )
    baseline = compact(source)
    return all(s.count(g) == baseline.count(g) and baseline.count(g) >= 1 for g in guards)


assert predicate(source), 'R3C03_SOURCE_REFUSED: one or more fail-closed predicates missing'
mutations = (
    ('event.key != active', 'event.key == active'),
    ('previous.key != active', 'previous.key == active'),
    ('event.refusedVersion != version', 'event.refusedVersion == version'),
    ('event.proof != UnavailabilityProof.EXPLICIT_EXACT_VERSION_DELIVERY_REFUSAL',
     'event.proof == UnavailabilityProof.EXPLICIT_EXACT_VERSION_DELIVERY_REFUSAL'),
    ('current.state == State.VERIFIED_SET', 'current.state != State.VERIFIED_SET'),
    ('event.resolvedVersion != version', 'event.resolvedVersion == version'),
    ('event.fileCount <= 0', 'event.fileCount >= 0'),
    ('event.downloadedVersion != version', 'event.downloadedVersion == version'),
    ('current.state != State.URLS_RESOLVED_NOT_VERIFIED',
     'current.state == State.URLS_RESOLVED_NOT_VERIFIED'),
    ('current.resolvedFileCount != event.fileCount',
     'current.resolvedFileCount == event.fileCount'),
    ('event.verifiedVersion != version', 'event.verifiedVersion == version'),
    ('current.state != State.BYTES_DOWNLOADED_NOT_VERIFIED',
     'current.state == State.BYTES_DOWNLOADED_NOT_VERIFIED'),
    ('current.resolvedFileCount != event.verifiedFileCount',
     'current.resolvedFileCount == event.verifiedFileCount'),
    ('current.verifiedApkVersion != version', 'current.verifiedApkVersion == version'),
)
for old, new in mutations:
    assert old in source, f'R3C03_MUTATION_FIXTURE_MISSING: {old}'
    changed = source.replace(old, new, 1)
    assert not predicate(changed), f'R3C03_MUTATION_NOT_REJECTED: {old}'
print(f'R3C03_01_NEGATIVE_PASS: {len(mutations)} static adversarial mutations rejected')
