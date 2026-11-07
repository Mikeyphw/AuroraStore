# R1A — Download cancellation and lifecycle safety

Starting point: fork `master` commit `b02559cafcb8d973b8430b8cb93faec5e7bd5adb`.

## Implemented in this patch

- Include VERIFYING in the user-cancellable/download-running states.
- Keep the actions sheet connected to live Room records rather than a stale Parcelable.
- Persist CANCELLED before requesting WorkManager cancellation, scoped by package+version.
- Cancel All targets queued and active app **and** update downloads.
- Guard worker state, file lists, shared-library metadata, and progress updates against
  cancelled records and newer versions for the same package.
- Bind each new worker to an explicit input version, reject mismatched/stale workers.
- Prevent a cancelled request from entering the installer hand-off.
- Fix a startup recovery bug that incorrectly marked running WorkManager jobs FAILED.
- Treat an orphaned processing row as FAILED, freeing the single download slot.
- Use BroadcastReceiver.goAsync() for notification-triggered cancellations.
- Prevent clearing APK files while the installation state is INSTALLING.
- Close icon HTTP responses reliably.

## Important limitations / next R1 phase

- Android PackageInstaller operations that have already been committed are NOT abortable
  by the download cancel operation. No "cancel" action is advertised for INSTALLING.
- This patch does not yet introduce persistent per-request UUIDs, a transfer-speed watchdog,
  pause/resume controls, or network-level OkHttp Call.cancel hooks. These are R1B follow-ups.
- R1A is source-level and Kotlin compile qualified by GitHub Actions after pushing.
  Device acceptance for process death, cancellation in transfer, and microG is still required.
- Legacy WorkManager requests created before this change (without VERSION_CODE input) are
  discarded when they execute; any orphaned row is recovered during the next startup.
- Force Clear All remains explicitly destructive. Avoid it during an active OS-level install.
- A same-version request requeued immediately after cancellation may reuse the same version
  identity. Persistent per-attempt UUIDs will be added in R1B for full generation isolation;
  R1A also checks `isStopped` to mitigate late callbacks after WorkManager cancellation.

## Qualification

1. scripts/ci/check_r1a.py passes (included in foundation workflow).
2. ./gradlew assembleVanillaDebug ktlintCheck testVanillaDebugUnitTest succeeds on Actions.
3. DownloadCancelReceiver actions cancel a running download on Android 12/16.
4. Verification exposes Cancel; installer hand-off is not incorrectly cancelled.
5. Cancel All cancels both app downloads and update downloads.
6. Process-death restart preserves live WorkManager tasks and frees orphaned slots.
7. Re-enqueueing a newer version cannot be overwritten by an older worker.
