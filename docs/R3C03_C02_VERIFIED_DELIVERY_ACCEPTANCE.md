# R3C-03 C02 — verified APK evidence and installer callback qualification

## Evidence authority

The existing C01 Room result DAO is unchanged. It is permitted to store
`URLS_RESOLVED_NOT_VERIFIED` only after a nonempty *actual* Play delivery
response. C02's separate store moves it to `BYTES_DOWNLOADED_NOT_VERIFIED`
only after the production worker has transferred the whole file list and won
the generation-scoped `VERIFYING` CAS. The step from bytes to `VERIFIED_SET`
requires `R3bVerifiedProof.verify()`, whose private constructor is reached
only after `ApkSetVerifier.verify()` authenticates and checks the exact
APK package/version/signers. Room additionally checks the current generation,
account selection, variant, file count and existing state in one transaction.

Installer `STATUS_FAILURE_ABORTED` is a cancellation, not an app failure. A
non-aborted installer callback may write `INSTALL_FAILED` only *after* the
existing attempt-scoped installer CAS accepted the callback and the evidence
row previously contained this attempt's `VERIFIED_SET`. The account fingerprint
is recomputed from the app-private HMAC key and never persists an e-mail,
Play token, URL, or certificate secret.

The current legacy `DownloadWorker` can start with prefilled URLs. C02 does
not fabricate `URLS_RESOLVED_NOT_VERIFIED` for those URLs. A retry that did
not itself resolve Play URLs may successfully download or install but remains
`UNKNOWN` (no misleading verified-Play claim).

## Boundaries and limitations

- A verified APK does **not** certify Google Play provenance cryptographically.
  The evidence chain is a local record that the URLs came from Play's authenticated
  or anonymous delivery response and that the signed downloaded bytes passed R3B.
- Debug loopback fixtures cannot mint Play evidence.
- `EXACT_VERSION_UNAVAILABLE` is deliberately not produced by generic HTTP
  failures, missing files, geo/device restrictions, or any C02 code path.
- `SDK_INCOMPATIBLE` is emitted only when the production R3B verifier
  succeeded and Android's archive parser reports a strictly higher `minSdk`
  from that exact, digest-rechecked BASE APK. Missing/unparseable manifest
  data remains unknown, not incompatible. Such a download is not installed.
- `ABI_OR_SPLIT_INCOMPATIBLE` requires trustworthy verified split/ABI proof;
  C02 deliberately does not infer it from the latest Play listing, a filename,
  or a generic `STATUS_FAILURE_INCOMPATIBLE`. The latter is recorded as
  `INSTALL_FAILED` only when a verified attempt's genuine callback is accepted.
- Source guards, synthetic SQLite CAS checks, JVM unit tests, and an API 36
  in-memory Room device suite are not live Play availability proof or a
  physical-device qualification.

## Qualification

The Foundation source gate runs C02 source and negative mutation checks.
The existing API-36 hosted emulator suite is extended with eight C02 Room
transaction tests and a source-bound receipt. The separate existing R3B
verifier suite remains the authority for signed APK acceptance. All CI is
hosted on GitHub Actions; the Termux overlay apply runs no local Gradle.

A complete Room v16 migration/schema export and live exact Play delivery
probe remain separate acceptance checks. In particular, no v16 schema is
handcrafted to pretend to be output from Room's schema generator.
