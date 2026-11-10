# R3C06 P5 — Manual-only hosted acceptance on existing R1D

**Baseline:** PR #9, R3C06 P4 commit `85840e3460f3372d9a50d1f760895eb6995a0d59`.
The real API36 P4 read-only receipt from workflow 42828215734 measured **51 actual tests in eight suites**. This does not cover actual installation, Play delivery, physical devices or vendor APKM/XAPK files.

## Safe default

The existing `Aurora R1D — API 36 Emulator Download Recovery` workflow remains manual (`workflow_dispatch`) and retains its unchanged read-only 51-case R3C06 P4 gate unless new optional inputs are explicitly set. The ordinary run performs no installer consent automation and no bundletool binary download. It creates no extra emulator build graph. P5 does not change the production installer, Play-evidence store, archive parser or package verifier.

## Explicit modes

- `r3c06_live_install=true`: on the hosted API36 emulator only, generate a new test-signed v2/v3 synthetic `com.aurora.r3c06.fixture` APK, stage and verify via Aurora, exercise actual system denial and acceptance, verify callback/version/signer and remove the fixture. It fails closed if the package is present before the test, installer UI cannot be uniquely identified, any ADB package query fails or cleanup cannot be proved.
- `r3c06_bundletool_matrix=true`: generate a real `vanillaDebug` AAB from Aurora on GitHub, download official `google/bundletool` release **1.18.3**, verify its fixed asset SHA-256 `a099cfa1543f55593bc2ed16a70a7c67fe54b1747bb7301f37fdfd6d91028e29`, then exercise device targeting against the API36 emulator using freshly signed `*.apks`. The production Aurora AAB is **not** guaranteed to contain alternate ABI, density, locale, SDK or on-demand feature variants. This matrix correctly emits `PARTIAL` when the fixture lacks coverage; it **must not** claim full qualification for such a run. No Android install is attempted by the bundletool matrix.
- Both options false (the default): only original R1D and P4 run; no P5 manual PASS receipt is produced.

After successful opted-in execution, `R3C06_P5_MANUAL_RECEIPT.json` binds SHA, run ID, Android API and the two independent test scopes. It has an explicit `PARTIAL` state, and never asserts real-world vendor format compatibility, publisher proof, physical-device testing, a signed release, or Play evidence qualification.

## Manual dispatch examples

Run only OS install/deny acceptance:

```zsh
gh workflow run aurora-r1d-emulator.yml -R Mikeyphw/AuroraStore-Standalone --ref feature/r3c04-c02-c08-import-handoff-archives-20261109 -f r3c06_live_install=true -f r3c06_bundletool_matrix=false
```

Run bundletool coverage probe, only if you want another full hosted R1D execution:

```zsh
gh workflow run aurora-r1d-emulator.yml -R Mikeyphw/AuroraStore-Standalone --ref feature/r3c04-c02-c08-import-handoff-archives-20261109 -f r3c06_live_install=false -f r3c06_bundletool_matrix=true
```

The user decides whether to dispatch either mode. **The overlay launcher never dispatches these workflows.**

## Honest limitations / follow-up

A published workflow is not itself qualification. After manual dispatch, inspect exact-SHA `R3C06_P4_API36_READONLY_RECEIPT.json`, `R3C06_P3_LIVE_OS_INSTALL_RECEIPT.json` when opted and `R3C06_P3_BUNDLETOOL_MATRIX_RECEIPT.json` when opted, plus the new P5 summary. A real dynamic-feature AAB fixture, positive vendor APKM/XAPK samples and separately authorized physical-device tests remain unresolved. R3C07 UX remains the next production-feature roadmap phase.
