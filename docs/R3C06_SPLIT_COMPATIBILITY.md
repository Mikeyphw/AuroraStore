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
