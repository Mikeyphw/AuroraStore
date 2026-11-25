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

## C04-02/03 HF01 security audit corrections

- **SAF names are untrusted.** Provider-returned filenames are sanitized before
  display/provenance construction. Invalid labels are discarded without crashing.
- **Stale cancellation callbacks are refused.** Every UI job carries a request
  serial and its cancellation token; old work cannot overwrite newer review UI.
- **Archive bounds are enforced while enumerating** ZIP entries, not after
  materializing the entire directory listing. Compression ratios are checked
  without integer rounding gaps or multiplication overflow.
- **Independent signing verification is API-36-only for now.** On API 23–35,
  `PackageManager.getPackageArchiveInfo()` by itself is not a sufficiently
  strong v2+ signing-block verifier for arbitrary standalone APK/split sets.
  These imports now fail closed until an audited `apksig` validation adapter is
  available. This is an explicit compatibility limit, not silent "verification".
- **Exact-session-byte integrity:** the same stream written to Android's
  PackageInstaller is hashed while writing and must match the digest attested
  by the private staging verifier before the OS session can commit.
- Static and JVM tests do not independently prove full archive/signer safety.
  The periodic hosted API36 gate additionally exercises real signed APKs and
  invalid/corrupt bytes; full physical-device acceptance is still separate.


## C04 HF02 audit (C04-02/03/04)

The consolidated pre-merge hotfix incorporates C04-02/03 HF01 safeguards and C04-04
independent OS-session checks. Explicit installation consent is passed into
`ArtifactInstallSession` (never hardcoded). A currently installed package needs
positive installed signer continuity; missing proof cannot be overridden by the
unknown-publisher checkbox. After consent, staged APK manifests, signing blocks,
byte digests, and the installed package/version/signing state are rechecked before
creating an OS session. Android still decides whether an installation/downgrade
is allowed. Receipts are keyed by system session ID and generation, with terminal
callback replay rejected; the OS-supplied session identifier must match.

The existing periodic API36 lane now runs five further non-installing cases for
revalidation, consent failure and post-verification private-byte mutation. This
is NOT a demonstrated complete install or downgrade on physical devices.


## C04-05 HF03: browser handoffs and opt-in provenance audit

GitHub Releases accepts canonical release listings, latest and tagged release **pages**; it
does not pass a direct asset URL to an embedded downloader. APKMirror and F-Droid
accept only official page hosts, including the F-Droid language-prefixed package
path. The developer URL is always a user-typed HTTPS browser destination, **not**
independently authenticated publisher identity. APKPure remains disabled by default
in the UI and requires a checked opt-in before its browser page is opened. Revoking
that opt-in also clears prior handoff context.

Only a successful external browser launch establishes temporary, untrusted display
attribution to the chosen provider host. The picker selection must match both the
originally opened URL and selected provider; any edit, switch, missing launch or
revoked APKPure opt-in falls back to **LOCAL_DOCUMENT**. No URI, redirect URL or
authentication token is stored in artifact provenance. Source attribution never
changes signer verification, publisher trust, PackageInstaller consent, Play-only
evidence or staging requirements.

`test_r3c04_c05_handoff.py` and the two JVM suites cover wrong hosts, lookalikes,
unsafe URL syntax, altered selection, revoked opt-in and failed attribution. These
are *not* browser UI automation nor proof of downloaded file origin. Hosted targeted
CI must compile the changed Android code.


## C04-06 HF04 — bounded ZIP structure and checksum acceptance (PR #9)

This security audit found that the prior `ZipFile` opened/indexed the central directory
**before** the existing `MAX_ITEMS` loop. It also skipped extraction of metadata
without reading it, so declared metadata CRC/actual-size inconsistencies were not
verified. The periodical staging gate required `6 tests` while the pre-HF04 test class
already contained **seven**. These discrepancies are now addressed in the source.

- A bounded EOCD/central-directory preflight happens before `ZipFile` indexing. It
  refuses more than 128 members, ZIP64/multivolume/self-extracting ZIPs, unsupported
  encoding/method/encryption flags, symlinks/special files, malformed local vs.
  central headers, name ambiguity, overlapping payloads, extra trailing bytes,
  and disallowed entry types. Non-ASCII member names are explicitly unsupported.
