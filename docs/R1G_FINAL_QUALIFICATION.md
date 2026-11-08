# R1G — Download reliability acceptance boundary

R1G is source-pinned to the R1F merge commit and retains the previous R0–R1F CI contracts and the exact API36 emulator runner entry point.

## Automated, hosted qualification (only after a successful PR run)

- Foundation CI runs every R0–R1G source-contract gate, ktlint, JVM tests and the vanilla debug build. It also compiles an **unsigned** vanilla release candidate as a separate job and uploads a source-bound SHA-256 manifest; no release signing or publishing.
- The existing Android 16 emulator runs the full 36 historical device tests plus four new Compose cases: cancel during VERIFYING, missing-cache retry instead of install, no cancel/retry while INSTALLING, and CANCELLED status without fabricated network stats.
- The final emulator evidence gate rejects missing/mismatched per-phase receipts and fewer than **40 real Android device tests**. It verifies five non-empty PNG captures with PNG chunk CRCs and records SHA-256, dimensions, commit and GitHub run ID.
- **Only** if all checks succeed is `R1G_QUALIFICATION_RECEIPT.json` written with `overall=PASS`. It explicitly records `physical_device_qualified=false`, `release_qualified=false`, `actual_google_play_delivery_qualified=false`, and `actual_package_installation_qualified=false`.
- The production UI now re-reads Room before Install and Export, rejecting the stale selected version/attempt rather than acting on an out-of-date UI snapshot. Cancel/Retry/Clear remain attempt-scoped.

## Physical device: pending and separately gated

After installing a debug APK **from the exact GitHub commit** onto a real, authorized Android device, run:

```zsh
bash scripts/ci/r1g_physical_device.sh localhost:5555 "$(git rev-parse HEAD)"
```

This script deliberately does not install an APK or perform any Play download. It refuses emulators, verifies a debuggable package is already installed, starts the app, captures a PNG, and produces **PENDING_MANUAL**, not PASS. The declared SHA is NOT verified against the installed binary. A physical/manual acceptance is not complete until the tester confirms and records all of the following in their own evidence and signs off:

1. Correct debug APK identity/digest and source commit mapped to the installed APK.
2. Normal user login (account handling and consent), network download and visible progress using a legitimate test app.
3. Cancellation while DOWNLOADING and while VERIFYING; no unwanted installation afterward.
4. Interruption/disconnection, reconnection and retry without corrupt APKs or stale progress.
5. App process death/force-stop and reopening; Room/WorkManager recovery, no duplicate attempt.
6. Successful package installation handoff with Android's user confirmation where required, correct installed version, and no unsafe automatic install.
7. Export and retry of downloaded files, including files removed from the cache, and stale-action protection.

If any one is absent or fails, mark physical acceptance **NOT QUALIFIED**. Privacy: inspect and redact screen captures or logs before sharing, since app/account details can be visible.

## Release boundary

The hosted release-candidate job compiles with release build settings but does **not** inject signing keys. An unsigned candidate **is not release-qualified**. Signed build reproducibility, signing identity, real-device installation, Google Play delivery and package-manager handoff remain blocked until separately verified. No workflow uploads a release or signs an artifact.
