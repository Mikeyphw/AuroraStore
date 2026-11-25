# R3C-01 — Exact-version availability and compatibility evidence policy

R3C-01 introduces an independently testable, conservative decision model. It **does not
yet enable a live Play availability probe or change the production manual download UI**.
Those integrations and hosted API-36 negative device tests are subsequent R3C gates.

## Evidence rules

- Exodus historical reports are informative only. They are not a Google Play APK archive.
- Delivery is UNKNOWN until the exact requested APK set is obtained and R3B-verified.
- An unavailable result only applies to its exact version; an error for another version
  cannot make the current selection unavailable.
- APK bytes verified for a different version cannot mark this version available.
- SDK bounds can be checked only against the **exact requested version** manifest. Current
  Play listing's SDK bounds must never be reused for historical APKs.
- Passing SDK bounds does not prove ABI, signing-lineage or Android install compatibility.
- An older installed version always requires the existing explicit downgrade consent;
  a matching signature or version history is not a downgrade override.
- Unknown availability is allowed to **attempt** exact Play delivery. It is never shown
  as available, and no mirror or fabricated URL is used.
- Android PackageInstaller is the final authority, with no silent uninstall or data wipe.

## Qualified scope

New JVM tests check malformed versions, stale reports, exact-version mismatches,
SDK-bound incompatibilities, unknown metadata, and explicit downgrade consent.
`scripts/ci/check_r3c.py` is a source contract wired into Foundation CI.
It is not a replacement for live historical APK acquisition and device qualification.

## R3C-02 — Picker and manual request integration

The historical picker and manual version input now invoke the conservative R3C policy
using the exact version selected by the user, the current listing version, and the
installed version. No manifest SDK bounds or verified APK evidence are fabricated.
A history report therefore remains UNKNOWN for Play availability and device compatibility.
The picker and manual form communicate this explicitly rather than showing a false
"available" state. The manual action refuses invalid selection, routes a downgrade
through the existing consent dialog, and re-checks installed-version state on action.
No account/network probe is performed when the picker opens; the existing worker attempts
exact Play delivery only after user confirmation. Runtime availability cannot be claimed
until that request succeeds and R3B verifies the resulting APK set.

R3C-02 is covered by an additional source contract, the R3C-01 JVM evidence-policy
suite, and hosted app compilation/ktlint. It is not a live Play-availability or
real-device historical downgrade qualification.

Remaining work: capture exact-version negative/positive Play delivery evidence and
R3B post-verification outcomes, report actionable unavailable and SDK-incompatible
states only on trustworthy evidence, and run API-36 device tests with fixtures.
