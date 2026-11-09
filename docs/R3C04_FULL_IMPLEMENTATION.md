# R3C-04 C02–C08 — conservative manual import and source handoff

This consolidated feature extends the merged C04-01 independent origin model. It
**does not modify Google Play delivery, `PlayVerifiedEvidenceStore`, Room v16, or
R3B's Play hash and installer gates**. It uses the existing independently tested
`BinaryApkManifest` and `ApkSetPolicy` identities for a separate local
`PackageInstaller` session.

## C04-02: working system-document picker

Settings → Import APK or bundle uses SAF `OpenDocument`, without requiring a new
broad-storage permission. Content is copied into a random private cache directory
before being inspected; no `content://` URI, authenticated link, or secret is
persisted. A changed/cancelled request cannot authorize a new install. User-facing
status separates received bytes, valid archive signer, unknown publisher, and OS
install outcome. `onDestroy` cancels in-progress work and deletes private temp
bytes. An OS-owned committed session survives activity destruction.

## C04-03/C04-04: independent signed-byte + OS install gate

- Bounds-checked Android manifest parse for **each** APK via `BinaryApkManifest`.
- Same package/version/signer across a unique base and all splits enforced by
  `ApkSetPolicy`, plus unique manifest split identity and basic ABI rejection.
- SHA-256 read from *copied bytes*, rechecked before session write; Android's
  verified v2+ archive signer API on API 36 and conservative package-manager
  archive signature fallback below API 36.
- Installed certificate continuity checked where an installed package exists.
  A mismatch blocks automatically, even if the user selects all consent controls.
- New installs show **unanchored publisher identity**, regardless of a valid APK
  signature or a website/repo label. Both explicit install and unanchored-publisher
  consent are required. Older versions require a **separate** downgrade consent;
  there is no uninstall/data deletion, root install bypass or claim of guaranteed
  downgrade support.
- Android `PackageInstaller` owns the final decision. Requests require system
  user action where the API supports it. Result receiver binds session id and
  generation to a private saved receipt; unknown/stale callbacks are ignored.

## C04-05: legitimate source/discovery handoff

Official developer HTTPS URL, GitHub Releases, APKMirror, F-Droid and APKPure are
**manual browser handoffs only**. All external links are validated HTTPS with
no user info, nonstandard ports, query strings or fragments. GitHub, APKMirror,
F-Droid and APKPure require the exact expected hosts. APKPure opt-in defaults to
false and is stored locally. There is no scraping, API abuse, content redistribution,
automatic fallback, account transfer, or Play evidence forgery.

**Not independently verified:** GitHub account ownership, publisher certificates,
F-Droid upstream vs F-Droid signing, and developer website ownership. An HTTPS
label must not become a verified publisher anchor. File picker always imports
with the same conservative signer/consent gate. F-Droid signing can legitimately
be different, which may prevent upgrading an installed app.

## C04-06: archive handling

- `.apk`, `.apks`, `.apkm`, `.xapk`: bounded extraction of all `.apk` entries into
  generated flat, private filenames, never archive paths. All APKs must pass
  per-file signer and manifest validation. Archive metadata never grants trust.
- Reject empty/unknown/traversal/backslash/control/duplicate paths, unexpected
  extensions, excessive decompression ratios, excessive counts and payload size.
- Reject `.aab` outright (not directly installable).
- XAPK files containing OBB expansion assets are **not supported** and fail
  closed until independent OBB storage authorization/provenance is implemented.
  ZIP entries are never materialized as symbolic links or outside app-private
  staging, so symlink mode bits in a ZIP cannot cause a filesystem escape.
- Incomplete configuration and device features may still be rejected by
  PackageInstaller. The app cannot infer guaranteed compatibility merely from
  a filename, mirror listing, or one APK's manifest.

## C04-07: honest UI

Settings entry, provider picker, optional browser page, APKPure opt-in, system
file picker, cancel control, private byte/signature proof, independent publisher
and installed-certificate status, exact package/version, SHA-256, downgrade warning,
and native Android installation result. Normal-sized text, no debug UI.

## C04-08: acceptance and limitations

`test_r3c04_full_import.py` runs source/negative checks during PR Targeted CI.
New JVM test classes cover trust/consent, URL sanitization, archive path and
compression caps. The existing R1D emulator script is extended additively to execute exactly six
new device staging tests at the *scheduled/manual full gate*, without a new
workflow or automatic per-PR emulator run.
New Android instrumentation fixtures exercise bounded staging,
zip traversal, OBB refusal, decompression bombs and cancellation. **Targeted CI compiles but does not execute the new Android instrumentation.**
Full device execution remains an explicit R3C-08 qualification gate; signed
fixture installation/mixed-signers/real-world APKM and XAPK matrices and device
ABI/locale/feature-split matrix require dedicated hosted/physical acceptance.

A successful source/targeted compile does **not** certify: downloaded APK publisher
identity, complete source-website integrations, every APKM/XAPK dialect, OBB import,
all device split compatibility, signing lineage, live Google Play availability,
paid/protected downloads, physical-device migration, or signed release readiness.

## Maintenance

All imported archives are untrusted. Provider URLs are optional, have no
privileged access to Play, and are never auto-fetched. Do not weaken source
identity or signature checks to expand supported formats. Keep native Devtool
schema-v2 overlay commits, `gh` push/PR watching, targeted CI per overlay, and
the five-overlay/manual high-risk full gate policy.
