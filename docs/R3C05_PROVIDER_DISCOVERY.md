# R3C05 — Explicit multi-source discovery and manual handoff

## Delivered in this overlay

- Seven clearly differentiated provider choices in Settings → Import and verify APKs: Google Play, local Android document picker, user-entered developer HTTPS page, GitHub Releases page, APKMirror, F-Droid and APKPure.
- Play is a **separate listing-only link**, constructed from a validated package ID. It **does not** enter the non-Play artifact-source model, claim an exact historical release or copy Play verified receipts. Play's actual installer/delivery remains the existing R3B/C03 system.
- Developer HTTPS and GitHub Releases are **browser pages only**, not authenticated developer bindings; no automatic release downloading, invented assets or publisher signing evidence. A valid GitHub org/repository name does not establish official ownership.
- APKMirror is restricted to its official HTTPS pages and requires an **explicit one-visit alternative-source acknowledgement**. No scraping/API/cloudflare bypass or direct-link guesses.
- F-Droid has the same per-visit consent and an additional FOSS/signing-identity acknowledgement. A repackaged/re-signed F-Droid build can fail installed-signature continuity and must not be installed over a different signer.
- APKPure is disabled by default and requires both a persistent opt-in and a *new, per-visit* alternative consent; no automatic fallback to mirrors for failed Play auth/quota/network responses.
- Source navigation is user-initiated. A successful browser open is not evidence of a specific download. The subsequent file must still be selected using Android SAF, copied privately, authenticated with API36 signing checks, and explicitly confirmed for installation.
- Ephemeral browser attribution expires after ten monotonic minutes, is invalidated on source change / URL edit / opt-in revocation, and is demoted to LOCAL_DOCUMENT if the separate alternative-visit acknowledgement is revoked. The receipt never stores raw browser URLs, document URIs, tokens, or account data.
- Existing Google Play proof store, R3B signed-set verification, Room migration, installed-signer continuity, and Android PackageInstaller remain unchanged.

## Limits and outstanding qualification

**No independently authenticated publisher registry is currently provided.** There is no secure automatic way to prove that a user-entered developer host or GitHub repository belongs to the real publisher of an arbitrary Android package; the authenticated developer and GitHub provenance capability remains unmintable. Such pages and all selected files are presented as **unverified publisher claims**, even after APK signature validation. Real cross-checked developer attestations and policy-compliant release metadata must be introduced and tested separately before representing those sources as verified or automating asset downloads.

No direct APKMirror/APKPure download, paid/protected APK redistribution, general Play mirror fallback, mirror availability checks, F-Droid license crawler or anti-bot circumvention is implemented. No device install or live provider response is claimed by source compilation.

## Acceptance matrix

| Lane | Evidence required |
|---|---|
| Source policy | `python3 -B scripts/ci/test_r3c05_source_handoff.py` and inherited `test_r3c04_full_import.py` PASS |
| Kotlin/JVM | `ArtifactProviderDiscoveryTest`, expanded `ArtifactHandoffClaimPolicyTest`, and existing URL/source tests PASS |
| Hosted Android | Existing Aurora Targeted CI app/androidTest compilation at exact PR HEAD PASS |
| Android device | The existing R1D API36 runner now requires all 3 `ArtifactProviderDiscoveryDeviceTest` tests, plus existing C04 import/signing/consent tests, and verify real browser unavailable, cancel, picker return and rotation behavior |
| Manual provider QA | Test a real developer site/GitHub release page, APKMirror, F-Droid and APKPure opt-in/refusal with the platform browser (no scraping); verify the source remains untrusted |
| Product completion | Independently authenticated developer/GitHub provenance and provider-specific live availability can be marked complete only after real evidence exists |

No automatic Foundation/R1D/R2D full gate or PR merge is authorized here. The **entire** previously saved R3C05–R6 roadmap is carried verbatim as context in the delivery ZIP.
