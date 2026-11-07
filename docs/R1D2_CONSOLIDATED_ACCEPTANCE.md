# R1D2 — Consolidated offline HTTP and WorkManager acceptance

Base: AuroraStore R1D merge `78c205152e081798c0a9174f14777429416007e3`.

The production `DownloadWorker` uses `ResumeRangePolicy` to validate the complete HTTP
Content-Range (start, end, total), including a zero-offset 206 response, before accepting
partial bytes. HTTP 416 resets an obsolete .tmp file for a bounded retry.

Five JVM tests cover valid/invalid range behavior. Six Android API36 emulator tests
exercise a local in-process HTTP server and real OkHttp: good 206, ignored Range 200,
wrong offsets, impossible bounds, 416 and cancellation while waiting for body data.
Four more emulator tests use Android's real WorkManager to prove old/new attempt
cancellation isolation, actual execution of an offline debug Worker and persistence
of scheduled work across a forced app process restart.

The existing **R1D 14-test suite runs first**. The extended emulator workflow must
run all 24 tests and produce an R1D2 PASS receipt after the last process restart.
It uses Cinderbox Companion's already proven GitHub-hosted API 36 / x86_64 / KVM
configuration; no local Gradle builds and no new parallel emulator workflows.

The test server permits cleartext only for localhost/127.0.0.1 via **debug-only**
network security configuration; no production/release network policy changes.

**Limitations:** these tests are not Google Play delivery tests. The live production
DownloadWorker, real Play download, APK install, physical device, release signing,
and end-to-end live network interruption remain unqualified. Do not claim a release
or real-device acceptance from this suite alone.
