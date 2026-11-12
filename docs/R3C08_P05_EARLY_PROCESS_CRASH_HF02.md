# R3C08 P05 HF02 — AndroidJUnitRunner early process crash handling

Source baseline: PR #9 `8756b1da20decad43397f4ed014b2e14d7f30a6b`.

## Observed run

In GitHub Actions run `43155498474`, targeted CI succeeded, R3C08 P01
completed its three real API36 tests and produced a signed receipt, but the
P02–P04 instrumentation process reported `Process crashed` in the first
`p02_remoteProviderDeathRefusesImportAndRestartsInNewProcess` test. No test
completed. The uploaded crash buffer lacked a Java exception stack.
The previous commit had passed all 21 P02–P04 tests with identical test/provider
source, so the cause is not established as a production importer regression.

## Strict remediation

* Start test APK and target from a stable stopped state, then clear logcat.
* Allow a single retry **only** for the exact unqualified zero-completion
  AndroidJUnitRunner process-crash terminal in the first provider-death case.
* Save first-attempt instrumentation and main/system/crash process diagnostics
  as separate non-qualifying evidence, never joining them to a PASS log.
* Force-stop both debug and debug.test packages, wait for process teardown,
  clear logcat and rerun all 21 selected methods from the beginning.
* Reject assertion failures, failed tests, partial test counts, duplicated
  terminals, later process crashes, repeated crashes and package mutations.
* Require final-attempt `OK (21 tests)`, `INSTRUMENTATION_CODE: -1`, unchanged
  package inventory and true independent provider START→KILL→START PID events.
* Rebuild the existing SHA/run-bound P02–P04 and P05 signoff receipts only
  from the final successful actual run; otherwise refuse.

No installer writes, privileged installation, Play evidence or physical-device
qualification are added. P05 full signoff remains manual-pending.
