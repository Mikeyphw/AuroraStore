# AuroraStore — R3C08 P05 adversarial security signoff protocol

## Exact evidence and fail-closed outcome

R3C08 P05 runs in the **existing** read-only API 36 R1D workflow, immediately
**after** P01 and P02–P04 device instrumentation. It independently reconstructs
R3C08 P01 (3 methods), R3C08 P02–P04 (21 methods), R3C07 P03B (5 methods +
3 SHA-256 checked screenshots), R3C07 P02B (5 methods, verified START/FINISH), R3C06 P4 (51 methods
with verified START/FINISH events across all eight uploaded source-hashed logs), and the signed APK pair's exact targeted CI run.

The P02 provider trace accepts actual repeated `START → KILL → START` cycles,
never same-PID resurrection or unmatched kills. Every accepted trace is bound
to the Git SHA and GitHub Actions run and the unchanged package inventory.

The output `R3C08_P05_API36_SECURITY_SIGNOFF.json` is sealed **only** after the
full device suite passes, with outcome `READ_ONLY_QUALIFIED_MANUAL_PENDING`.
This is **not PASS_FINAL**. The record explicitly sets
`final_security_signoff=false`, `release_qualified=false`,
`physical_device_qualified=false` and `actual_installer_rollback_qualified=false`.
A command with `--final` refuses by design instead of approving absent evidence.

## Manual acceptance still required for a genuine final security signoff

- Actual isolated Android PackageInstaller **DENY → ACCEPT** acceptance,
  cleanup and state restoration, using the existing explicitly opted-in
  R3C07 P04 live fixture—not the default read-only workflow.
- Real **rollback and application-data retention** with independently verified
  package versions/signers and a non-destructive isolated fixture; previous
  read-only policy assertions or an uninstall are insufficient proof.
- Concurrent, stale and replayed **real OS callbacks** with generation/session
  binding and final terminal state, not just pure state-machine unit tests.
- Provider-process failure and restart across a broader **third-party provider**
  matrix, with actual denial, permission and private-file cleanup receipts.
- Physical Android 16 device acceptance, repeatability and explicit release
  gates, each source/run/device-bound. No installation on the user's device is
  performed by this default workflow.

Until these proofs are implemented, executed and independently checked, P05
**must not** become a final PASS. This archive implements the read-only
cryptographically-bound signoff boundary and deliberately blocks premature
release qualification. It does not opt in to OS installs or rollback tests.

## No platform/Play overclaim

User-provided APKs, GitHub/browser handoffs and local file receipts cannot
be promoted to independently authenticated publisher or Google Play proof.
An isolated test-only provider restart cannot qualify arbitrary Android
content providers. A passed 21-test read-only suite is not evidence of live
PackageInstaller approval or data restoration.

## P05 hardened evidence audit

The independent verifier refuses synthetic or truncated inherited AndroidJUnitRunner
logs even if an attacker modifies the matching JSON receipt and recalculates
its SHA-256. A test must have exact START/FINISH markers, a success terminal
and an exact JUnit test-count result. It also refuses existing or symlinked
output paths rather than overwriting as-run evidence. The tests are run on
real historical evidence as an **offline replay**, not new device qualification.
