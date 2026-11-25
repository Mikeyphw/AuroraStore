#!/usr/bin/env python3
"""R1C source invariants (JVM tests execute the actual watchdog in hosted CI)."""
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[2]
src = root / 'app/src/main/java/com/aurora/store'
worker = (src / 'data/work/DownloadWorker.kt').read_text()
helper = (src / 'data/helper/DownloadHelper.kt').read_text()
watchdog = (src / 'data/work/TransferStallWatchdog.kt').read_text()
test = (root / 'app/src/test/java/com/aurora/store/data/work/TransferStallWatchdogTest.kt').read_text()
checks = {
    'monotonic clock used for transfer watchdog': 'TransferStallWatchdog(SystemClock::elapsedRealtime)' in worker,
    'network stalls are detected after byte inactivity': 'stallWatchdog.isStalled()' in worker and 'STALL_POLL_INTERVAL_MS = 15_000L' in worker,
    'stalled transfer closes active HTTP call': 'stalledTransfer.compareAndSet(false, true)' in worker and 'activeHttpCall.getAndSet(null)?.cancel()' in worker,
    'active transfer starts heartbeat before requesting bytes': 'stallWatchdog.begin()' in worker and worker.index('stallWatchdog.begin()') < worker.index('val response = get(url, headers)'),
    'positive bytes refresh heartbeat': 'stallWatchdog.onBytes(info.bytesCopied)' in worker and 'if (count > 0L' in watchdog,
    'stalled bytes never become installable files': 'if (stalledTransfer.get()) throw DownloadStalledException()' in worker,
    'stalled work retries with WorkManager backoff': 'is DownloadStalledException -> true' in worker and 'Result.retry()' in worker,
    'heartbeat disarmed after transfer': 'stallWatchdog.finish()' in worker and 'fun finish()' in watchdog,
    'queued and finished transfers never false alarm': 'lastByteAt ?: return false' in watchdog and 'lastByteAt = null' in watchdog,
    'queue recovery repeats while app remains running': 'monitorOrphanedDownloads()' in helper and 'delay(ORPHAN_CHECK_INTERVAL_MS)' in helper,
    'orphan recovery preserves live generation identity': 'matchingWork.none { !it.state.isFinished }' in helper and 'item.downloadedAt' in helper,
    'watchdog clock is independently testable': 'private val clock: () -> Long' in watchdog and 'timeoutMillis: Long' in watchdog,
    'five executable JVM tests exercise timeout cases': test.count('@Test') == 5,
}
for name, valid in checks.items():
    print(('PASS ' if valid else 'FAIL ') + name)
if not all(checks.values()):
    print('R1C_CONTRACT_FAIL', file=sys.stderr)
    sys.exit(1)
print(f'R1C_CONTRACT_PASS checks={len(checks)}')
