# R2B — installation callback identity and ordering

Source pin: `ad78c055730b4d6895454b12b82e54de923bd545` (R2A HF05, fully green).

## Scope

- Session installer creates a durable, immutable callback identity from the download's
  `(packageName, versionCode, downloadedAt)` and the platform session ID.
- The `PendingIntent` for each session carries that identity even across process death.
- The status receiver uses `BroadcastReceiver.goAsync()` to compare the identity against
  the current Room row **before** showing approval prompts, notifying, removing queued
  installs, or deleting cached APKs. An absent or mismatching row is ignored.
- Room updates use an optimistic `UPDATE ... WHERE packageName = ... AND versionCode = ...
  AND downloadedAt = ... AND downloadStatus = ...` transition. A stale callback that loses
  a race is rejected, never applied to the replacement download generation.
- Success, progress, pending-user-action and failure follow the pure
  `InstallResultPolicy` state machine. In particular, success is terminal and a later
  failure may not revert an installed row.
- Duplicate pending callbacks produce no additional prompt after the first accepted
  `INSTALLING/COMPLETED -> AWAITING_INSTALL` transition.
- Shared library install stages carry their parent package identity but retain separate
  confirmation handling (no independent Room download row).
- An unscoped `ACTION_PACKAGE_ADDED` is accepted as success by the Room observer only
  when Android reports the installed target version; unscoped failures and progress
  may not mutate Room.

## Deliberate limitations

- Existing session callbacks from *before* R2B do not include the persisted attempt
  extra and are discarded for Room effects. R2A startup/periodic reconciliation remains
  responsible for restoring their visible install state.
- The exact-once receipt ledger across multiple simultaneous platform session IDs and
  non-session privileged installers is outside this milestone (R2C/R2D).
- This change does not qualify microG or Shizuku/root result semantics.
- No local Android Gradle build is implied. Source contract and pure JVM policy tests
  precede hosted Android build, ktlint and emulator qualification.

## Acceptance

Run `python3 -B scripts/ci/check_r2b.py`, `python3 -B scripts/ci/test_r2b_sql_cas.py`, and the existing R2A contract. GitHub Foundation
must run `assembleVanillaDebug`, `ktlintCheck`, and `testVanillaDebugUnitTest`.
Only GitHub Actions and device tests can establish Android runtime acceptance.
