# R3C-04 C04-01 — source-independent artifact provenance (foundation)

**Scope:** non-Play provenance and attempt identity only. This is **not an installer**,
not an Android document picker, not a live download, and not signed-byte qualification.
The roadmap's C04-02 secure picker and C04-03 verified staging are separate phases.

- `ArtifactSource` identifies how a candidate was obtained. It has no Google Play value.
  In particular, APKMirror browser handoff and opt-in APKPure are discovery claims,
  never a license, developer identity, signing certificate, or trusted Play receipt.
- `ArtifactProvenance` contains optional untrusted display-only labels. It forbids
  raw `content://` or `https://` URIs, queries and control characters to reduce
  the chance of persisting secrets. No Android URI grants are stored.
- `ArtifactAttempt` binds exact APK package, positive version, positive generation,
  and immutable source identity. Changed versions, generations or origins cannot
  advance a previous attempt.
- `ArtifactAttemptPolicy` permits only selection, private-copy digest metadata,
  cancellation and failure. **Staged bytes remain unverified** regardless of SHA-256.
  A digest of copied bytes is not independent publisher/signing or install proof.
- `VerifiedApkSet` is an intentionally **unmintable capability**, with a private
  constructor and no factory in C04-01. C04-03 must implement a real verifier
  and add its restricted evidence factory. Until then no local/mirror provider can
  claim a verified APK set or invoke a trusted install handoff.
- `ArtifactTrustTier` distinguishes unknown publisher, cryptographically valid
  unanchored signer, installed-certificate continuity, and independently anchored
  publisher identity. Naming a developer or GitHub repository is not proof.
- Existing `PlayVerifiedEvidenceStore`, Room database v16, download Worker,
  `R3bVerifiedProof` and Android Installer are left unchanged. No Play evidence
  row is ever minted by this subsystem, and no extra Room migration is needed.

## Acceptance (C04-01 only)

`python3 -B scripts/ci/test_r3c04_source_boundary.py` runs light source/negative
checks. Hosted targeted CI compiles the Android app and test sources, but does
**not execute** JVM JUnit tests; those remain a full Foundation gate requirement.
No Kotlin JVM pass is claimed for targeted CI. Local pure-Kotlin smoke tests may
be run independently before publication.
Do **not** dispatch Foundation/R1D/R2D on this PR; the periodic gate router will
run them at the configured cadence or for genuinely critical master changes.

## Next

C04-02: Android SAF open-document picker + explicit consent + bounded private
copy and cancellation, without broad storage permission or trusting file names.
C04-03: exact signed APK/split verification on *copied bytes*, installed signer
continuity, and a restricted `VerifiedApkSet` factory; an unanchored signer must
not be called an official publisher. C04-04: installer/session integration with
fresh downgrade consent, CAS and Android package manager authority.
