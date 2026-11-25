# Aurora R3D P03 — disposable real Android upgrade/downgrade acceptance

Status of this source package: **IMPLEMENTED; LIVE DEVICE TESTS NOT RUN / NOT QUALIFIED**.
The P01+P02 overlay was not applied when P03 was folded in. Nothing here
establishes completed Android installations or storage preservation on a real device.

## Security boundaries

- Only manually dispatched `.github/workflows/aurora-r3d-p03-disposable.yml` permits live runs.
- The `authorization` input must equal `I_AUTHORIZE_DISPOSABLE_API36_EMULATOR_INSTALLS`; default is `DO_NOT_RUN`.
- A brand-new API36 x86_64 emulator is required (`ro.kernel.qemu=1`, only `emulator-5554` online).
- Only one hardcoded package: `com.aurora.r3d.fixture.history`. Abort before any writes if it already exists.
- Three temporary APKs: v1 and v2 share a new ephemeral RSA test signing key; v3 has a deliberately different ephemeral key for mismatch refusal. Each APK's exact package, version code and signature are inspected by Android SDK tools; its hash/cert are sealed into `fixtures.json`.
- These APKs are `android:debuggable=true` only to allow a disposable Android `adb install -r -d` test where supported. Not a bypass in AuroraStore or permission to downgrade real apps.
- No root, no inherited signatures, no device wipe, no uninstall of existing packages, no user-specific app testing, no Play evidence, no automatic backup claim.

## Measured sequence when explicitly authorized

1. Verify clean emulator, signed APK identities and test-package absence.
2. Install signed v1, write a random test-only SharedPreferences canary, read back SHA-256.
3. Create an Android shell-owned session, stream the **signed v2** APK bytes, **abandon** the populated session; verify v1 and canary remain.
4. Upgrade to signed v2; verify installed version and same private canary SHA-256.
5. Attempt to replace v2 with wrong-key signed v3; require OS signature failure and intact v2/data.
6. Attempt v2→v1 without downgrade permission; require Android version downgrade refusal and intact v2/data.
7. Attempt v2→v1 with **test-only** `adb install -r -d` on debuggable fixture. If Android permits: require v1 and canary, then re-upgrade v2 with same canary. If Android refuses: record `PARTIAL_OS_REJECTED_DOWNGRADE`, never claim success.
8. Uninstall the fixture **only if the test itself installed it**, verify absence; cleanup failure always overrides any apparent pass.

## Evidence

`R3D_P03_ACTUAL_DISPOSABLE_RECEIPT.json` is generated only by an actual explicitly opted-in hosted run. Its SHA/run ID, APK hashes, signing cert hashes, status transitions, tested scope, and cleanup state are recorded. No receipt is fabricated by the ZIP builder. Source-only negative tests are run on CI automatically, with **no** Android installation.

`PASS_DISPOSABLE_OS_ONLY` proves only this emulator, disposable fixture and test-owned data transitions. It **does not prove** AuroraStore's SAF UI/PackageInstaller transaction pathway, arbitrary user app data retention, manual UI denial, cancellation after commit, real-world downgrade compatibility, physical ARM64, app backup, or release qualification. These remain P04/manual gates.

## Manual workflow dispatch, after P01+P02+P03 source qualifies

```zsh
# Explicitly opted in, source branch pinned. No local Gradle.
gh workflow run aurora-r3d-p03-disposable.yml -R Mikeyphw/AuroraStore-Standalone \
  --ref feature/r3c04-c02-c08-import-handoff-archives-20261109 \
  -f authorization=I_AUTHORIZE_DISPOSABLE_API36_EMULATOR_INSTALLS

# Inspect the exact branch SHA and action runs before claiming qualification.
gh run list -R Mikeyphw/AuroraStore-Standalone \
  --workflow aurora-r3d-p03-disposable.yml --limit 10
```

Do not dispatch until targeted CI 3/3 and inherited non-installing API36 R1D pass on the new exact overlay commit. No live test is automatically dispatched by the launcher.

## HF01 audit correction

Real fixture verification now reruns `apksigner verify --print-certs` and `aapt2 dump badging` against each APK immediately before the hosted device test. The P03 shell session-cancellation cleanup tries both session abandonment and temporary-file deletion independently even if one fails; absence of the test-owned temp path is verified. An abandoned session or undeleted temporary file refuses acceptance. All live execution remains independently authorized on a clean API36 emulator.

## HF01 audit correction

Real fixture verification now reruns `apksigner verify --print-certs` and `aapt2 dump badging` against each APK immediately before the hosted device test. The P03 shell session-cancellation cleanup tries both session abandonment and temporary-file deletion independently even if one fails; absence of the test-owned temp path is verified. An abandoned session or undeleted temporary file refuses acceptance. All live execution remains independently authorized on a clean API36 emulator.

## HF01 audit correction

Real fixture verification now reruns `apksigner verify --print-certs` and `aapt2 dump badging` against each APK immediately before the hosted device test. The P03 shell session-cancellation cleanup tries both session abandonment and temporary-file deletion independently even if one fails; absence of the test-owned temp path is verified. An abandoned session or undeleted temporary file refuses acceptance. All live execution remains independently authorized on a clean API36 emulator.

## HF01 audit correction

Real fixture verification now reruns `apksigner verify --print-certs` and `aapt2 dump badging` against each APK immediately before the hosted device test. The P03 shell session-cancellation cleanup tries both session abandonment and temporary-file deletion independently even if one fails; absence of the test-owned temp path is verified. An abandoned session or undeleted temporary file refuses acceptance. All live execution remains independently authorized on a clean API36 emulator.

## HF01 audit correction

Real fixture verification now reruns `apksigner verify --print-certs` and `aapt2 dump badging` against each APK immediately before the hosted device test. The P03 shell session-cancellation cleanup tries both session abandonment and temporary-file deletion independently even if one fails; absence of the test-owned temp path is verified. An abandoned session or undeleted temporary file refuses acceptance. All live execution remains independently authorized on a clean API36 emulator.
