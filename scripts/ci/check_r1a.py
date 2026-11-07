#!/usr/bin/env python3
"""Static invariants for R1A; Gradle separately compiles the Kotlin and Room queries."""
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[2]
base = root / "app/src/main/java/com/aurora/store"
files = {name: (base / name).read_text() for name in (
    "data/model/DownloadStatus.kt", "data/room/download/DownloadDao.kt",
    "data/helper/DownloadHelper.kt", "data/work/DownloadWorker.kt",
    "compose/ui/sheets/DownloadActionsSheet.kt",
    "data/receiver/DownloadCancelReceiver.kt",
)}
status = files["data/model/DownloadStatus.kt"]
dao = files["data/room/download/DownloadDao.kt"]
helper = files["data/helper/DownloadHelper.kt"]
worker = files["data/work/DownloadWorker.kt"]
sheet = files["compose/ui/sheets/DownloadActionsSheet.kt"]
receiver = files["data/receiver/DownloadCancelReceiver.kt"]
# Only compare operations within cancelDownload(). The helper also cancels
# superseded versions in enqueue(), before the cancelDownload() declaration.
# A whole-file find() compared against that unrelated call and produced a false FAIL.
cancel_marker = '    suspend fun cancelDownload(packageName: String) {'
cancel_body = (
    helper.split(cancel_marker, 1)[1].split('\n    }', 1)[0]
    if cancel_marker in helper else ''
)
cancel_room_pos = cancel_body.find('downloadDao.cancelActiveDownload(packageName, current.versionCode)')
cancel_work_pos = cancel_body.find('cancelUniqueWork(')
checks = {
    "verification remains cancellable": "val running = setOf(QUEUED, PURCHASING, DOWNLOADING, VERIFYING)" in status,
    "cancel Room row atomically": "suspend fun cancelActiveDownload(packageName: String, versionCode: Long): Int" in dao,
    "worker status matches version": "suspend fun updateWorkerStatus(" in dao and "versionCode = :versionCode" in dao,
    "stale worker cannot assume latest version": "current.versionCode != expectedVersion" in worker,
    "worker input is versioned": '.putLong(VERSION_CODE, download.versionCode)' in helper,
    "worker owns install transition": 'if (!notifyStatus(DownloadStatus.INSTALLING, isProgress = true))' in worker,
    "cancel status first": cancel_room_pos >= 0 and cancel_work_pos >= 0 and cancel_room_pos < cancel_work_pos,
    "cancel-all handles each version": '?.forEach { cancelDownload(it.packageName) }' in helper,
    "orphan recovery uses matching live WorkInfo": 'matchingWork.none { !it.state.isFinished }' in helper,
    "no obsolete nullable-boolean recovery": '?.run { downloadDao.updateStatus(it.packageName, DownloadStatus.FAILED) }' not in helper,
    "notification cancel works while verifying": 'if (download.isActive)' in sheet,
    "notification receiver uses goAsync": 'val result = goAsync()' in receiver and 'result.finish()' in receiver,
    "clear-all cancels download workers": 'cancelAllWorkByTag(DOWNLOAD_WORKER)' in helper,
    "superseded versions are cancelled": '"$DOWNLOAD_WORKER/${existing.packageName}/${existing.versionCode}"' in helper,
    "stopped worker cannot write progress": 'if (isStopped && status != DownloadStatus.CANCELLED) return false' in worker,
}
failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(("PASS " if ok else "FAIL ") + name)
if failed:
    print("R1A_CONTRACT_FAIL", file=sys.stderr)
    raise SystemExit(1)
print(f"R1A_CONTRACT_PASS checks={len(checks)}")
