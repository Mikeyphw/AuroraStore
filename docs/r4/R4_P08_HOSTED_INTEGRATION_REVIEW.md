# AuroraStore R4 P08 — PR113 source reconciliation and hosted integration review

**Source review checkpoint:** `de3a9441eff1524b53fb8560385cdf9a4f7e0b9e`
**PR:** <https://github.com/Mikeyphw/AuroraStore/pull/2> — draft, not merged
**Original PR113 author:** `8ff1cbc8d252cee26507372b8ead59d72872c9da`
**R3D protected base:** `4afa0a40815da035547d7b62460d56bc6d0e26bc`

## Completed and independently verified

- Targeted CI [43480230083](https://github.com/Mikeyphw/AuroraStore/actions/runs/43480230083): **success** at the source review checkpoint.
- Real hosted API36 x86_64 emulator [43480215477](https://github.com/Mikeyphw/AuroraStore/actions/runs/43480215477): **success**, 43 actual device-test executions, 25 unique nonblank light/dark screenshots, source-verified signed APK inputs. This is an emulator, **not** physical ARM64.
- Main → actual More sheet → Settings tested in both themes. The modal compositor mismatch found in HF19 was corrected in HF20; the strict independent screenshot audit remained enabled.
- Real `ComposeActivity` routes to Settings, UI Preferences, Downloads, Main, Search, Updates; screenshot integrity and theme checks pass. Test fixtures are offline and do not log in to Play.
- Existing GPlayAPI v4 (`4.0.0`), Android minimum API 23, genuine two-parent original author merge and R3D provenance tests remain protected. No production Kotlin changes are made in P08.

## Visual inspection of the 25 HF20 captures

The screenshots show nonblank Main, More-sheet, Settings, UI Preferences, Downloads, Search, Updates and update-row states in both themes. The actual More sheet displays its account header and Settings entry above the gesture navigation region; dark and light scrims are present. The standalone expressive selection popup displays in both themes, and update states have distinct update, downloading, verifying and installing controls. The Settings list and UI Preferences do not visibly overlap the status or gesture navigation areas in these captures.

**Limits:** The Main feed is composed of offline-loading placeholders; Search contains no populated search result. These screenshots cannot prove real data rendering, service integration, device-specific performance, or a pixel match to the original author's UI. No original author reference screenshots were supplied for side-by-side visual approval. **Manual upstream visual fidelity remains unapproved.**

## PR113 source review: 100 original-author changed Compose files

At HF20 source SHA: **33 author-exact**, **48 R4/R3D adaptations**, **19 retained at R3D base**. `R4_P08_RETAINED_DECISIONS.json` records each of the 19 retained path names, a source-diff rationale, a named source anchor, and explicit nonqualification. The P08 source job requires all 19 explanations, verifies them against real Git blobs, and refuses unreviewed Compose changes after this checkpoint.

### Classification of the 19 retained files

| Group | Reviewed interpretation | Paths |
| --- | --- | --- |
| GPlayAPI v4 data model imports | Intentional v4 compatibility; `data.models` upstream differs from supported `model` API | `AppPreviewProvider`, `ReviewPreviewProvider`, `CategoryBrowseScreen`, `ScreenshotScreen`, `DeveloperDetails`, `InstalledScreen`, `NotificationsScreen` |
| Download / installation safety | R3D status handling, retry/export policy, clear-all confirmation, historical-version availability and ViewModel installer list | `DownloadListItem`, `DownloadsScreen`, `DownloadActionsSheet`, `VersionPickerSheet`, `InstallerScreen` |
| API 23 / resources / language compatibility | SDK-gated permissions, singular/plural resources, local resource access, safe comparator alternative | `PermissionList`, `PermissionRationaleScreen`, `FavouriteScreen`, `SortFilter` |
| Session/API compatibility | R3D MicroG session reconstruction rather than obsolete auth helper | `SplashScreen` |
| **Behavioral follow-up needed** | `TokenType.AAS` account error handling, and spoof restart path where original author explicitly called logout but R3D navigates to Splash | `GoogleLoginScreen`, `SpoofScreen` |

**Important distinction:** These are **source-diff decisions**, not approval of feature equivalence. In particular, the login and spoof-session differences remain pending targeted hosted tests or separate semantic review. Preserve v4 and R3D behavior for now rather than restoring obsolete author code automatically.

## New fail-closed source gate

- `scripts/ci/r4_p08_retained_decisions.py` verifies 19 distinct declared paths against the genuine R3D and author trees, the current source Git blobs, reason/anchor presence, and the approved cohort split. It refuses new unreviewed Compose changes until the checkpoint and ledger are explicitly updated.
- `scripts/ci/test_r4_p08_retained_decisions.py` exercises 13 adversarial ledger mutations and 3 synthetic source-drift cases; also checks that the hosted source gate still invokes P07 parity and the real emulator suite.
- Existing screenshot duplicate, nonblank and light/dark validation, plus the actual 43-test API36 emulator, remain unchanged.

## Deferred or outstanding, never silently passed

| Gate | Status |
| --- | --- |
| 43 tests / 25 screenshots at HF20 exact SHA | PASS |
| P08 source-diff ledger and local negative tests | OFFLINE TESTED; requires hosted source gate on new commit |
| Original-author manual/pixel fidelity approval | NOT APPROVED |
| Source-level Google account and spoof-session behavior follow-ups | PENDING HOSTED TARGETED WORK |
| Physical ARM64 device qualification | DEFERRED BY USER |
| Live Google Play operations, real downloads and installer acceptance | DEFERRED BY USER |
| Merge/release qualification | NOT QUALIFIED; PR stays draft, no auto-merge |

### Next roadmap milestone

P09: hosted **offline session-state regression tests** for account add/login error presentation and spoof restart/logout semantics, without real Play sign-in or physical-device actions. Update the ledger only when test evidence supports the behavior. Manual author visual comparison remains a separate explicit gate.
