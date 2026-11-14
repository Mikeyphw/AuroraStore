# AuroraStore R3D P04 — recovery, callback races, root guards and limited independent signoff

State: **SOURCE IMPLEMENTED, NOT APPLIED, NOT HOSTED OR LIVE QUALIFIED.**

## Production changes

- `ArtifactInstallSession.recordStatus` and `recordPresentationFailure` are individually `@Synchronized` on the existing singleton, serializing callback/user-prompt races *within the application's process*. The existing session ID, attempt generation, OS session identity, allowed transitions and terminal-state veto remain authoritative. Cross-process delivery or an installed OS upgrade is NOT promised; Android is final authority.
- Pending/stale Android outcome receipts explicitly say **UNCONFIRMED** after process restart or an interrupted session. Do not infer an OS success/rejection from an app process exiting. No automatic app rollback, purge, root, or data wipe.
- Four new **non-installing** instrumented tests are appended to the inherited API36 R1D, with an independent source/run-bound receipt in `aurora-r3c03-c02/R3D_P04_READONLY_RACE_DEVICE_RECEIPT.json`. Targeted CI compiles them but does not run emulator tests.

## Explicit live P04 acceptance (only disposable fixture)

`.github/workflows/aurora-r3d-p04-recovery.yml` has `workflow_dispatch` only, default `DO_NOT_RUN`, unique required authorization, fresh emulator, SDK35 build tools, ephemeral signed v1/v2 and intentionally mismatched signed v3 fixtures.

The runner verifies emulator-5554 only, API36, qemu, non-root shell UID2000, ro.secure=1, exact GitHub SHA/run, APK package+hash+signer inventory and **absence of the test package before installing anything**. No `su`, `adb root`, write on another package, `pm clear`, privileged install, or shared user app data operation. An existing test package always forces refusal, not cleanup.

Test operations, if explicitly dispatched:

1. Install fixture v1 and measure private SHA-256 data canary.
2. Populate a partial-install PackageInstaller shell session, abandon it, verify original v1/data. Abandon errors veto qualification.
3. Populate a full session, force-stop the disposable app process, abandon session from a separate command, verify v1/data.
4. Upgrade to v2 and force-stop/restart its app process; measure persisted data canary.
5. Require Android to reject a different signing identity and an unapproved downgrade, preserving v2/data.
6. **Test-only** `adb install -r -d` to v1 on a debuggable temporary app, verify data, re-upgrade v2, verify it again. If OS refuses, report PARTIAL and never claim a pass. This is **not Android RollbackManager**, and does not validate a production app downgrade.
7. Only when test package was proven absent before the run, remove it and confirm absence. Any cleanup failure overrides apparent success.

An independent source/run-bound P04 signoff validates exact steps, signed-fixture manifest, private canary digest, absence after cleanup, and all negative scope flags. It can only return `LIMITED_DISPOSABLE_OS_RECOVERY_PASS_MANUAL_SIGNOFF_PENDING`, not final release/security signoff. Test results from any other SHA/run are ineligible.

## Qualification that remains explicitly NOT done

- Actual AuroraStore production SAF → Android PackageInstaller confirmation UI DENY/ACCEPT, post-commit pending-user-action race and system callback actual delivery (simulated policy tests do not prove OS delivery), actual Android RollbackManager capability, arbitrary app data backups or preservation, real user's installed applications, physical ARM64, privileged/root path, Android 17 compatibility, release signing.
- Legacy R3C08 P05 independent read-only signoff for the original parent SHA does not transfer to a newly committed R3D SHA. New exact-SHA independent signoff and manual approval remain required.

## Commands **after applying the consolidated ZIP**, completing new-SHA targeted 3/3 and inherited R1D

