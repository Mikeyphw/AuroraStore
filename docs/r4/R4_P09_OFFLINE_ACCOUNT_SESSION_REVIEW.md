# AuroraStore R4 P09 — isolated account-state semantics and guarded source flows

**Base:** `fe871168a1bb9946259752371fabe7e9e381df5f` (P08; Targeted CI 43492579997 and real API36 emulator 43492567746 passed)

## Confirmed source defects corrected

1. `AccountProvider.getLoginToken()` previously rejected credentials only when the email was blank **and** at least one credential was blank. An email with zero tokens could therefore produce `Pair("", TokenType.AUTH)`, and a missing email with both tokens nonblank could also be returned. It now rejects a blank email **or** the absence of both nonblank credentials.
2. `AccountProvider.login()` previously wrote the account and chosen token through multiple preference mutations without clearing the token of the other type. A later AUTH login could therefore be overshadowed by a stale AAS token. The login now validates nonblank input, writes identity and chosen token in one preferences edit, and removes the old opposite token.
3. `AccountProvider.logout()` now clears identity, token types and MicroG/session markers in one preferences edit. The existing semantics (logout clears credentials, spoof restart does *not* automatically logout) are retained.

## Real hosted API36 test gate

A new `R4OfflineAccountSessionDeviceTest` has nine JUnit4 instrumentation tests against the **actual** AccountProvider and private preference store, covering email/token absence, whitespace-only tokens, both token types, bidirectional AAS/AUTH switching, failed login, and logout. Tests use literal synthetic `.invalid` identities, perform no sign-in or network calls, and snapshot/restore only auth keys through synchronous `commit()` in `@Before`/`@After`.

The hosted `r4_p05_emulator_acceptance.sh` executes the new nine-test suite alongside the previous 43 tests. The independent pixel/log auditor requires **52 real device-test executions and 25 unique, nonblank, correctly themed screenshots** on an API36 x86_64 hosted emulator. The existing 25 screenshot requirements and Main → More → Settings navigation tests are not reduced.

## Source-only UI behavior followups

`r4_p09_session_source_contract.py` verifies `GoogleLoginScreen` still uses the v4 `TokenType.AAS`, retains the `addAccount` branch that must not switch the default session, surfaces errors, and awaits `accountAdded`; it checks the `AuthViewModel` `makeDefault=false` and `syncDefaultToPrefs()` flow. It also asserts that spoof restart goes to Splash without immediately invoking logout, and that both device and locale pages trigger the restart prompt.

**Limitation:** These are *source contracts*, not runtime proof of Google account login, add-account errors, WebView/AC2DM exchange, or a physical spoof/device restart. The source-level behavior followups in the P08 ledger remain `manual_behavior_qualified=false`; P09 is an offline storage and wiring milestone, not live service qualification.

## Safety and release gates

- PR #2 remains **draft**, **not merged**. No release artifacts are signed or published.
- The genuine upstream PR #113 merge, GPlayAPI 4.0.0, minSdk 23, and R3D import/signer protection remain unchanged.
- `manual_upstream_visual_parity_approved=false`, `physical_arm64_qualified=false`, `live_google_play_qualified=false`, `real_installer_qualified=false`, `release_qualified=false`.
- The user's deferral of real-world acceptance is respected. CI must not treat emulator success as physical-device or live Google Play success.

## Next (P10)

After source-pinned hosted CI passes: inspect the fresh P09 evidence receipt and verify all 52 test executions and 25 screenshots, then prepare a **draft integration-readiness signoff** restricted to the reviewed offline gates. Investigate any P09 runtime or build failure from the actual hosted logs before claiming success. Live-service, physical ARM64 and manual upstream pixel-fidelity gates remain separate.
