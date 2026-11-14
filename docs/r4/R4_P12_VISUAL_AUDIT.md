# AuroraStore R4 P12 HF25 — actual-image visual audit and contrast repair

**Scope:** Source-pinned visual defect remediation only; fork [PR #2](https://github.com/Mikeyphw/AuroraStore/pull/2) remains draft and unmerged. Original reference is [upstream PR #113](https://github.com/whyorean/AuroraStore/pull/113).

## Evidence inspected

- P09 real hosted API36 x86_64 emulator run `43498499144`, source `ecb9c4db5d347f5073ceacc4ef0555f9d6e52608`, artifact `14072889339` (ZIP digest `5a4f633461934f05012dfa53492a417e0e034821982a2fbd09dfa06bd45c94ac`).
- Actual 25 PNGs (1080 × 2400), including 12 light, 12 dark and one additional light cold-launch capture; 52 instrumentation test executions.
- Original author's preview screenshots for For You, Settings and Search read from upstream PR #113 at `8ff1cbc8d252cee26507372b8ead59d72872c9da`.
- `Placeholder.kt`, `UpdatesScreen.kt`, `R4ActivityNavigationDeviceTest.kt`, and existing screenshot pixel auditor inspected at P11 head `9632c29bc19248bb905d1aaa257469118576312d`.

## Finding V-01 — confirmed dark-theme contrast failure

`dark/r4_activity_updates.png` displays *No updates available* in near-black on the dark canvas. Pixels in the message region show `#000000` text on `#121318` background, approximately **1.13:1 contrast**. The same label is clearly readable on the light screenshot. The existing PNG auditor checks nonblank uniqueness and theme canvas, not this text foreground. Android's `Placeholder` composable has a `Text(message)` with no explicit text `color`. Within the updates `PullToRefreshBox`, this appears to inherit a foreground inappropriate for the dark surface; the icon and button explicitly use theme colors.

**Patch:** Set `Placeholder`'s message `Text` color to `MaterialTheme.colorScheme.onSurface`. This changes no auth, downloads, installation, navigation, network or session behavior. Add a pure-stdlib pixel-region check to the existing hosted PNG auditor: the dark Updates empty-state label region must contain a sufficient number of high-luminance foreground samples. A separate negative fixture with black-on-dark foreground must be refused. This is a targeted automated contrast safeguard, **not** complete WCAG or visual equivalence certification.

## What the captured P09 images do and do not show

| Screen | Actual image review | Current status |
|---|---|---|
| Main / bottom floating navigation | Rounded controls and navigation remain visible in both themes; only loading skeleton rows, no populated catalog cards | Partial: populated For You/home-card fidelity unproved |
| More sheet | Modal visibly rendered and Settings item present; dimmed background and theme colors observed | Visual sample captured; detailed motion and touch geometry not proven |
| Settings / Customization | Material-like grouped rows, controls and theme selection present; R3D's extra *Import and verify APKs* item is intentionally retained | Representative empty-data visual sample; human author-side fidelity still pending |
| Search | The field is visible in light/dark, but no query is entered | Results/filter rows and full-screen search fidelity not proven |
| Downloads | Empty-state icon/message and navigation visible in both themes | Populated download queue visual not proven |
| Updates | Empty-state visible, **dark message contrast defect confirmed** | Fix and fresh CI screenshots required |
| App details, Top Charts, Categories, home-card install/open | No corresponding real populated P09 screenshots | Unqualified |
| Dynamic motion, clipping on differing screen sizes | Only static 1080×2400 hosted captures | Unqualified |

## Source and qualification boundary

P08, P09, P10, P11 reviews remain **historical** source-pinned milestones. The P12 patch changes production UI code and the screenshot auditor, so the old P09 emulator receipt must not be presented as acceptance of P12. For this reason, the historical P08/P10 reviews are explicitly bound to their original, unchanged Git checkpoints; P11's five-file review inventory is frozen at its P11 commit; the new P12 gate allows only its documented changed paths and requires the fresh 64-test/37-screenshot emulator workflow to execute on the P12 SHA. Only that **new** hosted run can qualify the contrast fix. The manual upstream visual parity flag remains false.

## After hosted P12 pass

Inspect the new populated, deterministic offline visual fixtures that exercise For You cards, search results, app details, charts and categories without live Google Play or installation. Then carry unresolved behavioral, physical ARM64, live-account and signing gates to separate explicitly authorized phases.

## HF25 fold-in: deterministic populated Compose coverage

Six additional JUnit4 tests are scheduled for the real hosted API36 x86_64 emulator
**in both light and dark modes**, capturing 12 extra screenshots of Aurora's
actual production composables: home carousel cards and install actions, search
result rows, app details and action/portal cards, top-chart ranks, categories,
and idle/verifying installation controls. The models use synthetic `invalid.aurora.p12`
package names, no live catalog, Play login, package installer or APK downloads.

The new gate requires **64 total test executions and 37 actual captured PNGs**.
It enforces nonblank/unique images, theme differentiation, and the new dark Updates
contrast guard; the earlier P09 52/25 receipt is strictly historical. These are
production component visual fixtures, **not full network-backed navigation** or
upstream screenshot parity approval. Manual comparison with PR #113 remains open.
