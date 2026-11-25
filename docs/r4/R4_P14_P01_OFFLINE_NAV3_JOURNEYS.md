# AuroraStore R4 P14-P01/P02 — Consolidated offline Navigation3 and full Search/Details journeys

## Qualification baseline

- Fork `Mikeyphw/AuroraStore`; stacked atop P13-B02 draft PR #3 exact commit `47c360e9cb553f73fb6858cd364ea19835bada6e`.
- P13-B02 source-qualified hosted run **43650748680** (20 tests/48 PNGs) and Targeted CI **43650752797**.
- Human reviewed the P13-B02 screenshots. The original source-bound limited visual review, hosted receipt and limited approval result are committed unchanged under `docs/r4/evidence/P13B02_*43650748680.json`.
- Manual approval means **limited P13-B02 screenshot acceptance**, not release approval or full upstream PR113 parity. The `details_top` fidelity gap remains unqualified.

## P14-P01 scope

Actual Hilt-backed ComposeActivity + Navigation3 on disposable GitHub API36 x86_64 emulator. Tests run in both light and dark at 1080x2400/420 and 720x1600/320 and capture 10 per profile/mode. Requires **16 instrumentation executions and 40 fresh distinct PNGs**, with exact source/run and app/test APK provenance receipts.

New actual routes:

1. Main → Search → Back → Downloads → Back (real buttons, no live query).
2. Main → More → Settings → UI Preferences → Back → Back; preserve protected R3D `Import and verify APKs` entry, without touching theme setting.
3. Main Apps → Games → Updates → Apps; assert selectable tab state, without triggering update/download/install operations.

Captured frames use bounded body-content change checks against the pre-route baseline, refusing stale compositor frames after 12 attempts.

The P14-P02 extension makes a minimal production Hilt injection seam (release binding is a strict no-op), exercises real SearchViewModel and AppDetailsViewModel with an androidTest-only Hilt module, renders the production Search/Details screens with local artwork and featured review, and adds non-visual semantics tags to the Details list/carousel/review. The new fourth journey captures populated Search, Details identity, actual screenshot carousel and reviews. It is deterministic fixture evidence, not a live Play or real-account journey. No Play login or real install. Existing P12 and P13 source trees and PRs remain immutable. No local Gradle. This source-only overlay and its tests are **not** hosted-qualified until the exact new branch SHA passes GitHub.

## Next P14 stages

- P14-P02 is folded in here: real production Search and Details ViewModels under androidTest-only deterministic Hilt gateway. Full upstream visual parity still requires live catalog evidence.
- P14-P03: controlled download/update failure, cancel, recover, persistence and installer refusal with dummy fixtures.
- P15: authorized physical ARM64 acceptance.
- P16: independent recovery, security, signing and merge/release qualification.

Release, live account, real installer and full upstream visual signoff remain false.
