# R3B — Downloaded APK identity, signer verification, and verified installer snapshots

<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

## Trust boundary

The download metadata lists the requested package/version and the BASE and SPLIT files. Both
worker completion and installer entry now demand all declared APKs. The worker verifies file
hashes, signatures and AndroidManifest package/version identities before recording COMPLETED.
Every installer backend creates a unique app-private, copied APK set and verifies the **copy**
before receiving its paths. Cached APK replacement cannot silently alter the staged bytes.
Extra undeclared APKs, missing/truncated files, stale `.tmp` files, unsafe names, duplicate
BASE entries, inconsistent splits, invalid archives or wrong signers fail closed.

On API 36+, `PackageManager.getVerifiedSigningInfo` requires an authenticated APK
Signature Scheme v2-or-newer signer for every APK, including independent split archives.
**v1-only historical APKs cannot pass this API-36 verification path** and will be
rejected rather than silently downgrading signature-scheme strength. On API 23–35 the
PackageManager archive verifier is used; if it cannot
independently authenticate an archive or split, Aurora refuses that particular artifact rather
than inferring signer trust. The compiled APK binary manifest is parsed defensively to obtain
package identity, full 64-bit versionCode, and base/split declaration even for split-only APKs.

Installed-package signer compatibility is checked, but **Android PackageInstaller remains the
final authority on signing rotation, installation policy, and safe downgrade**. Android may
reject an older version even when the downloaded APKs are authentic for their publisher.
Neither an APK's valid signature, matching hash nor historical metadata proves Play provenance.
Aurora never substitutes a URL, signing certificate, or mirrored APK for a missing requested
historical version. Neither uninstall nor data clearing occurs automatically.

For installers that cannot install dependencies/split sets safely, fail explicitly instead of
silently dropping parts (native single APK only; microG and Aurora Services refuse unresolved
shared libraries). Shared libraries staged by the session/root/Shizuku/App Manager backends
remain separately signature and identity checked.

## Acceptance matrix

| Case | Expected result | Evidence level before new CI |
|---|---|---|
| Correct signed package and exact version | Accepted | Pure contract/JVM policy; API36 test queued |
| Wrong package, version or historical code | Refused | JVM policy and real APK test queued |
| Invalid signature, signer mismatch or signer rotation | Refused unless compatible / OS final authority | API36 test queued; physical rotation not claimed |
| Truncated/corrupt APK and Play hash mismatch | Refused before backend | API36 test queued |
| Missing split, wrong split signer, undeclared split | Refused | JVM policy / API36 test queued |
| Cancelled, stale and interrupted verification | No installation | API36 test queued; Room CAS R1/R2 remains in place |
| APK replaced after verification | Installed paths isolated in immutable snapshot | API36 test queued |
| Historic APK unavailable from Play | No mirror fallback, exact error | R3A contract; live availability not tested |
| Real installation/downgrade/data preservation | Android is final authority | R3D pending; R2D existing installation evidence |
| API23–35, ARM64, privileged and live microG backends | Fail-closed fallback, not comprehensive device qualification | Physical/device matrix remains open |

## Hosted qualification

The existing R2D API 36 workflow is extended rather than duplicated. It builds disposable,
locally signed fixture APKs for distinct versions, packages, and signers. It also flips a
SHA-256 digest byte in **each v2 and v3 signed-data record** and asserts `apksigner verify` rejects
the corrupted fixture before the Android test presents it with a newly matching download
checksum. Mutating only v2 is insufficient: Android 16 may legitimately authenticate a
still-valid v3 signer. The fixture builder therefore refuses missing v2/v3 schemes and
never regards an `apksigner` rejection caused by a single broken scheme as sufficient.
The on-device validator must independently reject the doubly corrupted fixture because its
**cryptographic APK signature** is invalid, not because the supplied hash is stale. It exercises the
production archive verifier with Android instrumentation on x86_64. Foundation CI also runs
pure Kotlin JVM policy tests, ktlint and fail-closed Python source contracts. The R2D suite
continues to exercise real PackageInstaller session commit and process restart.

**Do not mark R3B qualified until the newly pushed commit's Foundation, R1D (if applicable),
and extended R2D source/emulator results are actually green.** No production-signed APK,
Google Play provenance, ARM64 device certification or physical downgrade is asserted.
