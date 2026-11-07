#!/usr/bin/env python3
"""R1B invariants: exercise the actual Room SQL with sqlite3, no Android SDK required."""
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import re
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'app/src/main/java/com/aurora/store'

def read(p):
    return (SRC/p).read_text()

DAO = read('data/room/download/DownloadDao.kt')
HELPER = read('data/helper/DownloadHelper.kt')
WORKER = read('data/work/DownloadWorker.kt')
RECEIVER = read('data/receiver/DownloadCancelReceiver.kt')
NOTIFICATION = read('util/NotificationUtil.kt')


def sql_for(name):
    # Connect the SQL annotation to the specific DAO function rather than
    # testing a reconstructed query that might not reflect production code.
    marker = 'suspend fun ' + name + '('
    if DAO.count(marker) != 1:
        raise ValueError(f'{name}: expected one DAO method')
    method_pos = DAO.index(marker)
    annotation_pos = DAO.rfind('@Query(', 0, method_pos)
    if annotation_pos < 0:
        raise ValueError(f'{name}: missing Room @Query')
    annotation = DAO[annotation_pos:method_pos]
    match = re.fullmatch(r'@Query\(\s*"""(?P<sql>.*?)"""\s*\)\s*',
                         annotation, flags=re.S)
    if not match:
        raise ValueError(f'{name}: cannot parse SQL annotation')
    return match.group('sql').strip()


def check(name, ok):
    print(('PASS ' if ok else 'FAIL ') + name)
    if not ok: raise ValueError(name)


def setup():
    con = sqlite3.connect(':memory:')
    con.execute('''CREATE TABLE download (
        packageName TEXT PRIMARY KEY,
        versionCode INTEGER NOT NULL,
        downloadedAt INTEGER NOT NULL,
        downloadStatus TEXT NOT NULL,
        fileList TEXT NOT NULL DEFAULT '[]',
        sharedLibs TEXT NOT NULL DEFAULT '[]',
        progress INTEGER NOT NULL DEFAULT 0,
        speed INTEGER NOT NULL DEFAULT 0,
        timeRemaining INTEGER NOT NULL DEFAULT 0
    )''')
    con.execute('''INSERT INTO download (packageName, versionCode, downloadedAt, downloadStatus)
                   VALUES ('app.test', 13, 500, 'CANCELLED')''')
    return con


def run():
    con = setup()
    retry = sql_for('retryWithNewAttempt')
    cancel = sql_for('cancelActiveDownload')
    status = sql_for('updateWorkerStatus')
    progress = sql_for('updateWorkerProgress')
    orphan = sql_for('failOrphanedDownload')
    files = sql_for('updateWorkerFiles')
    libs = sql_for('updateWorkerSharedLibs')

    args = {'packageName': 'app.test', 'versionCode': 13, 'previousAttempt': 500, 'now': 500}
    changed = con.execute(retry, args).rowcount
    new_attempt = con.execute('SELECT downloadedAt FROM download').fetchone()[0]
    check('same-version retry creates monotonic generation', changed == 1 and new_attempt == 501)
    check('duplicate retry rejected', con.execute(retry, args).rowcount == 0)

    check('stale worker cannot update new attempt status', con.execute(status, {
        'packageName':'app.test', 'versionCode':13,'attemptKey':500,'downloadStatus':'DOWNLOADING'
    }).rowcount == 0)
    check('current worker can update own status', con.execute(status, {
        'packageName':'app.test', 'versionCode':13,'attemptKey':501,'downloadStatus':'DOWNLOADING'
    }).rowcount == 1)
    check('stale worker cannot update progress', con.execute(progress, {
        'packageName':'app.test','versionCode':13,'attemptKey':500,
        'progress':99,'speed':123,'timeRemaining':1000
    }).rowcount == 0)
    check('stale worker cannot replace files', con.execute(files, {
        'packageName':'app.test','versionCode':13,'attemptKey':500,'fileList':'stale'
    }).rowcount == 0)
    check('stale worker cannot replace shared libraries', con.execute(libs, {
        'packageName':'app.test','versionCode':13,'attemptKey':500,'sharedLibs':'stale'
    }).rowcount == 0)
    check('stale cancellation cannot cancel fresh attempt', con.execute(cancel, {
        'packageName':'app.test','versionCode':13,'attemptKey':500
    }).rowcount == 0)
    check('current attempt can cancel', con.execute(cancel, {
        'packageName':'app.test','versionCode':13,'attemptKey':501
    }).rowcount == 1)
    check('cancelled attempt cannot be resurrected', con.execute(status, {
        'packageName':'app.test','versionCode':13,'attemptKey':501,'downloadStatus':'DOWNLOADING'
    }).rowcount == 0)
    check('orphan recovery cannot change cancelled row', con.execute(orphan, {
        'packageName':'app.test','versionCode':13,'attemptKey':501
    }).rowcount == 0)

    check('work request carries persisted attempt ID',
          '.putLong(ATTEMPT_KEY, download.downloadedAt)' in HELPER and
          '.addTag("$ATTEMPT_KEY:${download.downloadedAt}")' in HELPER and
          'download.downloadedAt,' in HELPER)
    check('worker rejects stale attempt before any network request',
          'current.downloadedAt != expectedAttempt' in WORKER and
          WORKER.index('current.downloadedAt != expectedAttempt') < WORKER.index('playClientFor(packageName)'))
    check('worker network calls follow coroutine cancellation',
          'awaitCancellation()' in WORKER and
          'activeHttpCall.getAndSet(null)?.cancel()' in WORKER and
          'activeHttpCall.set(call)' in WORKER and
          'activeHttpCall.compareAndSet(call, null)' in WORKER)
    check('same-package transfers never overlap',
          'transferLocks.getOrPut(packageName) { Mutex() }' in WORKER and
          'lock.lock()' in WORKER and 'lock.unlock()' in WORKER)
    check('resume checks Content-Range offset',
          'response.header("Content-Range")' in WORKER and
          'if (returnedStart != existingBytes)' in WORKER and
          'tmpFile.delete()' in WORKER and
          'is InvalidResumeRangeException -> true' in WORKER)
    check('app install state cannot be overwritten by new enqueue',
          'if (existing?.status == DownloadStatus.INSTALLING) return' in HELPER)
    check('notification cancellation carries the exact attempt',
          'putExtra(DownloadHelper.ATTEMPT_KEY, download.downloadedAt)' in NOTIFICATION)
    check('receiver never cancels a newer notification attempt',
          'getLongExtra(DownloadHelper.ATTEMPT_KEY, -1L)' in RECEIVER and
          'cancelDownload(packageName, expectedAttempt)' in RECEIVER)
    check('no Room schema upgrade required',
          'downloadedAt = CASE WHEN downloadedAt >= :now' in DAO)
    print('R1B_CONTRACT_PASS checks=20')

if __name__ == '__main__':
    try:run()
    except Exception as e:
        print('R1B_CONTRACT_FAIL ' + str(e),file=sys.stderr)
        raise SystemExit(1)
