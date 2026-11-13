# AuroraStore R4 P10 HF23 — Integration-readiness source and evidence gate

This is a **hosted-only integration checkpoint**, not release or physical-device qualification.
It carries forward the completed P09 run evidence and binds it to the exact source SHA.

## Verified baseline

- P09 source SHA `ecb9c4db5d347f5073ceacc4ef0555f9d6e52608`.
- Targeted CI run 43498509688: completed success.
- API36 x86_64 emulator run 43498499144: completed success.
- 52 device-test executions, including nine synthetic/offline account preference checks.
- 25 unique nonblank screenshots with light/dark theme checks.
- Exact-source debug APK and instrumentation APK provenance receipt; no release signing qualification.
- P08 source review: 33 exact original-author Compose files, 48 R3D adaptations, 19 intentionally retained R3D files.

## P10 gate

The new source gate validates byte-for-byte archived P09 receipt/provenance SHA-256, run and source identity,
all 52 per-suite test counts, all 25 screenshot manifest entries and unique hashes,
readonly GitHub permissions, original author merge ancestry, P08/P09 source-contract checks,
and the absence of post-P09 production changes. It refuses false claims of approval, fabricated
or mismatched screenshots, missing provenance, modified source and changed workflows.

The code and test are offline-only and do not perform network requests.
The existing 52-test/25-image hosted emulator workflow is unchanged apart from adding P10 source checks.
No Gradle is run on the local device.

## Remaining review work (not passed by this checkpoint)

- Original-author side-by-side Material 3 Expressive visual fidelity signoff remains unapproved.
- Real Google account sign-in and add-account flow are not qualified (the source and synthetic preference flow are checked).
- Spoof restart UI semantics are source-reviewed but not separately proven by a live session.
- Physical ARM64, live Google Play, real APK delivery, actual installer operations and release signing are deferred.
- PR #2 remains draft, not merged. This overlay must never auto-merge, tag, or publish a release.

## Next milestone

P11: optional explicit PR-review staging, cross-check changed source inventory against R3D, and final review checklist.
No release or physical-device claim may be automatically inferred from P10 success.