```zsh
# Manual opt-in ONLY; this modifies a newly created disposable hosted emulator.
gh workflow run aurora-r3d-p04-recovery.yml \
  -R Mikeyphw/AuroraStore-Standalone \
  --ref feature/r3c04-c02-c08-import-handoff-archives-20261109 \
  -f authorization=I_AUTHORIZE_R3D_P04_DISPOSABLE_API36_RECOVERY

gh run list -R Mikeyphw/AuroraStore-Standalone \
  --workflow aurora-r3d-p04-recovery.yml --limit 10
```

**No automatic live workflow dispatch by the overlay.** The pending source ZIP itself never installs anything.

## HF01 source audit — material repairs

The previous P04 signoff accepted an internally consistent result JSON without validating actual Android command outputs. That is no longer eligible for a limited signoff. The manual workflow now uploads a distinct `R3D_P04_AS_RUN_ADB_TRANSCRIPT.json`, generated from unprivileged ADB responses and SHA-256 bound into its session receipt. The independent checker verifies source SHA/run/serial, exactly one emulator, API36/qemu/UID2000/secure properties, ordered signed APK installation and expected OS refusal outcomes, two separately created/written/abandoned sessions (one partial and one full), eight post-transition private-data reads with matching SHA-256, final test package absence from Android package inventory, and test-owned temp absence. It refuses wrong session IDs, missing/reordered commands, fake cleanup and absent/modified logs. The raw test canary secret is redacted from command arguments.

No independent OS cryptographic attestation is implied: the transcript and receipt come from the same hosted runner. The result remains `LIMITED_DISPOSABLE_OS_RECOVERY_PASS_MANUAL_SIGNOFF_PENDING`; new exact-SHA P05 independent security signoff, Aurora's own live PackageInstaller confirmation UI, actual RollbackManager, and physical ARM64 acceptance remain pending.

Emergency cleanup attempts independent owned-session abandonment AND temporary-file deletion even when either fails. Neither P03 nor P04 can report PASS with a known orphaned test session or leftover device temp. The fixture builder independently revalidates the signed APK certificate/manifest directly before running.

## HF01 source audit — material repairs

The previous P04 signoff accepted an internally consistent result JSON without validating actual Android command outputs. That is no longer eligible for a limited signoff. The manual workflow now uploads a distinct `R3D_P04_AS_RUN_ADB_TRANSCRIPT.json`, generated from unprivileged ADB responses and SHA-256 bound into its session receipt. The independent checker verifies source SHA/run/serial, exactly one emulator, API36/qemu/UID2000/secure properties, ordered signed APK installation and expected OS refusal outcomes, two separately created/written/abandoned sessions (one partial and one full), eight post-transition private-data reads with matching SHA-256, final test package absence from Android package inventory, and test-owned temp absence. It refuses wrong session IDs, missing/reordered commands, fake cleanup and absent/modified logs. The raw test canary secret is redacted from command arguments.

No independent OS cryptographic attestation is implied: the transcript and receipt come from the same hosted runner. The result remains `LIMITED_DISPOSABLE_OS_RECOVERY_PASS_MANUAL_SIGNOFF_PENDING`; new exact-SHA P05 independent security signoff, Aurora's own live PackageInstaller confirmation UI, actual RollbackManager, and physical ARM64 acceptance remain pending.

Emergency cleanup attempts independent owned-session abandonment AND temporary-file deletion even when either fails. Neither P03 nor P04 can report PASS with a known orphaned test session or leftover device temp. The fixture builder independently revalidates the signed APK certificate/manifest directly before running.

## HF01 source audit — material repairs

The previous P04 signoff accepted an internally consistent result JSON without validating actual Android command outputs. That is no longer eligible for a limited signoff. The manual workflow now uploads a distinct `R3D_P04_AS_RUN_ADB_TRANSCRIPT.json`, generated from unprivileged ADB responses and SHA-256 bound into its session receipt. The independent checker verifies source SHA/run/serial, exactly one emulator, API36/qemu/UID2000/secure properties, ordered signed APK installation and expected OS refusal outcomes, two separately created/written/abandoned sessions (one partial and one full), eight post-transition private-data reads with matching SHA-256, final test package absence from Android package inventory, and test-owned temp absence. It refuses wrong session IDs, missing/reordered commands, fake cleanup and absent/modified logs. The raw test canary secret is redacted from command arguments.

