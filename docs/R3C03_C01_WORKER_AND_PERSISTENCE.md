# R3C-03 C01 — Attempt-scoped Google Play evidence

This source-pinned Devtool overlay wires real `DownloadWorker.resolveFiles()` results to
R3C-03/01's conservative immutable evidence policy and persists them in Room v16.
The migration **does not delete or reset existing downloads/accounts**.

Only an exact-version Play *request* that returns a nonempty file list may produce
`URLS_RESOLVED_NOT_VERIFIED`. Rate-limited (HTTP 429), server (5xx), network, authentication and ambiguous Play
refusals produce distinct non-unavailability states, **never** `EXACT_VERSION_UNAVAILABLE`.
Transient Play quota and server failures also retain WorkManager backoff/retry behavior.

`PlayException.AppNotSupported` is deliberately not an authoritative version-scoped
unavailability proof and now uses a noncommittal user-facing message.

Room evidence is keyed by package with current version, attempt generation, selected
account HMAC-SHA256 fingerprint and a device/offer/actual-anonymous-or-authenticated
resolution-lane variant. The raw account ID may be an e-mail
address and is never persisted; the 256-bit HMAC key is generated locally and stored in
private app preferences. It is not a Play credential; fingerprint tests reject
undersized keys and cross-account reuse. The account selection is checked against
Room for each write, but a supplier can still refresh credentials between calls;
C01 does not claim that the Play server authenticated that specific account. Its transactional CAS refuses stale or cancelled
workers, account changes and conflicting same-generation identities. No raw Play URL,
credential, e-mail, or APK claim is stored.

A URL resolution is not a verified APK set. The existing R3B verifier remains
unmodified and authoritative; recording verified sets is left to C02. This C01
policy does **not** make history a Play archive or change downgrade consent.

The source contract, 23 source-security mutation tests, and offline SQLite CAS
fixture run in Foundation CI. The JVM suite includes 12 typed Play failure tests
and five account-pseudonym tests. The SQLite fixture tests SQL semantics, not
Android Room migration runtime or process-death behavior. Android
Gradle and JVM tests run **only on GitHub Actions**. C01 is not qualified until
all six Foundation jobs pass, and Room schema v16 should be checked against the
host-generated Room schema before production rollout.

Hosted emulator/real Play availability and verification-to-install lifecycle are
C02 gates; fixture-based emulator checks cannot prove production Play availability.
