#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline DDL/retention contract, NOT a replacement for Android Room device tests."""
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / 'app/schemas/com.aurora.store.data.room.AuroraDatabase'
TEST = ROOT / 'app/src/androidTest/java/com/aurora/store/data/room/play/RoomV15ToV16MigrationDeviceTest.kt'
MIGRATION = ROOT / 'app/src/main/java/com/aurora/store/data/room/MigrationHelper.kt'


def require(cond, msg):
    if not cond:
        raise SystemExit('R3C03_C03_REFUSED: ' + msg)


def compact(sql):
    return re.sub(r'\s+', '', sql).lower()


v15 = json.loads((SCHEMAS / '15.json').read_text())['database']
test = TEST.read_text()
raw_tables = re.findall(r'"""(CREATE TABLE IF NOT EXISTS .*?)"""\.trimIndent\(\)', test, re.S)
# Formatter can put whitespace after opening quote; tolerate it while preserving SQL comparison.
if not raw_tables:
    raw_tables = re.findall(r'"""\s*(CREATE TABLE IF NOT EXISTS .*?)\s*"""\.trimIndent\(\)', test, re.S)
require(len(raw_tables) == len(v15['entities']), 'test fixture does not contain every v15 table')
actual = {compact(sql): sql for sql in raw_tables}
for entity in v15['entities']:
    expected = entity['createSql'].replace('${TABLE_NAME}', entity['tableName'])
    require(compact(expected) in actual, 'v15 DDL drift: ' + entity['tableName'])
require(v15['identityHash'] in test, 'Room v15 identity hash differs from checked-in export')

migration = MIGRATION.read_text()
start = migration.find('val MIGRATION_15_16 =')
end = migration.find('private const val TAG', start)
require(0 <= start < end, 'missing isolated MIGRATION_15_16')
body = migration[start:end]
parts = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', body)
require(parts, 'missing migration SQL')
sql = ''.join(parts)
require(sql.startswith('CREATE TABLE IF NOT EXISTS `play_delivery_evidence`'), 'unexpected migration operation')
require('DROP TABLE' not in body.upper() and 'DELETE FROM' not in body.upper(), 'destructive migration')
require('PRIMARY KEY(`packageName`)' in sql, 'unexpected evidence row key')

conn = sqlite3.connect(':memory:')
conn.execute('PRAGMA foreign_keys=ON')
for ddl in raw_tables:
    conn.execute(ddl)
for e in v15['entities']:
    for idx in e.get('indices', []):
        conn.execute(idx['createSql'].replace('${TABLE_NAME}', e['tableName']))
for stmt in v15['setupQueries']:
    conn.execute(stmt)
conn.execute(
    "INSERT INTO `download` VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    ('com.aurora.migration.fixture', 737, 0, 0, 'v15 persisted', '', 8, 0,
     'FAILED', 0, 0, 0, 1, 0, '[]', '[]', 23, 9001, 0),
)
conn.execute(
    "INSERT INTO `account` (`id`,`type`,`email`,`tokenType`,`authViaMicroG`,`isDefault`,`addedAt`) "
    "VALUES ('v15-account','ANONYMOUS','','NONE',0,1,1234)"
)
conn.execute(
    "INSERT INTO `app_account_binding` VALUES ('com.aurora.migration.fixture','v15-account')"
)
conn.execute(sql)
require(conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'SQLite integrity')
require(conn.execute('SELECT versionCode,downloadedAt FROM download').fetchone() == (737,9001), 'download lost')
require(conn.execute('SELECT id,addedAt FROM account').fetchone() == ('v15-account',1234), 'account lost')
require(conn.execute('SELECT accountId FROM app_account_binding').fetchone()[0] == 'v15-account', 'binding lost')
require(conn.execute('SELECT count(*) FROM play_delivery_evidence').fetchone()[0] == 0, 'evidence not empty')
assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
conn.close()

v16_path = SCHEMAS / '16.json'
if v16_path.is_file():
    v16 = json.loads(v16_path.read_text())['database']
    tables = {e['tableName']: e for e in v16['entities']}
    require('play_delivery_evidence' in tables, 'generated v16 schema lacks evidence')
    require(len(tables) == len(v15['entities']) + 1, 'unexpected v16 table count')
    for name in (e['tableName'] for e in v15['entities']):
        require(name in tables, 'v16 lost v15 table: ' + name)
    require(compact(tables['play_delivery_evidence']['createSql'].replace(
        '${TABLE_NAME}', 'play_delivery_evidence')) == compact(sql),
        'Room-generated v16 table differs from migration')
    print('R3C03_C03_HOSTED_V16_SCHEMA_CONTRACT_PASS')
else:
    print('R3C03_C03_V16_SCHEMA_NOT_TRACKED: generate with hosted KSP; do not fabricate schema')
print('R3C03_C03_SQLITE_FIXTURE_PASS: offline simulation; device Room migration remains required')
