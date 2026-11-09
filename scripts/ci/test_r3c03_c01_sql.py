#!/usr/bin/env python3
"""SQLite CAS fixture for Room schema/transaction intent; not a replacement for Room tests."""
import hashlib
import hmac
import sqlite3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
migration = (ROOT / 'app/src/main/java/com/aurora/store/data/room/MigrationHelper.kt').read_text()
start = migration.index('val MIGRATION_15_16 = object : Migration(15, 16)')
end = migration.index('private const val TAG', start)
section = migration[start:end]
segments = re.findall(r'^\s*"([^"\n]*)"\s*\+?\s*$', section, re.M)
if len(segments) < 9:
    raise SystemExit('C01_SQL_REFUSED: migration SQL changed unexpectedly')
sql = ''.join(segments)

con = sqlite3.connect(':memory:')
con.executescript('''
CREATE TABLE download(packageName TEXT PRIMARY KEY, versionCode INTEGER NOT NULL,
 downloadedAt INTEGER NOT NULL, downloadStatus TEXT NOT NULL);
CREATE TABLE account(id TEXT PRIMARY KEY, isDefault INTEGER NOT NULL);
CREATE TABLE app_account_binding(packageName TEXT PRIMARY KEY, accountId TEXT NOT NULL);
''')
con.execute(sql)
cols = {row[1]: row[2] for row in con.execute('PRAGMA table_info(play_delivery_evidence)')}
for name in ('packageName', 'versionCode', 'attemptGeneration', 'accountBinding',
             'variant', 'state', 'verifiedApkVersion', 'unavailableVersion', 'resolvedFileCount'):
    assert name in cols, name
assert len([r for r in con.execute('PRAGMA table_info(play_delivery_evidence)') if r[5]]) == 1
con.execute('INSERT INTO download VALUES(?,?,?,?)', ('org.example.app', 73, 9001, 'PURCHASING'))
con.execute('INSERT INTO account VALUES(?,?)', ('opaque-account-a', 1))
selected = '''SELECT COALESCE(
 (SELECT accountId FROM app_account_binding WHERE packageName=?),
 (SELECT id FROM account WHERE isDefault=1 LIMIT 1), 'unbound')'''
active = '''SELECT COUNT(*) FROM download WHERE packageName=? AND versionCode=?
 AND downloadedAt=? AND downloadStatus IN ('QUEUED','PURCHASING','DOWNLOADING','VERIFYING')'''


def accept(package, version, attempt, account, outcome, variant="offer:1;lane:anonymous"):
    with con:
        if con.execute(active, (package, version, attempt)).fetchone()[0] != 1:
            return False
        if con.execute(selected, (package,)).fetchone()[0] != account:
            return False
        fingerprint = hmac.new(bytes(range(32)), account.encode(), hashlib.sha256).hexdigest()
        old = con.execute('SELECT attemptGeneration,accountBinding,variant FROM play_delivery_evidence WHERE packageName=?', (package,)).fetchone()
        if old is not None and old[0] == attempt and (old[1], old[2]) != (fingerprint, variant):
            return False
        con.execute('''INSERT OR REPLACE INTO play_delivery_evidence VALUES(?,?,?,?,?,?,?,?,?)''',
                    (package, version, attempt, fingerprint, variant, outcome, None, None, 2))
        return True


assert accept('org.example.app', 73, 9001, 'opaque-account-a', 'URLS_RESOLVED_NOT_VERIFIED')
assert 'opaque-account-a' not in str(con.execute('SELECT * FROM play_delivery_evidence').fetchone())
assert not accept('org.example.app', 74, 9001, 'opaque-account-a', 'UNKNOWN')
assert not accept('org.example.app', 73, 9000, 'opaque-account-a', 'UNKNOWN')
assert not accept('org.example.app', 73, 9001, 'opaque-account-b', 'UNKNOWN')
assert not accept('org.example.app', 73, 9001, 'opaque-account-a', 'UNKNOWN',
                  variant='offer:1;lane:authenticated')
con.execute("UPDATE download SET downloadStatus='CANCELLED'")
assert not accept('org.example.app', 73, 9001, 'opaque-account-a', 'NETWORK_OR_AUTH_FAILURE')
con.execute("UPDATE download SET downloadedAt=9002, downloadStatus='QUEUED'")
assert not accept('org.example.app', 73, 9001, 'opaque-account-a', 'NETWORK_OR_AUTH_FAILURE')
assert accept('org.example.app', 73, 9002, 'opaque-account-a', 'NETWORK_OR_AUTH_FAILURE')
con.execute("UPDATE account SET isDefault=0 WHERE id='opaque-account-a'")
con.execute("INSERT INTO account VALUES('opaque-account-b',1)")
assert not accept('org.example.app', 73, 9002, 'opaque-account-a', 'UNKNOWN')
assert not accept('org.example.app', 73, 9002, 'opaque-account-b', 'UNKNOWN')
con.execute('INSERT INTO app_account_binding VALUES(?,?)', ('org.example.app', 'opaque-account-a'))
assert accept('org.example.app', 73, 9003, 'opaque-account-a', 'UNKNOWN') is False
con.execute('DELETE FROM download')
assert not accept('org.example.app', 73, 9002, 'opaque-account-a', 'UNKNOWN')
print('R3C03_C01_SQL_CAS_PASS: migration columns, current generation, cancellation, account changes')
