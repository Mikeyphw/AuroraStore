# R3C06 P6 — Independent on-demand feature targeting qualification

## Scope and authority

This opt-in extension **does not insert a feature into the AuroraStore production application**. It builds a second isolated Android Gradle Plugin 9.4.1 Android App Bundle with `com.android.dynamic-feature`, named `featureproof`, declared `dist:on-demand` and `fusing=false`.

On one exact-commit hosted API36 emulator, the existing signed production `app-vanilla-debug.aab` is run through the **official SHA256-pinned** bundletool 1.18.3 signer/targeting oracle. Its measured ABI, density, locale and SDK selections must remain independently signed and distinct. The fixture AAB is then built with hosted Gradle, its actual **compiled** feature and base manifests are inspected through official bundletool, and its generated `.apks` set is separately signed using a *new* ephemeral PKCS12 key. The feature selection must contain its own cryptographically verified `featureproof-*.apk`, absent from default device selection.

The combined `R3C06_P6_COMPOSITE_RECEIPT.json` may return PASS only when both distinct AAB receipts have matching source SHA, run ID, actual device specifications, pinned tool hash, independent AAB and `.apks` hashes, **different** ephemeral fixture certificate identities, 4/4 production dimension coverage and on-demand feature evidence. The feature matrix itself may honestly remain `PARTIAL` on ABI/density/locale/SDK where this *minimal* fixture has no variants; the production matrix remains `PARTIAL` because it has no dynamic feature. **Composite PASS is scoped to two different AABs**. It never claims one production APK has all five dimensions.

No `--strict-dimensions` shortcut, no certificate parsing bypass, no synthetic APK signature claims, no Play/publisher verification, no release signing, no physical ARM64 acceptance, no live installation, no vendor APKM/XAPK acceptance. All full R3C07/R3C08/R3D/R4/R5/R6 milestones remain separate.

## Manual invocation after exact-head targeted 3/3 CI

```zsh
# Branch must be the actual remote PR #9 head at time of dispatch.
gh workflow run aurora-r1d-emulator.yml \
  -R Mikeyphw/AuroraStore-Standalone \
  --ref feature/r3c04-c02-c08-import-handoff-archives-20261109 \
  -f r3c06_live_install=false \
  -f r3c06_bundletool_matrix=true \
  -f r3c06_feature_matrix=true
```

The P6 input **defaults false** and explicitly requires the existing production matrix input true. It runs only through manual workflow dispatch. The existing workflow's read-only 51 Android tests run first, preserving their separate source-bound receipt. It uploads the raw and composite JSON receipts under the existing `aurora-r1d-api36-emulator-evidence` artifact. If the AAB build, manifest inspection, extraction, signing, or any receipt comparison fails, CI fails closed. Do not claim P6 qualified until that actual run is successful and its JSON receipts inspected.

## Expected raw receipts

- `R3C06_P4_API36_READONLY_RECEIPT.json`: existing 51 read-only device tests, separate.
- `R3C06_P3_BUNDLETOOL_MATRIX_RECEIPT.json`: real Aurora AAB, four dimensions true, `PARTIAL` due absent production feature.
- `R3C06_P5_MANUAL_RECEIPT.json`: still `PARTIAL` for production-only matrix without live install.
- `R3C06_P6_FIXTURE_MANIFEST_RECEIPT.json`: actual compiled isolated feature module on-demand, fixture asset and package identity.
- `R3C06_P6_FEATURE_MATRIX_RECEIPT.json`: independent official signed feature APK selection, usually `PARTIAL` for unrepresented hardware dimensions.
- `R3C06_P6_COMPOSITE_RECEIPT.json`: **PASS only for combined independent fixture targeting**.

Local Python/unit tests are only source/receipt-adversarial checks, never a substitute for the hosted AAB build or device runtime acceptance.
