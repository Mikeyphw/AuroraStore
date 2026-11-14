# R3C06 — Secure split-targeting hardening (phase 1)

**Source:** PR #9 on HF08 + R3C05. This overlay does not modify the Play evidence store, PackageInstaller, or Android storage permissions.

## Why this change

The initial `.apks`/`.apkm`/`.xapk` importer strictly bounded ZIP extraction and verified **every** APK, but then submitted all valid entries to one installation. An archive may contain multiple ABI or screen-density alternatives, so signatures and identical package/version alone do not establish an installable variant. ZIP entry names and `toc.pb` cannot be silently promoted into a trusted selector.

## Implemented safeguards

- Evaluate **signed manifest split identities**, not ZIP path names, before displaying a verified import and **again** before creating an Android install session.
- Fail closed when multiple ABI or density alternatives are present. No automatic extraction of a convenient subset or fallback to a mirror/Play artifact.
- When a single ABI qualifier is present, require it in `Build.SUPPORTED_ABIS` (with Android hyphen/underscore normalization); reject absent/unsupported device lists.
- Refuse unrecognized targeting qualifiers such as `sw600dp` until a real Android bundletool target selector is qualified.
- Permit ordinary language packs and a single density qualifier, but do **not** equate this with complete device compatibility.
- For `feature.config.*` qualifiers, require the corresponding feature split; feature dependency completeness remains **unverified**.
- `.apk` must remain a single base APK; `.aab` is still refused; OBB files remain unsupported and are never written outside private staging.
- Keep certificate, exact package/version, ZIP CRC, decompression limits, installed-signature continuity, fresh rehash and Android-owned installation consent unchanged.

## Acceptance and honest limitations

Fifteen Kotlin/JVM tests cover single-base, multiple/duplicate bases, supported/unsupported ABIs, multiple ABI/density targets, locales, unknown qualifiers, feature references and all three archive formats. Four new read-only API36 tests are wired **additively** into the existing R1D script; they do not install anything.

This is **not** a complete real-world APKM/XAPK/APKS qualification. A correct bundletool/APKM variant selector and parsed manifest `uses-split`/feature dependencies, density/locale/device-feature targeting, on-device signed positive fixtures, OBB scoped authorization and Android API23–35 apksig remain future R3C06 acceptance work. Avoid claiming that package signature validity or a successful source/compile check proves the archive is compatible or that Android installed it. Do not modify `R3B`/Play evidence to accommodate non-Play formats.


## R3C06 phase 2 — APKM/XAPK descriptor consistency (additive)

This phase adds bounded, **veto-only** APKM `info.json` and XAPK `manifest.json`
parsing. The parser uses Android's strict UTF-8 decoder and a maximum 64 KiB
index; all archive metadata entries retain the existing per-entry CRC, expanded
size, count, path and ZIP preflight limits. A contradictory archive package,
version, split index or missing APK reference causes a refusal *after* independent
signed APK identity checking, and again immediately before PackageInstaller.

APKMirror APKM bundles may include the three known `META-INF` metadata files
(`MANIFEST.MF`, `APKMIRRO.SF`, `APKMIRRO.RSA`) and `APKM_installer.url` at their
exact paths. These are copied into no executable location and never opened;
their structure/CRC is checked and discarded. **This is NOT verification of the
APKM outer JAR signature, APKMirror's identity, or publisher authenticity.**
Partial signature metadata is refused. `toc.pb` is only allowed for `.apks` and
remains opaque; the app does not interpret protobuf targeting or silently pick
an arbitrary variant. `.xapk` permits only known root metadata/icon labels; an
explicit `split_apks` index must list every archived APK and its signed manifest
split identity exactly. OBB file members *and* nonempty XAPK expansion claims
remain refused without independent authorization.

The phase deliberately does not install arbitrary multidensity/multi-ABI
archives; R3C06 phase 1 still refuses ambiguity. APKM/XAPK vendor dialects,
APKMirror outer signature authentication, full bundletool protobuf selection,
resource/feature dependencies, API23–35 signature verification, live signed
multi-split installs and arm64/physical-device qualification remain **OPEN**.

Targeted CI uses `test_r3c06_archive_descriptors.py`; the existing scheduled
R1D API36 gate adds six non-installing device methods. This is a source-level
implementation **not** full R3C06 signoff until exact-commit real hosted results.

## R3C06 P3 — signed feature dependencies and runtime acceptance (unqualified until run)

- Read compiled, **v2+ signed** `<uses-split android:name>` from each APK in the
  exact staged set. Reject absent dependencies, self/cyclic references, config
  dependencies, and dependency drift at install-time revalidation. This is a
  conservative bound, *not* independent proof of bundletool's complete targeting.
- Six new Android API36 cases wrap the **actual installed, signed debug APK** into
  synthetically constructed APKM/XAPK ZIPs. They exercise production staging,
  independent signer validation, source neutrality, descriptor contradiction,
  tampering rejection and pre-session revalidation. They are genuine signed APK
  bytes but **not** claims of downloading original APKMirror/XAPK provider files.
- The `r3c06_bundletool_matrix.py` runner uses a SHA-256-pinned external bundletool
  JAR, a real AAB and real SDK36 device spec. It builds signed APK sets with an
  ephemeral fixture key; extracts and validates SDK, ABI, density, locale and
  explicitly requested feature variants. If a fixture has no corresponding split,
  the dimension is reported **not covered**, never passed silently. This oracle
  does not grant app-side publisher authority and cannot replace the Android OS.
- The `r3c06_api36_live_install.py` acceptance runner creates a new local-only,
  short-lived PKCS12 signing key and **separate package**
  `com.aurora.r3c06.fixture`, with aapt2+zipalign+apksigner. It injects only into
  Aurora debug's private cache, calls its real `ArtifactInstallSession`, verifies
  both **Android rejection** and **user-approved Android installation**, then
  validates the installed version and certificate and uninstalls the fixture.
  It refuses to run on physical phones, if the fixture is already installed, or
  if the system confirmation/fixture label cannot be verified. It never silently
  clicks an unrelated UI or performs privileged/root installation.
- Source checks and compilation on a PR do not qualify any of the preceding
  runtime claims. The scheduled full emulator gate runs the six signed-archive
  cases; the real install gate is **opt-in** with
  `R3C06_ALLOW_LIVE_INSTALL=yes`. Bundletool requires an actual AAB and pinned
  JAR; if either is absent, the matrix remains **not qualified**.
- Outstanding for a complete R3C06/R3C08 claim: actual supplier-provided APKM
  and XAPK format corpora, independently verified feature-on-demand AAB fixtures,
  locale+hardware-specific targeting, physical device acceptance (if permitted),
  and handling OBB assets (still unsupported). No production/Play data is written.
