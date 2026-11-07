# R1D — Hosted Android emulator acceptance

Base: `Mikeyphw/AuroraStore` at `dd8f0188705ae1115f080c74d9daff4c574ff967`.

## Actual device evidence

This phase uses Cinderbox-Companion's proven GitHub-hosted emulator configuration:
Ubuntu 24.04, KVM, Google APIs API 36, x86_64, Pixel 6, 2 cores and 2 GiB RAM,
with the exact pinned ReactiveCircus action. Aurora retains Java 21 and the
Android **37.0** build platform because its own AGP/compileSdk need them.

The workflow compiles **both** the vanillaDebug application APK and the
vanillaDebug AndroidTest APK with Gradle on GitHub Actions only. It installs
both into a disposable emulator and runs the project's existing Hilt
AndroidJUnitRunner. It refuses to report success unless all expected tests
actually execute.

## Tests and scope

* 9 Android instrumentation cases use Aurora's **production Room DAO**, in an
  isolated in-memory database, to verify cancellation during downloading and
  verification, same-version retries, attempt isolation, stale notifications'
  DAO safeguards, obsolete versions, orphaned processing state, installer
  handoff, obsolete clear actions, and terminal-state preservation.
* 3 device tests exercise the **production TransferStallWatchdog** using an
  injected deterministic clock.
* 2 separately executed Android instrumentation cases write a persisted Room
  row, actually force-stop Aurora's app process, then reopen the persisted
  database in the next process and apply the exact-attempt orphan recovery
  compare-and-swap.

No Google account, anonymous Play token or third-party APK is needed. These
are not live Google Play delivery tests; no real DownloadWorker transfer is
performed, and neither a physical device nor release signing is qualified.

Future acceptance: an isolated test HTTP server/fault injector around actual
DownloadWorker transfers, WorkManager process-death/retry scheduling, and
Android 16 device hardware/UI tests. Those are deliberately not claimed here.
