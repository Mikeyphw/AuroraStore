# AuroraStore R4 P07 — hosted-only Expressive port review

Date: 2026-11-13  |  Repository: `Mikeyphw/AuroraStore`  |  PR: #2 (draft)

## Verified checkpoints

- Original author PR #113 commit: `8ff1cbc8d252cee26507372b8ead59d72872c9da`
- Protected R3D parent: `4afa0a40815da035547d7b62460d56bc6d0e26bc`
- Original two-parent integration: `340ecef9ffd8235a6e721ca37604fc380728fbf4`
- Pre-P07 qualified emulator HEAD: `d5e9672135c3147fcf605870867f92422b423684`
- Targeted CI PASS: <https://github.com/Mikeyphw/AuroraStore/actions/runs/43466429407>
- Hosted API36 x86_64 PASS: <https://github.com/Mikeyphw/AuroraStore/actions/runs/43466408915>
- Earlier evidence: 41 actual device-test executions and 23 unique nonblank screenshots, real production `ComposeActivity` navigation, offline only, no release/physical qualification.

The P07 candidate adds a real Main > More bottom sheet > Settings test in both themes, with a screenshot of the actual bottom sheet, and fixes an **isolated-test-only** menu canvas that previously stayed white in dark mode. The P07 acceptance target becomes **43 executed device tests / 25 screenshots**. These are not yet hosted-qualified until the new workflow concludes successfully.

## Grounded visual observations from HF18 screenshots

- Main: light/dark floating bottom app/games/updates navigation and search button render; the offline data feed is still loading placeholders, not live content.
- Settings and UI Preferences: both themes show actual material list surfaces, headings, controls and system bars. The previous blank Settings screenshots are no longer present.
- Downloads: offline empty-state surface and icon render in both themes.
- Updates: no-updates/loading presentations render with bottom navigation and checks; this does *not* qualify an actual Google Play update.
- Search: top search input renders, but the offline session does not produce populated results.
- Standalone expressive menu: popup selection and checkbox callbacks are qualified; the old **dark-mode screenshot background was white** because the isolated `AuroraTheme` did not paint a Surface. P07 paints a theme-matching Surface before capturing the popup and adds a pixel guard for both modes.
- More bottom sheet: this was missing from the HF18 evidence and is added as a P07 hosted navigation/screenshot target.

No reference screenshots were obtained from the original author to claim pixel-perfect similarity. No human visual approval is implied by screenshot hash, nonblank, navigation or color checks.

## Upstream source parity baseline

The genuine author and protected R3D Git trees contain **100** author-changed `app/src/main/java/com/aurora/store/compose/` paths. At HF18: **33** exactly match the author's Git blob, **48** are R4/R3D adaptations, and **19** remain identical to the protected R3D blob. Those 19 must be reviewed for intentional safety preservation vs. missing Expressive changes. Do not infer 19 functional defects from Git blob inequality.

The retained-file backlog includes the DownloadListItem, DownloadsScreen, DownloadActionsSheet, VersionPickerSheet, InstalledScreen, FavouriteScreen, NotificationsScreen, InstallerScreen, ScreenshotScreen and related flows. Initial comparisons found small or safety-related deltas in the first inspected set (notably guarded download clear-all and version picker behavior). Upstream replacement must not discard those protections. `scripts/ci/r4_p07_source_parity.py` emits a full 100-path inventory from *actual Git trees* and refuses any new unreviewed wholesale regression to R3D.

## Qualification and merge policy

| Gate | Status |
| --- | --- |
| HF18 Targeted CI / hosted API36 / 41 tests / 23 screenshots | PASS (exact HF18 SHA) |
| New P07 real More navigation and dark-menu background tests | PENDING HOSTED CI |
| R3D download and installation safety source protection | PASS as of HF18; P07 source-gated |
| Upstream PR113 UI adaptation inventory | BASELINED; 19 retained files pending individual review |
| Material 3 Expressive manual/pixel-perfect signoff | NOT APPROVED |
| Physical ARM64 / live Play / real installer | DEFERRED BY USER, not passed |
| Release qualification and merge authorization | NOT QUALIFIED; PR must remain draft |

The deferred gates are informational limitations, not blocked CI or reasons to silently certify a release. Continue safe hosted development and keep the draft PR open. Any eventual merge is a separate explicit decision, not an automated consequence of green CI.
