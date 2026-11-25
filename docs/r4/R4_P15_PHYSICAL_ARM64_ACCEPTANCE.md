# AuroraStore R4 — P15 consolidated physical ARM64 acceptance

Status: **source overlay prepared; no physical device run and no installed APK proven yet**.

Stacked on the fully hosted-qualified P14-P03 PR #5 (`1ab625ea916de533de4bbc9db8703aafc23f691b`), which itself follows P14-P01/P02 PR #4 (`6e9418baaefadd4afcf4320b4a4b193546e66ec7`) and the limited P13 approval. P15 is never release qualification.

## Two independent gates

**Gate A — GitHub hosted provenance:** Only GitHub Actions runs Gradle, compiles vanilla-debug and AndroidTest APKs, verifies package identities and real APK signing fingerprints, hashes both APKs and uploads an exact-source/run-attributed artifact. This workflow runs no emulator and no physical device. Never regard source-only PASS as evidence of a built APK.

**Gate B — physical API36 ARM64:** A read-only preflight is available without authorization. `localhost:5555` must resolve to one boot-complete, physical `arm64-v8a` API36 target. A preexisting Aurora debug app or test package causes refusal; no overwrite, clear-data, root, ADB shell install, display overrides, locale/theme changes, Wi-Fi configuration, live Play access, or other app installation. The separate `--run` requires `I_AUTHORIZE_P15_TEST_APK_INSTALLS` and a verified downloaded Gate A artifact. It installs only P15's new debug/test APKs and uninstalls only these test-owned packages in `finally`; `--cleanup` provides rollback for interrupted ownership journals and refuses deletion of preexisting packages.

### Consolidated P14 parity (physical)

Run production Navigation3/Search/Details (4), actual Room update/cancel/recovery policies (8), real Compose download-state UI (8), production DownloadDao regression (9), and three named offline DownloadWorker/loopback cases: **32 Android test executions**. Capture and structurally decode **15 full-display PNGs** (10 navigation/catalog, 5 download widgets), reject blank or identical frames, validate exact source/run and the APK pair. Keep bounded instrumentation logs, screenshot SHA-256, explicit cleanup result, and an atomic local journal; read-only preflight writes no device state.

### Explicit exclusions and manual installer gate

The P14-P03 installer-decline outcome was a simulated production callback policy; it is **not** a real user declining an Android installation prompt. P15 automated parity likewise **does not** perform a real package update/install flow, click the OS confirmation, access a Play account, or prove physical production download against Google servers. `real_installer_prompt_decline_qualified=false` remains in evidence. A separate manually supervised, disposable signed-fixture prompt trial and cleanup proof are still required before declaring *full P15* qualified. Even a physical parity PASS is **not** P16 release/signing qualification.

## Operator commands (Termux Zsh)

After the P15 overlay is applied/pushed and hosted build CI is GREEN, the ZIP launcher can fetch the exact source SHA/run artifact. The only read-only device command is:

```zsh
python3 /sdcard/Download/Aurora_P15_CONSOLIDATED.zip --physical-preflight
```

To run P14 parity on the physical device, explicitly authorize new test APK installation **after verifying** the read-only report and the download artifact:

```zsh
python3 /sdcard/Download/Aurora_P15_CONSOLIDATED.zip --physical-run \
  --authorize I_AUTHORIZE_P15_TEST_APK_INSTALLS \
  --artifact-dir /sdcard/Download/AuroraStore-P15/apks \
  --physical-output /sdcard/Download/AuroraStore-P15/physical
```

If interrupted after installing test-owned APKs:

```zsh
python3 /sdcard/Download/Aurora_P15_CONSOLIDATED.zip --physical-cleanup \
  --physical-output /sdcard/Download/AuroraStore-P15/physical
```

Never use `adb uninstall` on a user's preexisting Aurora installation. Physical tests are independently authorized and never triggered by `--apply-and-push --watch`, `--check`, or `--fetch-apks`.

## Scope / stop conditions

The P15 runner can fail on a real device due to OS policy, insets, test-only Hilt state, or screenshot differences. It must preserve failures, refuse a green receipt, and attempt cleanup; never relax test or safety gates to manufacture qualification. Preflight cannot guarantee a device's installed package is not replaced concurrently by unrelated software. In a crash, `--cleanup` uses the verified ownership journal and remains fail-closed if identity cannot be proven.

## P15 HF01 — robust signed APK package-ID attestation

The first hosted P15 compile (run 43776123080, source d7009e4f) completed both Gradle
APK builds but stopped in the artifact manifest builder with
`P15_ARTIFACT_REFUSED_NO_APK_BADGING`. The original parser incorrectly made
package identification depend on a populated numeric `versionCode` field in
`aapt dump badging`; AndroidTest metadata can have an empty versionCode.

HF01 takes the exact app/test package identities from the documented
`aapt2 dump packagename` command and optionally cross-checks the legacy
`aapt dump badging` name without assuming versionCode. It rejects missing,
malformed, multi-line, mismatched or swapped package identities and still
requires both APK signatures and SHA-256 hashes before publishing the manifest.
Tests run with mocked Android tool stdout, including a blank versionCode.
No APK installation or physical ARM64 operation is part of this fix.

## P15 HF02 — Android Build Tools 37 certificate labels

Run `43778003268` compiled both APKs and verified the app/test package IDs,
then failed `P15_ARTIFACT_REFUSED_UNSIGNED_OR_UNRECOGNIZED_SIGNER_app-vanilla-debug.apk`.
The legacy parser only accepted `Signer #1 certificate SHA-256 digest:`.
Android Build Tools 37 may instead produce `V2 Signer:` and `V3.0 Signer:`
certificate lines. This is an output-format mismatch, not evidence that
signing verification failed. HF02 explicitly requires apksigner's successful
verification exit, parses known legacy/V2/V3 certificate SHA-256 formats,
requires a 64-character hex digest, and refuses conflicting certificate
identities across schemes. It never accepts a public-key fingerprint in place
of a certificate digest. Local regressions cover valid legacy/current labels,
missing/short/mismatched fingerprints, and reported verification failures.
Hosted provenance remains pending until a new exact-source Actions run passes.
There are no local Gradle or physical-device operations in this repair.
