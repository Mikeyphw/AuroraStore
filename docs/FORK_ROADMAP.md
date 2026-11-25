# Aurora Store fork: development roadmap

<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

Source of record: https://github.com/whyorean/AuroraStore (`master`).
The initial foundation was prepared against upstream commit
`89933d4a2c138a3452486c5eb6e5c2e0df578470`.

This fork is an independent work-in-progress and is not endorsed by Aurora OSS.
Retain upstream GPL-3.0-or-later licensing and attribution.

## Release sequence

| Phase | Goal | Minimum exit gate |
|---|---|---|
| R0 | Fork, reproducible source baseline, GitHub Actions | Source contract, hosted vanillaDebug build, lint, JVM tests, APK artifact |
| R1 | Reliable download state, cancellation, queue recovery, retries/resume | Cancellation and recovery regression tests, Android device acceptance |
| R2 | Installation lifecycle including microG and interrupted installs | Verified terminal outcomes across installers; no permanent Installing state |
| R3 | Historical version picker and downgrade safety | Search by version name, availability/compatibility checks, safe error states |
| R4 | Material 3 Expressive UX based selectively on PR #113 | No backend regression, UI/accessibility/insets tests, Android compatibility decision |
| R5 | Advanced update filtering | Correct version rules, preserved existing ignore preferences |
| R6 | Full regression suite, hosted CI, device qualification | Release acceptance matrix and signed release strategy |

## Development and release rules

- Maintain a clean relationship to the upstream history.
- Use source-pinned overlays that declare their input source commit and validate files before modification.
- Prefer a consolidated overlay per release and consolidate any follow-up hotfixes.
- Never overwrite unrelated local changes. Do not bypass a failed source integrity check.
- Keep Gradle builds on GitHub Actions. Use the Termux checkout only for source preparation and `gh` operations.
- R1 must address queued/purchasing/downloading/verifying cancellation, cancel-all coverage for both app and update workers, stale status writes, recovery from process death, and stalled network operations.
- R2 must reconcile saved installation state with Android package state and handle microG results correctly.
- R3 cannot guarantee Google still serves any given historical APK; keep an advanced manual version-code option.
- Port PR #113 selectively onto current upstream; never replace the modern download backend with stale PR code.
- Retain upstream `minSdk=23` unless separately qualified and approved to change.
- Avoid changing the application ID/signing policy during the foundation phase. The upstream debug variant uses the `.debug` suffix; release distribution requires its own signing decision.
- All release claims require measured CI/device evidence; a static contract check alone is not a successful Android build.

## Rebase / upstream sync

`git fetch upstream master` and inspect the actual changes. Create an integration branch,
replay only fork changes after reviewing compatibility, run GitHub Actions, and merge
only after acceptance. Preserve the recorded baseline for traceability.

## Source baseline

- Android Gradle Plugin: 9.4.1
- Gradle wrapper: 9.6.0
- Kotlin: 2.4.10
- Java toolchain: 21
- Android compile SDK: 37
- Android minimum SDK: 23
- Build flavor: `vanilla`
- Initial CI artifact: `app/build/outputs/apk/vanilla/debug/app-vanilla-debug.apk`

## AUR-INT01 — consolidated source and acceptance campaign

The restored six draft PRs (#1–#6) are preserved. Integrate on
`feature/aurora-consolidated-integration-20261125`, based on fork master
`12840634f1a812c613eda49dff5abeeb6e02cc25`. The seven input heads are locked
in `scripts/ci/check_aur_int01.py`. A merge-based history, not an artificial
linear overlay, preserves all six PR ancestors and both repaired CI heads.

| ID | Scope | Gate |
|---|---|---|
| INT01-A | Source/history identity | Exact seven inputs and Git object integrity |
| INT01-B | Consolidate fork heads | All six heads ancestors |
| INT01-C | Current master and v17 Room/API integration | Local regression; generated schema and real Room tests hosted |
| INT01-D | P13 fresh-frame and CI provenance repairs | Current source contracts plus exact historical replay |
| INT01-E | Native Devtool committed-source delivery | Source-bound session, normal push, single replacement draft PR |
| INT01-F | Full hosted acceptance | Targeted PR CI plus Foundation, R1D, R2D and five R4 push lanes on exact integrated SHA |
| INT01-G | Independent acceptance | Separately authorized R3D disposable gates, P15 ARM64/real installer prompt, P16 independent review |

`config/delivery-required-ci.json` pins the actual Targeted PR workflow identity.
It qualifies **only** the PR CI lane; other exact-source push workflows are
separate, mandatory campaign acceptance gates. No CI24 workflow is declared
in this Aurora repository. Do not substitute Devtool's own CI24 for Aurora
Android evidence. Do not auto-close original PRs or merge the replacement.
Generated Room v17 must be uploaded, reviewed and committed from hosted KSP
before final release qualification. No generated schema hash is fabricated.
R5 advanced update filtering and R6 release qualification remain subsequent
milestones. Historical R0–R4 receipts remain evidence at their original SHAs,
not acceptance of this integrated source.

### INT01-HF01 — initial hosted failure repair

PR #7 was delivered at `d234dc010d7625b75ddb6d28fefdb43d4d0114d6`.
The initial nine hosted workflows failed; source contracts passed, but Kotlin
compilation, debug-provider formatting and transient AGP resolution blocked
acceptance. Repair the missing Compose and privacy-model imports, preserve
read-only fixture behavior, and retry only the exact observed AGP 9.4.1
resolution failure in R1D/P13. Re-run all nine workflows at the repaired PR
head. The new local source tests check import declarations, executable P14
markers, provider formatting and bounded retry behavior; they do not qualify
Android compilation, ktlint, Room KSP export, emulator or physical execution.
Do not create another consolidation PR or replay the original integration.
