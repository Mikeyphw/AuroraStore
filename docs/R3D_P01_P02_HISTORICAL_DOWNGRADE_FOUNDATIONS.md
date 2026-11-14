# R3D P01 + P02 — Historical-version references and safe downgrade review

**Scope**: read-only historical candidate and downgrade decision foundations. GitHub-hosted build and JVM tests, no automatic historical-provider API, no root, no APK installation in these tests. Extends the R3C08 verified-file pipeline; does not replace it.

## P01 — historical-version references

- Existing Settings import UI accepts an **optional exact version code** and manually opens provider pages through external browser routing. The enhanced UI adds an optional expected package ID, a button to record manually observed package/version/source references, and an ephemeral list of at most 64 unverified candidates. Same-version duplicate/competing source and cross-package references are rejected; nothing is auto-discovered, downloaded or persisted. The app does not claim any historical version is available on those sites.
- `ArtifactHistoricalVersionPolicy` parses strict decimal version codes and package IDs, rejects unsafe raw source labels, and sorts comparison-only manual references. None is authenticated release/publisher/Play evidence.
- Once the user selects a SAF document, only the signed manifest package/version verified by the production APK verifier can satisfy the optional requested package/version. A mismatch disables installation consent AND aborts the install handler if called despite the disabled button. Editing the reference invalidates previous import, stream lease and approvals.
- The worker reads minSdk from the independently verified staged base APK via PackageManager and checks the already verified split ABI against this device. The read-only report labels `INCOMPATIBLE`, `UNKNOWN`, or a **limited preflight pass, NOT installability**. A known incompatibility blocks consent and install dispatch. Missing SDK information stays UNKNOWN and does not become evidence of compatibility. Android remains authoritative.
- No scraping, provider version APIs, automatic APK selection, unverified URL persistence, cached grant, background download or privileged path. No APK parsing on the UI thread.

## P02 — downgrade safety

- `ArtifactDowngradeSafetyPolicy` compares the verified APK version to the current installed version and requires positively verified **active installed signing identity**. Historical signing-certificate presence alone is not permission to overwrite an app.
- Shared decision logic now enforces **TWO independent, default-off downgrade gates**: (1) approval to request the older version, and (2) acknowledgment of backup/data-loss risks. Both are rechecked by the installer entry point, not just the disabled button. Both reset on every new selection, source/reference change, verification failure and cancellation. Neither can override missing/mismatched active signer evidence.
- The UI and both receipts warn that **AuroraStore has NOT verified any backup**; this acknowledgement does **not** prove a backup exists or that app data will survive. Non-downgrade installs do not require this extra acknowledgment.
- Pre-install verification is repeated **immediately before Android session commit**, after streaming verified APK bytes, closing the time gap for installed version/signing identity changes. It adds extra private I/O and must be evaluated in hosted CI and P03 device tests. The OS still arbitrates final install behavior, including races after commit.
- Every session receipt stores the independent risk acknowledgment and installed version at review (not a backup claim). Precommit abort cleans these fields.
- `ArtifactInstallSession` remains the only installer entry point: validates blockers, revalidates APK bytes and current installed identity immediately before session creation, and forces Android PackageInstaller user action. No new installer behavior is enabled by R3D P01+P02.
- **Data preservation is not guaranteed**, even with a valid signature and explicit user consent. Live downgrades, rollback, Android DENY/ACCEPT and preservation of app data are R3D P03/P04 gated acceptance with disposable fixtures; no real personal app/data mutations are authorized here.

## Qualification

- CI source/security test: `python3 -B scripts/ci/test_r3d_p01_p02_source.py`
- Hosted Android compilation: `:app:assembleVanillaDebug`, `:app:assembleVanillaDebugAndroidTest`.
- Hosted JVM policy tests: `:app:testVanillaDebugUnitTest --tests 'com.aurora.store.data.artifact.ArtifactR3DP01P02PolicyTest'` plus inherited tests.
- Inherited R1D API36 read-only emulator must stay green. P05's `READ_ONLY_QUALIFIED_MANUAL_PENDING` is a historical result bound to its source commit; this R3D commit needs fresh hosted evidence and does not retroactively change it.

## Pending after Overlay 1

- P03: disposable fixture upgrade/downgrade, actual OS refusal/user action, data-preservation and cleanup, all explicit opt-in.
- P04: interrupted sessions/replays, root separation and final cross-device security signoff; no live test by default.