- APK bytes receive a **separate archive CRC-32 verification** during bounded
  staging, in addition to SHA-256 and later Android signing verification. Every
  opaque metadata entry is bounded, fully read and checked against declared CRC
  and expanded size before it is ignored. Aggregate expanded bytes are capped.
- `toc.pb` is accepted only as inert, checksummed bundletool metadata: the parser
  **does not select a device-appropriate split set** from toc.pb and never treats
  it as signer/provenance evidence. The existing APK set verifier and Android
  installer remain the authority for all staged APKs; a universal `.apks`
  package with incompatible variants may still be refused. Third-party APKM/XAPK
  variants are not comprehensively qualified. OBB expansion files remain refused.
- The R1D API36 staging runner now requires **13 actual tests** (previous 7 plus
  6 new cases), not the stale six-test expectation. A new JVM ZIP-structure
  suite and targeted source contract cover the new guardrails.

**Qualification boundary:** pure-Kotlin preflight smoke and source checks are not
Android runtime evidence. The targeted Android build compiles the instrumentation;
the milestone R1D emulator lane must execute all 13 staging tests on the exact
commit. No real-world APKM/XAPK dialects, all ABI/locale/feature splits, or
PackageInstaller end-to-end acceptance are claimed from this hotfix.

## C04-07 HF05 — user-facing verification and consent audit

HF05 folds the unapplied C04-06 HF04 archive fix with a separate C04-07 UI/receipt
hardening into **one atomic native Devtool overlay** on the same exact PR #9 head.

- Settings explicitly navigates to *Import and verify APKs*. The local-only route
  remains non-exported; browser choices remain manual claims, not authenticated
  download integrations or Google Play evidence.
- The verification panel labels the state **VERIFIED APK FILES — NOT INSTALLED**,
  gives package/version, source claim and unverified reference, original selected
  file SHA-256, signing certificate fingerprints, APK count/bytes, installed
  signer continuity and a conservative compatibility warning.
- Valid signatures do not establish publisher identity. Existing-signer continuity
  is distinguished from verified publisher identity and does not falsely mint a
  developer anchor. No success badges are assigned to mere browser/source claims.
- A file-specific install approval is always required. Unknown-publisher consent
  is shown only for unanchored fresh installs; a separate downgrade consent is
  shown only when the installed version exceeds the selected version.
  Mismatching/unknown installed signatures remain non-overridable blockers.
  The install button cannot be enabled until current-attempt blockers clear.
- File replacement, cancellation, rotation/activity teardown and import failure
  invalidate prior UI consent. The existing installer **revalidates staged bytes,
  manifests, installed signing identity and exact streamed SHA-256** before commit.
- A distinct **Android installation outcome** panel displays the last private
  per-session receipt (source label, signer/source SHA-256, APK count/size, consent
  booleans, status), with an explicit refresh action. Pending approval/session
  submission says *NOT confirmed* and cannot masquerade as Android-reported success.
- Edge-to-edge content receives system bar insets; the existing scrollable
  normal-size layout and English controls are preserved.
- JVM presenter negative tests and three read-only API36 activity instrumentation
  cases were added to the existing periodic emulator runner. They are not real
  installation tests and have not been run on API36 yet.

**Still required:** hosted targeted Android compilation on exact HF05 HEAD,
periodic API36 instrumentation (including 13 archive tests + 3 UI tests),
real installation consent/success/denial/restore/replay, source browse/SAF
screenshots, ABI/locale/split compatibility, signed APKM/APKS/XAPK fixture
matrix, physical-phone acceptance and release qualification. No automatic
full-gate run or PR merge is performed by this delivery.

## HF06 — C04-01 exact provenance and trust boundary (consolidated with HF04/HF05)

The C04-01 foundation was merged in PR #8. HF06 audits its original promise
against the later real C04-03 verifier and includes the unapplied C04-06 HF04
and C04-07 HF05 changes in the same source-pinned PR #9 overlay.

- `ArtifactOriginBoundary` explicitly separates Play, developer-release **claims**,
  GitHub-release **claims**, local documents, APKMirror, F-Droid and opt-in APKPure.
  Source-family classification alone has no verifier or publisher authority.
- Reserved authenticated Play/official-developer/GitHub identities cannot be
  constructed by a browser handoff. They require actual future attestation;
  C04 implements **no authenticated official developer or GitHub downloader**.
