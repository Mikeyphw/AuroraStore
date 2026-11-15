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
