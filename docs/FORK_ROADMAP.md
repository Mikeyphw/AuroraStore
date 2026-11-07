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
