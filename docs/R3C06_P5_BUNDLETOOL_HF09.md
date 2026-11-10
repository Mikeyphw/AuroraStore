# R3C06 P5 HF09 — bundletool split signing forensic repair

## Proven trigger and limitations

Manual R1D matrix-only run **42890752610**, source `e5ebff49924a3890f3f15542d1bf878592dd427f`, failed after **51 read-only API36 tests** at `unsigned or invalid extracted split base-en_3.apk`. The original code inspected only the default `apksigner verify --verbose` v2 output string, discarding the detailed verifier result. The exact reason v2 was not reported is **not proven** by that run. Earlier synthetic OS DENY→ACCEPT run **42887604268** is separate and qualified only for that scope. Neither establishes a real-vendor APKM/XAPK install, an authenticated publisher, real Play delivery, physical-device acceptance or a release.

## Repair semantics

The official `bundletool-all-1.18.3.jar` stays SHA-256 pinned at `a099cfa1543f55593bc2ed16a70a7c67fe54b1747bb7301f37fdfd6d91028e29`. Bundletool generates its own ephemeral test-key-signed `.apks`. No APK is re-signed after extraction.

Each selected APK must match exactly one original member's SHA-256 in that signed `.apks` archive and pass all three `apksigner` cryptographic probes: declared SDK range, actual API36, and an explicit API24–27 window proving APK Signature Scheme v2. All probes must report the identical, unique signer certificate SHA-256. All selected splits and tested device scenarios must share the baseline signer **and match the short-lived generated fixture keystore certificate**. Changed, missing, ambiguous, unsigned, v3-only without positive v2, cross-signer, unprovable or unstable APK bytes **REFUSE** instead of claiming coverage. No SDK bypass and no signature policy downgrade.

`apksigner` output can vary with its SDK window: a default `v2: false` line alone does not always establish the absence of a valid v2 block. The explicit window plus actual API36 verification resolves that ambiguity without trusting string changes or a naked v3 success. If the official tool actually produces an APK without verifiable v2, the new runner still refuses and reports its failing probe.

The matrix record now includes source SHA, run ID, official jar SHA, AAB SHA, `.apks` SHA, actual API36 device spec, selected APK names/digests, original archive-member paths, v2/API36 signer proofs, and truthful per-dimension coverage. The manual P5 validator independently cross-checks the receipt structure, signed selections, variant differences and PASS/PARTIAL status. It cannot independently replay ephemeral APK cryptography from JSON alone; that requires the pinned as-run CI runner.

## Qualification ladder

1. The exact-head Devtool full-file overlay must pass 20 new matrix security negatives and 29 P5 receipt negatives plus all existing targeted source/security/Android compilation gates on its new SHA. Never rewrite the old run or old install evidence.
2. **Only with opt-in:** separately dispatch `aurora-r1d-emulator.yml` with `r3c06_live_install=false`, `r3c06_bundletool_matrix=true`. No repeat synthetic install by default.
3. Require actual API36 logs and the newly uploaded `R3C06_P3_BUNDLETOOL_MATRIX_RECEIPT.json` and `R3C06_P5_MANUAL_RECEIPT.json` tied to the exact source SHA/run ID; if the current vanillaDebug AAB does not contain dynamic features or distinct ABI/density variants, report `PARTIAL` rather than inventing coverage.
4. Continue R3C07 user-facing provider/evidence/consent UX, then R3C08 adversarial signoff, R3D installed signer/downgrade, R4 selective M3 Expressive, R5 filtering, R6 release/physical acceptance. Complete historical roadmap files remain in the user's prior full handoff.

## Security note

`apksigner` confirms APK signatures, not publisher authenticity: the ephemeral CI key merely proves continuity of a synthetic split set. Device/emulator compatibility and Android PackageInstaller consent are independent checks, and local import must never create Google Play provenance.

## HF03 — legacy P4 source regression migration

The historical P4 `test_refused_bundletool_variant_does_not_count` used two filenames and shortened hashes as a supposed positive `SIGNED` candidate. Under the hardened HF09 contract this must REFUSE: no `verified_apks`, unique signer SHA-256, actual APK v2 or API36 proof existed. HF03 migrates **that one test method** to use realistic complete proof and checks refused/unchanged, missing proof, missing one split, failed v2/API36 and mismatched signer. The remaining P4 tests and the verification policy remain unchanged. The exact original P4 Git blob is pinned; the complete overlay touches seven files. An isolated no-network P4 rehearsal runs within the executable archive before the full Devtool apply.