- `ArtifactIndependentEvidence.fromVerifiedImport` binds the actual C04-03
  verified APK hashes and signing fingerprints, exact package/version and
  random attempt generation to a non-Play source. Installed signer continuity
  is reported but never equated with publisher or Play authenticity.
- The import review and private Android session receipt expose per-file hashes,
  origin family and attempt generation. No user-supplied URL, filename or
  claimed trust enum can mint Play verification.
- Unknown-publisher consent remains visible for all new independent imports;
  caller-supplied VERIFIED_PUBLISHER_IDENTITY must not silently hide the control.
- `VerifiedApkSet` remains a historical C04-01 unmintable placeholder; the
  real API36 `ArtifactApkVerifier.VerifiedImport` is the live proof producer.

The existing `PlayVerifiedEvidenceStore`, R3B verifier, C03 Room schema, Play
worker and download-account checks remain unchanged. Targeted compilation,
source contracts and isolated JVM tests do not prove source authentication,
physical-device behavior, API36 installation or Play delivery.

## C04-02 HF07 — SAF picker, private staging and cancellation audit

- The previous picker path left an active verified import in private cache when a
  replacement picker was launched and then cancelled. HF07 revokes/discards the
  previous attempt **before** opening the Android document picker, clears consent,
  and invalidates any earlier background serial. A cancelled/failed picker does not
  restore the former review or private APKs.
- Only `content:` URIs returned by the picker are accepted by the activity. The
  provider `DISPLAY_NAME` is treated as an untrusted format hint and queried on a
  background worker; it must be a bounded basename without URI syntax, slash,
  question mark or control characters. SAF provider metadata is *not* source proof.
- Each copy owns a one-shot cancellation lease. The close of an active provider
  stream runs on a dedicated close worker so the main thread does not wait on
  provider I/O. Cancellation is also polled before/after reads, metadata streams,
  digesting and successful staging. Private files are deleted on exceptions.
- This intentionally does **not** claim to interrupt an arbitrary provider that
  indefinitely blocks inside `openInputStream` or metadata query. Such providers
  remain a compatibility/liveness risk; no main-thread resolver call is made.
- Four more read-only API36 staging cases cover a self-owned content URI, denied
  provider, a mid-copy cancellation and an already-cancelled lease. The periodic
  emulator runner now requires **17** staging tests, not the old 13. Three C04-07
  UI tests remain separate. JVM cancellation and picker-policy tests are additive.
- Pending prior commit Android sessions still belong to the OS; cancellation of
  this screen is **not** equivalent to a PackageInstaller rollback. No Play evidence
  or account state is written by the SAF importer.

**Not yet qualified:** third-party SAF provider revocation mid-read, actual system
picker UI instrumentation, rotation/restart while a provider blocks, API36 runtime
and physical-device install consent. These are acceptance gates, not local PASS.


## HF08 C04-03 manifest, split and signing identity hardening

Before presenting a verified local import, each APK must expose exactly one
`AndroidManifest.xml` entry, have a canonical manifest package/version and a
nonempty, nonambiguous feature/config split name (when a split attribute exists).
The base APK must also yield an Android `PackageInfo` whose package and full
`longVersionCode` match the compiled manifest; when Android exposes standalone
split archive info, any inconsistent split package/version is rejected.
A missing standalone split `PackageInfo` is **not** treated as platform proof;
the signed compiled manifest and split-set policy remain mandatory.

Unlike the more permissive shared Play/R3B rotation compatibility routine,
**non-Play replacement** requires an exact match against the installed *active*
signer set. A certificate appearing only in signing history is **not** proof of
Android-authorized update/rollback lineage capabilities. Such cases fail closed
until a genuine capabilities-aware platform test is available. This deliberate
compatibility restriction may reject some legitimate key-rotated APKs. No change
is made to Play's verifier, database or evidence flow.

The API36 periodic lane is adjusted from three to seven signed-identity device
methods (one real signed APK positive, one unsigned failure, one staged mutation,
plus four identity-policy/platform-archive checks). These new tests are **not**
cryptographic multi-split or key-rotation qualification. Real signed split
fixtures, lineage capability matrices, device ABI/locale split selection, and
full PackageInstaller runtime acceptance remain open in R3C-08/R3C-06.
