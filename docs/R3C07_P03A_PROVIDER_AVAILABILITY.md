# R3C07 P03A — Pre-import availability and provider-state disclosures

**Scope:** truthful Settings → Import provider-selection state, all seven existing sources.

- The import Activity renders `ArtifactProviderDiscovery.status` when the source changes. P03A makes that status a typed `ArtifactProviderDisclosure.BeforeSelection`, projecting each independently missing fact: listing, exact version, downloaded bytes, APK signature, publisher authentication, compatibility, Android result.
- The local document route has no external provider listing. All other sources are *not checked* by Aurora. Availability remains **UNKNOWN**, rather than derived from a website URL, a package ID, GitHub, or a browser visit.
- No signatures, publisher identities, device compatibility, or install success are minted by provider selection. Existing `ArtifactReviewPresentation` remains the sole UI layer for verified files, based on `ArtifactApkVerifier` data; Android alone reports final install status.
- The existing APKPure persisted opt-in and per-visit alternative/F-Droid acknowledgements remain enforced. No source fallback or provider scraping added.
- Tests: five Kotlin JVM tests; executable source negative matrix with 11 mutations; targeted security CI and Android compilation on the exact commit.

- HF01 adds verified-file state awareness: during copying show in-progress, after an actual verified file show a source caveat instead of a stale NOT SELECTED label, and reset the independent preselection panel after cancel/refusal. The file-specific verified receipt remains authoritative. Four additional executable source mutations cover state transitions.

**Explicitly not qualified by this milestone:** real remote provider availability, publisher attestation, Play delivery, actual TalkBack-service navigation, real APK install/outcome, physical ARM64, release, or Android API<36.

**Next:** P03B provider-specific handoff/retry/rotation UI instrumentation with source-bound API36 receipt, then R3C08 adversarial signoff and R3D/R4/R5/R6. Do not equate targeted compilation with runtime qualification.
