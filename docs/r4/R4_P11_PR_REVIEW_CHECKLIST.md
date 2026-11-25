# AuroraStore R4 P11 — draft PR review staging (not release approval)

**Scope:** Review [fork PR #2](https://github.com/Mikeyphw/AuroraStore/pull/2) against [upstream original-author PR #113](https://github.com/whyorean/AuroraStore/pull/113) without automatically marking the draft ready, merging, tagging or releasing.

## Pinned baseline and inventory

- R3D comparison base `4afa0a40815da035547d7b62460d56bc6d0e26bc`.
- P10 integration checkpoint `a21f81a03ea618dcd2fe97d3725343f81449b715`.
- Genuine original-author merge `340ecef9ffd8235a6e721ca37604fc380728fbf4`, whose parents are R3D and upstream author `8ff1cbc8d252cee26507372b8ead59d72872c9da`.
- R3D → P10: **153 changed paths**: 95 production paths, 4 Android instrumentation, 13 CI scripts, 8 docs/evidence, 1 new workflow, 32 other paths (showcase assets, README, Gradle metadata).
- Of the **100 upstream author-changed Compose files**, prior Git tree classification has **33 exact author blobs, 48 adapted blobs and 19 retained R3D blobs**. These are byte/source classifications, **not visual-equivalence or behavior-equivalence proofs**.
- Post-P10 changes are restricted to this P11 review gate, its tests, checklist, status record, and the existing hosted workflow's two added gate invocations. No Android production/test source changes may inherit earlier device evidence silently.

## Prior hosted evidence (source-bound, do not upgrade qualification)

- P09 source `ecb9c4db5d347f5073ceacc4ef0555f9d6e52608`: Targeted CI run `43498509688`, emulator run `43498499144`, each reported success.
- API36 **x86_64 hosted emulator**: 52 Android test executions including 9 synthetic account-preference tests, and 25 unique nonblank light/dark screenshot captures, with APK input provenance receipts.
- P10 targeted CI run `43503513494` passed; the P10 archive verifies exact receipt bytes, protected source state, original merge ancestry and no post-P09 application modifications.
- P11 is an inventory, reviewer staging and regression guard. It **does not** independently reproduce these P09 screenshots, prove original-author visual fidelity, sign in to live services, run on ARM64, operate a real installer, or authenticate a production release.

## Manual reviewer work still open

1. **Author comparison:** side-by-side inspect every relevant original PR #113 screenshot and the actual R4 captures for home cards/actions, bottom navigation, search, details, charts, settings, updates, status/navigation bars and motion/spacing. Treat pixel differences as explicit decisions, not automated passes.
2. **Retained-file behavior:** inspect the 19 R3D-retained Compose files. In particular verify `GoogleLoginScreen.kt` and `SpoofScreen.kt` in an appropriate real session; P09 only proves their source wiring and synthetic preference behavior.
3. **Real Google services (deferred):** manual first/default and added-account login, errors, account switching, AAS/AUTH, MicroG, and persistence. Do not use synthetic `.invalid` identities as live evidence.
4. **Spoof restart (deferred):** verify restart prompt, Splash route, and session preservation during actual user interaction.
5. **Physical device (deferred):** Android ARM64 validation only after explicit permission, without surprise root/device actions.
6. **Actual install/update (deferred):** verify a real-world update, cancellation, failure handling and recovery with intentional test fixtures, separately from offline workers.
7. **Release & signing (deferred):** signing chain, artifact provenance, publication and merge approval are out of scope.

## Review disposition

**DRAFT_REVIEW_STAGED_RELEASE_NOT_QUALIFIED**. PR #2 stays draft; PR #1/R3D stays separate. No automatic merge or release. The source gate denies unexpected post-P10 paths, false review approval flags, removed workflow test steps, or permission escalation. CI's success may certify *the hosted source checkpoint only*. The human reviewer may choose to perform the deferred checks in a future separately authorized phase.
