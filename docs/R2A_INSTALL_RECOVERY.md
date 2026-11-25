# R2A — installation state recovery

Source pin: `e19b6ad27684e142f185bc514d1ee241f2c0ee68` (`master` after PR #1).

## Behavior

- Never abandon every owned `PackageInstaller` session on application startup: doing so
  could destroy a still-pending Android confirmation after process death.
- On startup, and during orphan-recovery polling, read Android's installed version and
  sessions owned by Aurora to reconcile Room `INSTALLING` / `AWAITING_INSTALL`.
- At startup, also reconcile a download stranded in `COMPLETED` before handoff.
- The Android-installed target version wins over missing callbacks; an outstanding session
  remains `AWAITING_INSTALL`; a vanished session becomes retryable when APKs exist;
  when no target APK, session, or cached APK exists, report `FAILED` rather than `Installing`.
- Recovery writes compare package, version and durable `downloadedAt` attempt, and only
  update installer-stage states. No active download attempt should be replaced.
- Guard empty staging sets, partially failed shared-library staging, session close and
  abandon-on-stage-failure, and duplicate commits while a confirmation is outstanding.

## Intentionally excluded from R2A

- Result callback identity and attempt-order protection (R2B).
- microG/privileged installer outcome compatibility (R2C).
- Hosted true package installation lifecycle and process-death emulator suite (R2D).
- Physical-device qualification and signing: **not qualified**.

## Verification

The overlay's embedded source contract is a local structural check only, not an Android
build. GitHub Foundation CI must pass `check_r2a.py`, `assembleVanillaDebug`, `ktlintCheck`
and `testVanillaDebugUnitTest`. The `InstallRecoveryPolicyTest` JVM matrix runs there.
Do not merge before hosted tests pass.
