# Aurora Store R1B — Attempt Isolation, Network Cancellation and Safe Resume

**Repository:** Mikeyphw/AuroraStore

**Exact merged base:** `cee2f5b79d4d743b97820ec4b30461d0b99fb2ae`

**Branch:** `feature/r1b-download-recovery-20261107`

## Scope

- Persist a unique, monotonic attempt identifier using the existing `downloadedAt` column (the existing download queue timestamp). This avoids a new Room migration and tracks a retry as a fresh download attempt.
- Include that identifier in WorkManager input, tags, and unique-work naming.
- Require package + version + attempt for cancellation, worker status, progress, file metadata and orphan-recovery SQL.
- Include the attempt ID in cancellation notifications so an old action cannot cancel a newer retry.
- Cancel obsolete WorkManager jobs using their exact identity. Preserve the ability to stop legacy R1A version-only workers.
- Keep the same-package APK write lock across workers, including the window while an old worker is being cancelled.
- A child coroutine observes cancellation and cancels the active synchronous OkHttp Call. `CoroutineWorker.onStopped()` is final and is **not** overridden.
- Validate HTTP Content-Range when appending to a partial APK. Reject mismatched ranges and restart the partial from zero; handle HTTP 416 for stale partials.
- Do not requeue while an install has already entered `INSTALLING`.
- Add a hosted R1B source check that executes actual Room SQL statements using sqlite3.

## Bounded stalls

The existing OkHttpClient already sets a 25-second `readTimeout` and `connectTimeout`. R1B wires cancellation into the active HTTP call and treats malformed resume responses as bounded transient failures. A separate persistent download heartbeat/wall-clock watchdog is **not** added here; it remains a follow-up. Slow transfers that continue delivering bytes are not forcibly terminated by a total download deadline.

## Not included

- The older-version picker, Play Asset Delivery support, or Material 3 Expressive UI.
- Device and OS installer recovery (R2).
- New pause/resume controls.

## Qualification

1. Run `python3 scripts/ci/check_foundation.py`, `check_r1a.py`, `check_r1b.py`.
2. Hosted GitHub Actions `assembleVanillaDebug ktlintCheck testVanillaDebugUnitTest` must pass.
3. On-device: cancel an active download during a blocked HTTP read and confirm return to `CANCELLED` without a ghost job.
4. Retry a just-cancelled download of the same version, and confirm a fresh WorkManager operation progresses without state races or corrupted temp files.
5. Verify a simulated server returning the wrong Content-Range offset causes clean retry, not a corrupted APK.
6. Ensure pause/restart on flaky connections retains verified data and only re-requests necessary file bytes.

**Note:** The source-pinned overlay and offline tests do not themselves demonstrate an Android build or on-device behavior. Those gates require GitHub Actions and device acceptance after the overlay is pushed.
