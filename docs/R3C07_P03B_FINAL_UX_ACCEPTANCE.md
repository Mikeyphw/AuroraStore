# R3C07 P03B — provider journeys, truthful retries, consent and Android UI proof

This fold-in finishes the **implementation** of the R3C07 planned import/review UX
at the existing Settings entry and integrates source-neutral, manual-only
history/version reference. It does not convert a browser visit into a signed,
version-bound provider availability proof. The real backend remains in C04/05/06.

## User experience

- Provider chooser remains explicit (Google Play listing, local SAF picker,
  developer site, GitHub release, APKMirror, F-Droid and opt-in APKPure); no
  programmatic browser download, scraping, automatic fallback or paid APK bypass.
- Separate listing, exact-version UNKNOWN, downloaded bytes, verified APK,
  publisher identity, compatibility and Android install outcome remain visible.
- Optional version-code **reference** matches independently verified file bytes;
  it is not a live query. Mismatch/overflow blocks the installation button
  even if the other individual consents are checked. Editing after verification
  invalidates the selected bytes and all prior consent.
- Invalid and inaccessible files show bounded English
  failure categories, never raw URI, provider credentials or thrown exception
  strings. Retry is an explicit Android document-picker action; canceled
  attempts discard previously selected bytes/consent and never auto-retry.
- Activity recreation drops old verified consent. User provider switch and
  request-serial cancellation still revoke worker output. Scroll and readable
  text remain usable at large fonts and in real landscape orientation.
- Technical receipt still exposes exact independent file hashes and signer
  certificate fingerprints. Final Android success is exclusively from the
  PackageInstaller session callback, not the source picker or review UI.

## Qualification (not automatic)

- R3C07 P03B: five real hosted API36 UI tests using signed APKs returned by
  the existing debug content provider, plus *three real PNG screenshots* saved
  by UiAutomation and read from Aurora's private files via `adb run-as`. R1D
  source/run-bound receipt validates five exact test events, the Android
  terminal result, actual PNG magic/IHDR/IEND/dimensions, unique screenshots,
  and SHA-256 of every byte. Host refuses failure or missing screenshot.
- P03 genuine TalkBack and P04 actual signed-fixture Android DENY/ACCEPT remain
  separate **opt-in-only** gates. P02B node semantics never count as real TalkBack.
- Only a new full exact-SHA targeted CI 3/3 and default API36 R1D upload can
  qualify P03B. JVM and source tests do not replace device evidence.
- No claim of real provider historical availability, publisher identity, Play
  provenance, physical ARM64, production dynamic feature or release signing.

## After R3C07

R3C08 adversarial signoff, R3D historical installs, R4 Material3 Expressive,
R5 version filtering and R6 release hardening remain independent milestones.
The two verbatim canonical roadmaps are delivered with the self-executing ZIP.
