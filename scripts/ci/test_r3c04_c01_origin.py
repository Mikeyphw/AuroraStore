#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""HF06: check live C01/C03 contracts for stale assumptions, trust-claim upgrades and Play crosswrites."""
from pathlib import Path
import re
root=Path(__file__).resolve().parents[2]
base=root/'app/src/main/java/com/aurora/store/data/artifact'
play=root/'app/src/main/java/com/aurora/store/data/room/play/PlayVerifiedEvidenceStore.kt'


def read(p):
    if not p.is_file():raise SystemExit('R3C04_C01_HF06_REFUSED: missing '+str(p))
    return p.read_text()

def need(ok,reason):
    if not ok:raise SystemExit('R3C04_C01_HF06_REFUSED: '+reason)

origin=read(base/'ArtifactOriginBoundary.kt')
provenance=read(base/'ArtifactProvenance.kt')
verified=read(base/'ArtifactApkVerifier.kt')
ui=read(base/'ArtifactReviewPresentation.kt')
activity=read(base/'ArtifactImportActivity.kt')
install=read(base/'ArtifactInstallSession.kt')
legacy=read(base/'VerifiedApkSet.kt')
play_source=read(play)
model=read(root/'app/src/test/java/com/aurora/store/data/artifact/ArtifactOriginBoundaryTest.kt')
legacy_tests=read(root/'app/src/test/java/com/aurora/store/data/artifact/ArtifactAttemptPolicyTest.kt')

for name in ('GOOGLE_PLAY','DEVELOPER_RELEASE','GITHUB_RELEASE','LOCAL_IMPORT',
             'APKMIRROR_BROWSER','FDROID_BROWSER','APKPURE_OPT_IN_BROWSER'):
    need(re.search(r'^\s*'+name+r'\s*[,\n]',origin,re.M) is not None,'missing explicit origin '+name)
for name in ('GooglePlayVerified','OfficialDeveloperVerified','GitHubReleaseVerified'):
    need(re.search(r'class '+name+r' private constructor\(\)',origin) is not None,
         'authentication capability is forgeable or missing: '+name)
need('GOOGLE_PLAY' not in provenance and 'get() = false' in provenance,
     'non-Play provenance acquired Play authority')
need('fun family(source: ArtifactSource)' in origin and
     'ArtifactSource.GITHUB_RELEASE -> ArtifactOriginFamily.GITHUB_RELEASE' in origin and
     'fun claimOnly(source: ArtifactSource)' in origin and
     'return ArtifactOriginAssurance.UNVERIFIED_SOURCE_CLAIM' in origin,
     'browser source selection must remain claim-only')
need('private constructor(' in origin and
     'fun fromVerifiedImport(imported: ArtifactApkVerifier.VerifiedImport)' in origin and
     'require(imported.signerSha256.isNotEmpty()' in origin and
     'apks.map { it.sha256 }' in origin and
     'attempt.attemptGeneration' in origin and
     'imported.totalApkBytes' in origin and
     'imported.signerMatchesInstalled != false' in origin,
     'verified independent evidence missing field/signature/size/identity checks')
need('error("C04 cannot mint unknown or authenticated publisher evidence")' in origin and
     'val isPlayEvidence: Boolean get() = false' in origin and
     'val hasPublisherAttestation: Boolean get() = false' in origin,
     'unanchored source could mint authenticated Play or publisher proof')
need('getVerifiedSigningInfo(' in verified and 'BinaryApkManifest.read(' in verified and
     'ArtifactPrivateStager.sha256(' in verified and
     'val generation = SecureRandom().nextLong()' in verified and
     'class VerifiedImport internal constructor(' in verified,
     'stale model or real C04-03 verifier regressed')
need('private constructor(' in legacy and 'companion object' not in legacy,
     'legacy unmintable marker unexpectedly exposed')
need('ArtifactIndependentEvidence.fromVerifiedImport(verified)' in activity and
     'receipt.attemptGeneration' in activity and 'receipt.apkSha256' in activity and
     'receipt.signingCertificateSha256' in activity,
     'user review detached from actual verified import receipt')
need('ArtifactIndependentEvidence.fromVerifiedImport(imported)' in install and
     'ArtifactApkVerifier.revalidateForInstall(' in install and
     'key(sessionId, "origin_family")' in install and
     'key(sessionId, "apk_sha256")' in install and
     'key(sessionId, "generation")' in install and
     '"INDEPENDENT_NON_PLAY"' in install and
     'session.commit(pending.intentSender)' in install,
     'OS session receipt lacks independent exact provenance or revalidation')
need('fun consentNeedsUnknownPublisher(f: VerifiedFacts): Boolean = f.installedVersion == null' in ui and
     'attestation unavailable in C04' in ui and
     'f.apkSha256.forEachIndexed' in ui,
     'unverified publisher enum could hide consent or evidence from UI')
need('PlayExactVersionOutcomePolicy.Source.GOOGLE_PLAY' in play_source and
     'proof: R3bVerifiedProof' in play_source and
     'key.attemptGeneration' in play_source and
     'database.withTransaction' in play_source,
     'existing Play-only evidence gate changed or missing')
for bad in ('PlayVerifiedEvidenceStore','PlayDeliveryEvidenceDao','PlayExactVersionOutcomePolicy',
            'R3bVerifiedProof','DownloadDao'):
    # The independent receipt class must not import or call the Play store.
    need(bad not in origin, 'independent origin model references Play evidence authority: '+bad)
need(model.count('@Test') >= 11 and legacy_tests.count('@Test') >= 14,
     'negative tests missing or stale')
need('assertThat(r.isPlayEvidence).isFalse()' in model and
     'forgedVerifiedPublisherTierIsRejected' in model and
     'githubBrowserClaimNeverBecomesAuthenticatedReleaseProof' in model,
     'source/cryptographic evidence separation not tested')
print('R3C04_C01_HF06_SOURCE_PASS: independent delivery families, explicit unmintable anchors, exact signed-byte receipt, generation binding, Play noninterference')
