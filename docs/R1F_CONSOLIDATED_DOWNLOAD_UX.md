# R1F — Consolidated download UX integration

Pinned base: `99ae82a555d384c6fe0eff8bcb50df29fa1fe14a` (merged R1E).

## Scope

- Downloads list prefers the latest live Room record for the same package, retaining stable
  Paging ordering while progress, status and retries change without waiting for refresh.
- Only DOWNLOADING shows byte-transfer percentage, speed and ETA. Zero-byte rate, absent
  ETA and stale progress in QUEUED / PURCHASING / VERIFYING are not invented.
- FAILED, CANCELLED and UNAVAILABLE entries expose **Retry download** in the action sheet.
  COMPLETED or AWAITING_INSTALL with missing cached files also exposes Retry instead of
  an inert Install button. The existing DownloadHelper retry code creates a new attempt.
- Retry, cancel and clear actions from the Downloads screen pass the selected persisted
  attempt ID; if the row changed between tap and action, the action is ignored.
- 'Force clear all' requires explicit confirmation before cancelling and deleting all
  download records and cached files.
- A failure receives the FAILED semantics label rather than a misleading CANCELLED icon label.
- Additive English strings are in `strings_r1f.xml`; translations are not silently rewritten.

## Hosted acceptance

Foundation CI runs original source checks and all JVM / lint / build checks. Existing
API36/x86_64 emulator runs all 32 earlier tests plus four real Compose UI tests, including
retry tapping and non-fabricated progress. Three real emulator PNG screenshots are uploaded
as source-bound evidence; absence or bad PNG signature fails the gate.

## Explicit exclusions

No extra large-font/accessibility initiative, no live Google Play credentials,
no actual package installation, no physical-device pass, no release qualification.
R1G remains the final audit and broader acceptance milestone.
