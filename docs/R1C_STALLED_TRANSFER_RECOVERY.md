# Aurora Store R1C — Stalled-transfer watchdog and live queue recovery

**Base:** `Mikeyphw/AuroraStore` `master` at `19ce17c120a0ec7f0ff602fc7c5765cc91f7659f` (merged R1B).

## Changes

- A monotonic (elapsed realtime) byte-level heartbeat is active only while an APK/patch transfer is in progress. Zero-byte events do not reset it.
- If no bytes arrive for 90 seconds, a coroutine watchdog checks every 15 seconds, cancels the in-flight OkHttp call, and makes the worker return a retryable stalled-transfer failure.
- Existing WorkManager exponential backoff and its five-attempt bound remain in effect; validated existing partials are retained for network/timeout retries, rather than being erased on a transient stall.
- A large or slow download is **not** considered stalled as long as it transfers bytes within each timeout window; waiting in queue and local verification are excluded from this network watchdog.
- The normal download helper now reconciles orphaned `PURCHASING`/`DOWNLOADING`/`VERIFYING` rows every two minutes as well as at startup. It checks the exact WorkManager package, version **and attempt** tags, so live/backoff workers are not marked failed.
- Add deterministic, clock-injected JVM tests and source-contract checks for all of these invariants; GitHub Actions continues to run the existing source, ktlint, compilation and JVM gates.

## Scope & limitations

- R1C monitors the OkHttp transfer of APK files and patch files, not the upstream Play delivery-metadata APIs or third-party installers. Their own request-level timeouts and R2 recovery are separate work.
- An Android force-stop or blocked disk I/O cannot be corrected by a coroutine monitor alone. The periodic WorkManager orphan reconciler handles stale persisted slots while Aurora runs; user-cancel during committed Android installation remains unsupported.
- No database schema migration, permissions, downloaded-file format change, UI overhaul, or new SDK requirement.
- Offline checks are not Android qualification; merge only after CI, then validate interruption, slow transfer, cancel, restart, and retry on devices.

## HF01 — R1B contract compatibility

The R1C worker adds `DownloadStalledException` to the Kotlin `when` branch that
already retries `InvalidResumeRangeException`. R1B's static check matched the
single-exception spelling instead of the invariant and incorrectly failed.
HF01 changes **only the R1B check** in addition to the original R1C payload,
accepting either a single invalid-range exception or the combined group.
The SQL/Content-Range guard assertions remain required. The R1C contract
additionally requires the stalled-transfer exception to be retryable.

The installer first attempts to verify and resume the untouched worktree from
`R1C_WORKTREE_RETAINED`. When it is unavailable, it does a fresh source-pinned
R1C application including the corrected test. It never force-pushes or resets
other local work. Android/Kotlin compilation remains a hosted CI gate.
