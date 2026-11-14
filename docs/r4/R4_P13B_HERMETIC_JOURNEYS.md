# AuroraStore R4 P13-B02 — Consolidated Nav3, Multi-Size & PR113 Visual Gate

**Status:** `P13B_HOSTED_PENDING`. This source-only package is **not** a passing
GitHub Actions run, human signoff, physical acceptance, or release qualification.

- Fork: `Mikeyphw/AuroraStore`, ID `1457358363`.
- P12 checkpoint: `3ea10b6f4b0fed5a8913e4edef3536cfc93fc52f`.
- P12 historic CI: 64 Android tests / 37 verified PNGs at run 43612363362.
- New branch: `feature/aurora-r4-p13b-nav3-multisize-20261114`.
- Draft stacked PR against R4 PR #2's branch, not main/master.

## Integrated execution contract

A new `R4P13BIntegratedVisualDeviceTest` still renders real Aurora production
composables with local `.invalid` app models, navigation-like stateful component
journeys, review card and local artwork; **not** a production Navigation3 graph.

A separate `R4P13BProductionNav3DeviceTest` launches the **actual** Hilt-backed
`ComposeActivity` and taps through **real** routes: Main → Search → Back and
Main → More → Settings → UI Preferences, including the protected R3D APK
verification setting. These are production routing probes with no live catalog
query, account authentication, downloads or APK installer side effects.

The source-pinned hosted API36 x86_64 workflow runs both classes in light/dark
at **two display configurations**: full 1080×2400 / density 420, compact
720×1600 / density 320. Each of four combinations must pass 3 integrated +
2 Navigation3 tests and capture 8 integrated + 4 production-route screenshots.
Expected total: **20 Android test executions / 48 compositor PNGs**.
The workflow uses the existing P12 pixel decoder, validates exact screenshot
sizes, distinct light/dark frames and test counts, and keeps failure logs and
fail-closed `NOT_RUN` evidence until successful audit.

## Upstream author references and final visual review

The 8 original-author visuals in
`docs/r4/R4_P13B_UPSTREAM_PR113_REFERENCES.json` pin filenames and Git blob
SHA1 from `aryan-j/AuroraStore`, branch `codex/aurora-ui-showcase`, as cited
in the upstream author PR #113. These are examples, not pixel-exact test
goldens: they show **live app data, another device, and a different M3
version**, whereas most P13B visuals are offline deterministic fixtures.

The `r4_p13b_visual_signoff.py` utility operates only **after** a real hosted
receipt exists. It generates an explicit reviewer template and validates
human review decisions against the exact source/run, pinned upstream blobs,
all 48 actual screenshot hashes and the eight required screen comparisons.
It refuses missing reviewer identity, unreviewed comparisons, mismatched
provenance, release approval, and any attempted **full upstream signoff**
while the record still contains fixture-only or missing live-catalog routes.
A limited P13B visual review may be approved when all eight reference
comparisons are marked `match` or `intentional_deviation` with explanations.
This does **not** authorize a full upstream PR113 visual fidelity certificate.

Example after downloading the successful evidence ZIP:

```bash
python3 scripts/ci/r4_p13b_visual_signoff.py \
  --receipt evidence/receipt.json \
  --references docs/r4/R4_P13B_UPSTREAM_PR113_REFERENCES.json \
  --template evidence/review-template.json
# Inspect every actual PNG against the real author reference first.
# Complete reviewer, acknowledgement, and all eight grounded decisions.
python3 scripts/ci/r4_p13b_visual_signoff.py \
  --receipt evidence/receipt.json \
  --references docs/r4/R4_P13B_UPSTREAM_PR113_REFERENCES.json \
  --review evidence/review-completed.json \
  --out evidence/limited-visual-review.json
```

## Non-goals and retained deferred checks

No production UI/security code changes; no local Gradle, no physical device
writes, no root, no live Play or accounts, no real install/update. Neither
x86_64 emulator tests nor reviewer decisions can override deferred physical
ARM64, real full-catalog UX, signing, release qualification or independent
merge review. Both R3D PR #1 and R4 PR #2 remain draft until separately approved.
