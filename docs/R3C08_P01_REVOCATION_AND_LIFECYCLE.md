# R3C08 P01 — actual Android SAF revocation & importer cancellation

**Scope:** the three-test Android 36 instrumented harness uses TWO test-APK-only
content providers: one OS-protected document provider and one exact-target-UID
control provider that issues/revokes a temporary OS read grant. The target app
must have no persistent read entitlement. The signed bytes originate in the
instrumentation APK; no Play identity or historical version is inferred.

1. Test an initial OS permission denial, a temporary OS grant, a successful
   fresh read, a genuine revoke, an OS denial and an unsuccessful new open.
2. Hand the revoked URI to the production importer, not a fake staging function;
   confirm safe refusal, no active verified receipt and no install consent.
3. Verify a separate signed debug APK, approve only its transient consent, then
   cancel through the production button; assert that the active receipt and
   consent are gone. Source regressions also require **document-picker dismissal**
   to invalidate the active session rather than merely repainting the UI.

R3C08 P01 deliberately does NOT assert that Android revocation retroactively
closes already-open file descriptors. Such races, signer substitution, replayed
callbacks, archive bombs, downgrade/install denial, and real-world/physical
install work remain independent subsequent R3C08 milestones.

**Qualification:** targeted CI 3/3, then the inherited API36 R1D workflow and
uploaded source/run-bound `R3C08_P01_API36_REVOCATION_RECEIPT.json` with its
actual instrumentation log. The 13 receipt-negative selftests cannot produce
live qualification and the default run performs **no installation**.
