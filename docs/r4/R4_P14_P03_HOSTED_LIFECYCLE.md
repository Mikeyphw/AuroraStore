# AuroraStore R4 P14-P03 — hosted-only download/update lifecycle

**Status:** Source overlay prepared; GitHub CI and actual Android instrumentation not tested yet.

**Stacked source:** PR #4 `6e9418baaefadd4afcf4320b4a4b193546e66ec7`, new draft branch `feature/aurora-r4-p14-p03-hosted-lifecycle-20261115`. P14-P01/P02 and P13 limited manual approval must remain unchanged.

This P14-P03 milestone is **hosted-only** on disposable GitHub API36 x86_64, two display sizes and both light/dark themes. No physical ARM64 writes, no Gradle on Termux, no real Play accounts, no installation prompt or APK install.

The suite deliberately tests production Room download/update attempt identity and cancellation, the existing real DownloadWorker with a local loopback test server, and actual production Compose DownloadListItem and DownloadActionsSheet. It adds eight tests for update version supersession, lost-worker recovery and the *simulated* `PackageInstaller.STATUS_FAILURE_ABORTED` **installer decline** outcome through the existing production installer result/recovery policies.

The actual OS user-confirmation dialog is **not tested** in P14-P03: do not interpret decline-policy coverage as proof of an observed end-user click. Full physical behavior will be evaluated at P15 after explicit device-write authorization and readiness review.

CI demands 76 real test executions total: 32 new Room/policy executions, 32 real Compose UI executions, 9 baseline DAO regression executions, and 3 real DownloadWorker offline executions. Twenty actual Android PNGs are required: five true full-display compositor screenshots per full/compact × light/dark profile, with source/run identities, image hashes, dimensions and exact execution logs. On failure, collect partial screenshots and logcat. This is not a release gate.

**P15 remains the next milestone**, unifying the fully qualified P14-P01/P02/P03 functionality on `localhost:5555` (Android 16 / API36 / ARM64) with read-only device preflight, independently authorized device writes, exact-SHA APK provenance, rollback and cleanup. P16 security/signing/release qualification remains deferred.

## HF01 (compiled P14-P03 runtime repair)

The first hosted run (43669701808) passed 8/8 lifecycle cases but failed 3/4
Compose UI cases: the whole-screen screenshot guard wanted 42 visual samples
while isolated real download cards supplied 28–35. HF01 uses the same real
UiAutomation compositor PNGs, excludes system bars, requires at least 12
contrasting app-content samples and 2 KiB of encoded image, plus independent
Compose semantic assertions. It still refuses blank screenshots and retains
all 20 PNG integrity checks. This is *not* a live download or Android installer
prompt test.

The HF01 terminal launcher additionally streams unmodified native `gh run watch`
for both exact-SHA workflows and `gh pr checks` after completion, saving the
workflow output/failure logs and a resume journal. No `gh --json` flags.

## HF02 — correct real AndroidJUnitRunner single-test verdict

Exact failing hosted attempt: [43673400844](https://github.com/Mikeyphw/AuroraStore/actions/runs/43673400844), PR #5 commit `1d7eaa7aea5645975a987eecc3f096cf98cd3b79`.
Both targeted CI and P14-P03 source gates passed. The new eight Room/policy tests,
four UI tests, four Final UI tests and nine DAO regression tests passed on the first
(full/light) profile. The first worker test also reported **`OK (1 test)`** and
`INSTRUMENTATION_CODE: -1`, but the hosted shell runner incorrectly required
`OK (1 tests)` for every `count=1` case. The result was a false refusal, not a
failed worker implementation.

HF02 requires `OK (1 test)` for a single instrumented method and `OK (N tests)`
for N>1, plus a successful Android instrumentation completion code; crash and
failure markers still block success. Source-negative mutations and seven
isolated **executed Bash** exit-gate tests prevent reintroducing this issue.
The production download worker, Room state transitions, P14-P01/P02/P13,
workflow trust permissions and scope of P15 remain unchanged. The HF02 Termux
launcher continues to print the real, unmodified stdout/stderr from `gh run watch`,
`gh pr checks`, and `gh run view --log-failed`, with evidence and durable journals.
**Hosted HF02 has not yet run**; P14-P03 remains unqualified until the exact
source/run-bound 76 tests and 20 screenshots pass GitHub CI.

## HF03 — actual isolated-widget capture plus evidence audit repair

Exact failing GitHub Actions run: 43675171321 at PR #5 HEAD `eadfbc3bb09e7edc3db46e993b8c14258416d246`.
All 76 Android instrumentation executions on full/compact x light/dark were green;
20 PNGs were collected. The final audit rejected a legitimate small queued
component image because the *historical full-screen* `r4_p05_screenshot_audit`
pixel threshold demands 42 changed pixels while the screenshot showed 35 and
15 sampled colors. A visual review of the actual archived PNGs additionally
identified legacy `DownloadFinalUiDeviceTest` images that were blank apart from
Android system bars: merely lowering the audit threshold would be unsafe.

HF03 consolidates all eight actual production Compose UI tests in the P14-P03
instrumentation class. In particular, missing-cache recovery and cancelled
states now use the same bounded UiAutomation full-display PNG capture as the
already passing queued/downloading/failed tests. Each screenshot requires at
least 12 contrasting body samples, 2 KiB, valid dimensions and actual Compose
semantic assertions. Test counts are unchanged: 32 Room+policy, 32 production
Compose, nine baseline DAO, three real loopback DownloadWorker = 76 executions;
20 distinct PNGs are still required for two sizes and two themes. The frozen
older test source is **not** mutated or qualified retroactively.

For those specific isolated component PNGs, HF03 retains the protected R4 P05
stdlib PNG parser's *full decode, chunk CRC and decompression validation*.
Only if that exact parser finishes and rejects at its final 42-sample body
threshold does the P14-P03 wrapper accept the context-specific 12-sample,
8-color nonblank policy. All CRC, malformed PNG, missing file, wrong viewport,
wrong mode, blank, duplicates, and source/run identity failures remain fatal.
The P13 / P14-P01/P02 image gates remain untouched. This does not qualify
physical device installation, live Google Play, personal accounts or release.

The HF03 native terminal launcher preserves actual `gh run watch`, `gh pr checks`,
`gh run view --log-failed`, stored logs and resumable journals with no `--json`.

## Hosted AGP resolution repair after fork restoration (November 17, 2026)

Restored-fork run 43894619025 (source 1ab625ea) stopped during Gradle plugin
resolution, before Android compilation or instrumentation. The error was
`com.android.application:9.4.1` unavailable from plugin repositories, despite
P15 subsequently compiling the same AGP version in run 43894636811.
The P14 workflow now retries only this exact transient lookup failure, at most
three attempts, preserving complete attempt logs. Any unrelated build failure
immediately stops; an exhausted retry remains red. The source gate has new
negative coverage for the retry and non-transient failure safeguards.
All 76 instrumentation cases, 20 screenshots, immutable ancestor pins, read-only
permissions, installer exclusions and device/release nonqualification remain.
This change requires a new exact-HEAD hosted run; old evidence is not regraded.
