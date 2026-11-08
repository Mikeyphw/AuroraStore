#!/usr/bin/env python3
"""Execute R2B's actual Room UPDATE against SQLite to prove generation isolation."""
# SPDX-License-Identifier: GPL-3.0-or-later
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "app/src/main/java/com/aurora/store/data/room/download/DownloadDao.kt").read_text()
pattern = r'@Query\(\s*"""([^"]*)"""\s*\)\s*suspend fun transitionInstallAttempt\('
match = re.search(pattern, SOURCE, re.DOTALL)
assert match, "R2B_SQL_CAS_REFUSED: missing Room transition query"
query = match.group(1)

connection = sqlite3.connect(":memory:")
connection.execute(
    "CREATE TABLE download (packageName TEXT PRIMARY KEY, versionCode INTEGER, "
    "downloadedAt INTEGER, downloadStatus TEXT)"
)
connection.execute("INSERT INTO download VALUES ('org.example.app', 42, 1200, 'INSTALLING')")


def state():
    return connection.execute("SELECT downloadStatus FROM download").fetchone()[0]


def apply(version, attempt, expected, replacement):
    return connection.execute(
        query,
        {
            "packageName": "org.example.app",
            "versionCode": version,
            "attemptKey": attempt,
            "expected": expected,
            "replacement": replacement,
        },
    ).rowcount


assert apply(41, 1200, "INSTALLING", "INSTALLED") == 0
assert state() == "INSTALLING"
print("R2B_SQL_PASS old_version")
assert apply(42, 1199, "INSTALLING", "INSTALLED") == 0
assert state() == "INSTALLING"
print("R2B_SQL_PASS old_attempt")
assert apply(42, 1200, "COMPLETED", "INSTALLED") == 0
assert state() == "INSTALLING"
print("R2B_SQL_PASS prior_state_drift")
assert apply(42, 1200, "INSTALLING", "AWAITING_INSTALL") == 1
assert apply(42, 1200, "INSTALLING", "AWAITING_INSTALL") == 0
print("R2B_SQL_PASS duplicate_pending")
assert apply(42, 1200, "AWAITING_INSTALL", "INSTALLED") == 1
assert apply(42, 1200, "AWAITING_INSTALL", "FAILED") == 0
assert state() == "INSTALLED"
print("R2B_SQL_PASS late_failure")
connection.execute(
    "UPDATE download SET versionCode=43, downloadedAt=1201, downloadStatus='COMPLETED'"
)
assert apply(42, 1200, "COMPLETED", "INSTALLED") == 0
assert state() == "COMPLETED"
print("R2B_SQL_PASS replaced_generation")
print("R2B_SQL_CAS_PASS: 6 replay cases")
