# R3C-03/01 — Exact Play delivery outcome model (not live-qualified)

This is the **first** R3C-03 implementation slice, not completion of R3C-03. Its
immutable, pure-Kotlin evidence reducer is tested as an independent JVM policy.
It is deliberately **not wired to DownloadWorker** in this slice, does not persist
Room evidence, does not change the UI, and supplies **no live Play proof**.

## Proof boundaries

- Request identity includes exact package name, positive Long version code,
  attempt generation, account binding, explicit Google Play source and variant.
- An event from a different version, attempt, account or variant is refused. An
  earlier snapshot must not be reused for a different request generation.
- Timeout, rate limiting, authentication, access denial and ambiguous Play
  rejection are **not** evidence that an exact version is unavailable.
- Only an explicit, authoritative exact-version delivery refusal may produce
  `EXACT_VERSION_UNAVAILABLE`. No existing Play error has been certified as such.
- Resolving URLs proves neither bytes nor signing identity. Bytes received are
  still not a verified set. `VERIFIED_SET` requires the staged transition after
  an event emitted **only following R3B** validation of the exact APK set.
- SDK/ABI/split and install outcomes must match exact verified APK manifests;
  no current-listing metadata can fill gaps. Android remains installation authority.
- Negative security mutations and JVM state transitions run on GitHub Actions.

## What is still required to close R3C-03

The worker integration must map **real** gplayapi exceptions conservatively,
key all results to the persisted Room/WorkManager generation and current account,
and only record verified outcomes after the exact R3B staging gate. A stale
worker or cancelled/replaced request must not overwrite current UI evidence.
Add hosted API36 fixture tests for worker transitions and stale results.
**Never** map generic `AppNotSupported`, `AppRemoved`, timeout, HTTP 429 or
`AppNotPurchased` to confirmed version unavailability without explicit Play
version-bound proof. Do not trigger network probes when opening Exodus history.

Next: R3C-03/02 worker and Room integration; then R3C-04 secure local import,
R3C-05 provider handoffs, R3C-06 archive/split parsing and R3C-07/08 UX and
hosted acceptance. Synthetic fixtures do not prove real historical Play APK
availability, physical-device installability or signed release qualification.
