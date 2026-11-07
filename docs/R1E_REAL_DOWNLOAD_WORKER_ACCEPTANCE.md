# R1E — Real DownloadWorker offline qualification

Base commit: `9aa7fdfbdcd003276dd164c36422849d236edfbb` (R1D2 merged).

This consolidated milestone runs the actual Hilt-created `DownloadWorker` (`CoroutineWorker.doWork`) with the production streaming, Room and retry code against a local HTTP server in Android instrumented tests. It does NOT substitute a small fake worker for the production implementation.

## Safeguards

- Offline fixture mode is compiled behind `BuildConfig.DEBUG`, requires an exact synthetic `com.aurora.r1e.fixture.*` package, `127.0.0.1` HTTP endpoint, tiny capped input, and SHA-256 digest.
- No Google accounts, Play tokens, external network, root access, remote delivery, APK package installer or release publishing are used.
- The user-visible notifications and installer handoff are skipped **only** for the enabled test fixture; the real app code path is unchanged.
- A new generation gets a separate cache file; obsolete workers skip `AuthWorker.doWork()` entirely and cannot touch newer attempts.
- Truncated HTTP bodies are treated as transient IO failures (bounded WorkManager retry policy in the production path is unchanged).

## Hosted qualification

The existing pinned API 36/x86_64 Google APIs emulator runs its 24 R1D/R1D2 tests, then eight R1E tests against the actual Hilt-created worker:

1. Offline HTTP 200 transfer and SHA-256 verification, without package installation.
2. Interrupted 200 response leaves partial bytes; the next worker invocation sends Range and resumes exactly.
3. Mismatched 206 `Content-Range` destroys the partial file and retries.
4. HTTP 416 destroys a stale partial file and retries.
5. SHA-256 mismatch fails and discards the downloaded payload.
6. Obsolete attempt has no network activity or database mutation.
7. Cancelled generation is not resurrected or downloaded.
8. Non-loopback test endpoint is rejected before network activity.

The test uses `TestListenableWorkerBuilder` + injected `HiltWorkerFactory`: this executes real `DownloadWorker.doWork()` but is not an assertion that the production Worker is itself scheduled by WorkManager in these eight tests. Existing WorkManager scheduling/force-stop tests remain in R1D2.

The R1E evidence receipt stays `NOT_RUN` unless all 32 tests pass. Physical-device testing, Play-delivery acceptance, a real package installation and release signing remain future gates. Do not call this release qualification.