No independent OS cryptographic attestation is implied: the transcript and receipt come from the same hosted runner. The result remains `LIMITED_DISPOSABLE_OS_RECOVERY_PASS_MANUAL_SIGNOFF_PENDING`; new exact-SHA P05 independent security signoff, Aurora's own live PackageInstaller confirmation UI, actual RollbackManager, and physical ARM64 acceptance remain pending.

Emergency cleanup attempts independent owned-session abandonment AND temporary-file deletion even when either fails. Neither P03 nor P04 can report PASS with a known orphaned test session or leftover device temp. The fixture builder independently revalidates the signed APK certificate/manifest directly before running.

## HF01 source audit — material repairs

The previous P04 signoff accepted an internally consistent result JSON without validating actual Android command outputs. That is no longer eligible for a limited signoff. The manual workflow now uploads a distinct `R3D_P04_AS_RUN_ADB_TRANSCRIPT.json`, generated from unprivileged ADB responses and SHA-256 bound into its session receipt. The independent checker verifies source SHA/run/serial, exactly one emulator, API36/qemu/UID2000/secure properties, ordered signed APK installation and expected OS refusal outcomes, two separately created/written/abandoned sessions (one partial and one full), eight post-transition private-data reads with matching SHA-256, final test package absence from Android package inventory, and test-owned temp absence. It refuses wrong session IDs, missing/reordered commands, fake cleanup and absent/modified logs. The raw test canary secret is redacted from command arguments.

No independent OS cryptographic attestation is implied: the transcript and receipt come from the same hosted runner. The result remains `LIMITED_DISPOSABLE_OS_RECOVERY_PASS_MANUAL_SIGNOFF_PENDING`; new exact-SHA P05 independent security signoff, Aurora's own live PackageInstaller confirmation UI, actual RollbackManager, and physical ARM64 acceptance remain pending.

Emergency cleanup attempts independent owned-session abandonment AND temporary-file deletion even when either fails. Neither P03 nor P04 can report PASS with a known orphaned test session or leftover device temp. The fixture builder independently revalidates the signed APK certificate/manifest directly before running.

## HF01 source audit — material repairs

The previous P04 signoff accepted an internally consistent result JSON without validating actual Android command outputs. That is no longer eligible for a limited signoff. The manual workflow now uploads a distinct `R3D_P04_AS_RUN_ADB_TRANSCRIPT.json`, generated from unprivileged ADB responses and SHA-256 bound into its session receipt. The independent checker verifies source SHA/run/serial, exactly one emulator, API36/qemu/UID2000/secure properties, ordered signed APK installation and expected OS refusal outcomes, two separately created/written/abandoned sessions (one partial and one full), eight post-transition private-data reads with matching SHA-256, final test package absence from Android package inventory, and test-owned temp absence. It refuses wrong session IDs, missing/reordered commands, fake cleanup and absent/modified logs. The raw test canary secret is redacted from command arguments.

No independent OS cryptographic attestation is implied: the transcript and receipt come from the same hosted runner. The result remains `LIMITED_DISPOSABLE_OS_RECOVERY_PASS_MANUAL_SIGNOFF_PENDING`; new exact-SHA P05 independent security signoff, Aurora's own live PackageInstaller confirmation UI, actual RollbackManager, and physical ARM64 acceptance remain pending.

Emergency cleanup attempts independent owned-session abandonment AND temporary-file deletion even when either fails. Neither P03 nor P04 can report PASS with a known orphaned test session or leftover device temp. The fixture builder independently revalidates the signed APK certificate/manifest directly before running.
