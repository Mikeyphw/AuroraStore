#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R3D P01/P02 source safety: exact user reference, downgrade and CI host gates."""
from pathlib import Path
import re
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
ART=ROOT/'app/src/main/java/com/aurora/store/data/artifact'
H=ART/'ArtifactHistoricalVersionPolicy.kt'
D=ART/'ArtifactDowngradeSafetyPolicy.kt'
DECISION=ART/'ArtifactImportDecision.kt'
JOURNEY=ART/'ArtifactImportJourney.kt'
UI=ART/'ArtifactImportActivity.kt'
REVIEW=ART/'ArtifactReviewPresentation.kt'
SESSION=ART/'ArtifactInstallSession.kt'
TEST=ROOT/'app/src/test/java/com/aurora/store/data/artifact/ArtifactR3DP01P02PolicyTest.kt'
WF=ROOT/'.github/workflows/aurora-targeted.yml'
DOC=ROOT/'docs/R3D_P01_P02_HISTORICAL_DOWNGRADE_FOUNDATIONS.md'

class Refused(AssertionError): pass

def need(ok,why):
    if not ok:raise Refused('R3D_P01_P02_REFUSED '+why)
for p in (H,D,DECISION,JOURNEY,UI,REVIEW,SESSION,TEST,WF,DOC):need(p.is_file(),'missing '+str(p))
h,d,decision,journey,ui,review,session,test,workflow,doc=[p.read_text() for p in (H,D,DECISION,JOURNEY,UI,REVIEW,SESSION,TEST,WF,DOC)]

def historical(s):return all(x in s for x in (
    'enum class Match { NO_REFERENCE, UNVERIFIED_REFERENCE, VERIFIED_MATCH, REFUSED }',
    'val availabilityConfirmed: Boolean get() = false',
    'val publisherAuthenticated: Boolean get() = false',
    'val playDeliveryVerified: Boolean get() = false',
    'val installationApproved: Boolean get() = false',
    'val availabilityConfirmed: Boolean = false',
    'val publisherAuthenticated: Boolean = false',
    'val installationApproved: Boolean = false',
    'private val digits = Regex("[0-9]{1,19}")',
    'text.toLongOrNull()?.takeIf { it > 0L }',
    'signedVersion == null',
    'signedVersion <= 0L || signedVersion != version',
    'return Assessment(Match.VERIFIED_MATCH, version, signedVersion)',
    'compare(requested, signedVersion).match in setOf(Match.NO_REFERENCE, Match.VERIFIED_MATCH)',
    'entries.size > 64',
    'entries.any { it.packageName != packageName }',
    'entries.map { it.versionCode }.distinct().size != entries.size',
    'fun matchesVerifiedPackage(requested: String, signedPackageName: String)',
    'validPackageName(requested) && requested == signedPackageName',
    'enum class Compatibility { INCOMPATIBLE, LIMITED_PREFLIGHT_ONLY, UNKNOWN }',
    'minSdk != null && minSdk > deviceSdk -> Compatibility.INCOMPATIBLE',
    'abi != null && normalizedAbis.isNotEmpty() && abi !in normalizedAbis',
    '!checkedSignedSplitLayout -> Compatibility.UNKNOWN',
    'val finalAndroidInstallConfirmed: Boolean = false',
    'val dataPreservationGuaranteed: Boolean = false',
    'manually discovered historical-version REFERENCES',
)) and all(x not in s for x in ('https://', 'HttpURLConnection', 'openConnection(', 'PackageInstaller', 'Thread.sleep('))

def downgrade(s):return all(x in s for x in (
    'enum class Relation { INVALID, NOT_INSTALLED, SAME_VERSION, UPGRADE, DOWNGRADE }',
    'val dataPreservationGuaranteed: Boolean = false',
    'val silentUninstallAllowed: Boolean = false',
    'val privilegedBypassAllowed: Boolean = false',
    'installedVersionCode == null && installedSignerMatches != null',
    'installedVersionCode != null && installedVersionCode <= 0L',
    'candidateVersionCode < installedVersionCode -> Relation.DOWNGRADE',
    'installedSignerMatches != true,',
    'kind == Relation.DOWNGRADE, kind == Relation.DOWNGRADE',
    'separateDataRiskAcknowledgementRequired: Boolean = false',
    'AuroraStore has NOT verified any backup',
    'Back up important app data',
    'Data preservation is NOT guaranteed',
    'Android may refuse',
    'No automatic uninstall, data wipe or root bypass',
)) and 'PackageInstaller' not in s and 'pm uninstall' not in s

need(historical(h),'historical reference/evidence gate')
need(downgrade(d),'downgrade identity, consent, data warnings')
need('ArtifactHistoricalVersionPolicy.matchesVerified(reference, verifiedVersion)' in journey,
     'actual review consent ignores signed version reference')
need('ArtifactDowngradeSafetyPolicy.assess(' in decision and
     'downgradeSafety.installedIdentityBlocked' in decision and
     'downgradeSafety.separateDowngradeConsentRequired' in decision and
     'Blocker.SIGNER_MISMATCH' in decision and
     'Blocker.DOWNGRADE_CONSENT_REQUIRED' in decision and
     'Blocker.DOWNGRADE_DATA_LOSS_RISK_ACK_REQUIRED' in decision and
     'downgradeSafety.separateDataRiskAcknowledgementRequired' in decision and
     '!review.userAcknowledgedDataLossRisk' in decision and
     'val userAcknowledgedDataLossRisk: Boolean = false' in decision,
     'installer authorization not using common signer/downgrade policy')
need(review.count('ArtifactDowngradeSafetyPolicy.notice(')==2 and
     review.count('ArtifactHistoricalVersionPolicy.displayPreflight(')==2 and
     'Exact-version availability from provider: UNKNOWN' in review and
     'Historical reference: user-selected only' in review and
     'ArtifactImportDecision.Blocker.DOWNGRADE_DATA_LOSS_RISK_ACK_REQUIRED' in review and
     'fun consentNeedsDataRisk(' in review,
     'summary and detailed review must show same data warning')
need('Historical-version reference only' in ui and
     'the signed APK selected with Android' in ui and
     'I should back up important data first' in ui and
     'I separately approve the older version' in ui and
     'Android may refuse' in ui and
     'requestSerial += 1' in ui and
     'cancellation.cancel()' in ui and
     'ArtifactImportJourney.versionMatches(' in ui and
     'ArtifactInstallSession.install(' in ui and
     'downgradeConsent.isChecked' in ui and
     'private val historicalReferences' in ui and
     'historicalReferences.size >= 64' in ui and
     'ArtifactHistoricalVersionPolicy.matchesVerifiedPackage(' in ui and
     ui.count('ArtifactHistoricalVersionPolicy.matchesVerifiedPackage(')>=2 and
     'ArtifactHistoricalVersionPolicy.preflight(' in ui and
     'val preflight = historicalPreflight(result)' in ui and
     'activePreflight = preflight' in ui and
     'getPackageArchiveInfo(it.file.absolutePath, 0)' in ui and
     'it.packageName == verified.attempt.packageName' in ui and
     'verified.splitNames.indexOf(null)' in ui and
     'ArtifactSplitCompatibilityPolicy.check(' in ui and
     'Compatibility.INCOMPATIBLE' in ui and
     'No provider API queried' in ui and
     'private lateinit var dataRiskAcknowledgement: CheckBox' in ui and
     'dataRiskAcknowledgement.isChecked = false' in ui and
     'dataRiskAcknowledgement.visibility = View.GONE' in ui and
     'ArtifactReviewPresentation.consentNeedsDataRisk(facts)' in ui and
     'userAcknowledgedDataLossRisk = dataRiskAcknowledgement.isChecked' in ui and
     'val dataRisk = dataRiskAcknowledgement.isChecked' in ui and
     'approved, unknown, downgrade, dataRisk)' in ui,
     'visible review, stale invalidation or independent installed signer gate missing')
need('approvedDataLossRisk: Boolean = false' in session and
     'userAcknowledgedDataLossRisk = approvedDataLossRisk' in session and
     'consent_data_loss_risk' in session and
     'installed_version_at_review' in session and
     '.remove(key(sessionId, "consent_data_loss_risk"))' in session and
     '.remove(key(sessionId, "installed_version_at_review"))' in session and
     session.count('ArtifactApkVerifier.revalidateForInstall(context, imported, cancelled)') == 2 and
     session.index('ArtifactApkVerifier.revalidateForInstall(context, imported, cancelled)',
                   session.index('session.openWrite')) < session.index('session.commit(pending.intentSender)') and
     'params.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_REQUIRED)' in session and
     'if (blocks.isNotEmpty())' in session,
     'P02 installer no independent risk gate, stale pre-commit signature/version or OS user action')
required_tests=[
 'p01ReferenceRequiresExactUnsignedBoundedVersion',
 'p01ProviderReferenceCannotMintPublisherPlayOrAvailability',
 'p01UnverifiedReferenceCannotBePromotedToVerifiedFile',
 'p01ManualReferenceMustMatchSignedVersionAtConsentTime',
 'p01ShortlistRejectsCrossPackageAndConflictingVersionSources',
 'p01PackageReferenceMustMatchIndependentlySignedManifest',
 'p01ManualReferenceOriginMustBeBoundedAndNeverBeARawUrl',
 'p01ManualDiscoveryIsDeterministicAndNeverFetchesOrApproves',
 'p01KnownUnsupportedMinSdkIsIncompatible',
 'p01KnownIncompatibleAbiIsIncompatible',
 'p01MissingMetadataNeverPretendsInstallability',
 'p01LimitedPreflightNeverClaimsAndroidInstallation',
 'p01HistoricalDiscoveryDisplayIsExplicitlyUntrusted',
 'p01ReviewSurfacesCompatibilityWithoutPublisherClaims',
 'p02DowngradeRequiresPositiveActiveSignerAndSeparateApproval',
 'p02InstalledSignerMismatchCannotBeOverriddenByConsent',
 'p02MissingConsentBlockedEvenWhenSignerMatches',
 'p02InvalidInstalledStateNeverGrantsConsent',
 'p02UpgradeAndSameVersionNeedNoDowngradeConsent',
 'p02DisplayNeverPromisesDataPreservationOrRootBypass',
 'p02ReviewDisplaysVersionComparisonAndSignerGate',
 'p02DataRiskAcknowledgementIndependentFromDowngradeConsent',
 'p02AckCannotOverrideUnknownOrMismatchedInstalledSigner',
 'p02RiskGateAppliesOnlyToActualDowngrades',
 'p02NoticeDoesNotPretendBackupExistsOrAndroidWillInstall',
]
need(test.count('@Test fun ')==25 and
     all(re.search(r'@Test\s+fun\s+'+re.escape(t)+r'\s*\(',test) for t in required_tests),
     'missing actual hosted twenty-five JVM regressions')
need('ArtifactR3DP01P02PolicyTest' in workflow and
     'python3 -B scripts/ci/test_r3d_p01_p02_source.py' in workflow and
     '--tests' in workflow and 'gradlew' in workflow,
     'GitHub hosted compilation/JVM source gates not wired')
need('P03' in doc and 'P04' in doc and 'read-only' in doc and
     'Data preservation is not guaranteed' in doc,
     'unsafe qualification promise')

negatives=[
 ('historical-source-grants-publisher',h,'val publisherAuthenticated: Boolean get() = false','val publisherAuthenticated: Boolean get() = true',historical),
 ('historical-grants-play',h,'val playDeliveryVerified: Boolean get() = false','val playDeliveryVerified: Boolean get() = true',historical),
 ('historical-grants-installer',h,'val installationApproved: Boolean get() = false','val installationApproved: Boolean get() = true',historical),
 ('historical-weak-version',h,'[0-9]{1,19}','.*',historical),
 ('historical-no-cross-package',h,'entries.any { it.packageName != packageName }','false',historical),
 ('historical-no-match',h,'signedVersion <= 0L || signedVersion != version','signedVersion <= 0L',historical),
 ('downgrade-assumes-data-safety',d,'val dataPreservationGuaranteed: Boolean = false','val dataPreservationGuaranteed: Boolean = true',downgrade),
 ('downgrade-accept-unknown-signer',d,'kind, installedSignerMatches != true,','kind, false,',downgrade),
 ('downgrade-disables-risk',d,'Back up important app data','Nothing to back up',downgrade),
 ('downgrade-permit-root',d,'val privilegedBypassAllowed: Boolean = false','val privilegedBypassAllowed: Boolean = true',downgrade),
 ('downgrade-missing-installed-state',d,'installedVersionCode == null && installedSignerMatches != null','false',downgrade),
 ('downgrade-disables-risk-ack',d,'separateDataRiskAcknowledgementRequired: Boolean = false',
       'separateDataRiskAcknowledgementRequired: Boolean = true',downgrade),
 ('downgrade-fakes-safety',d,'AuroraStore has NOT verified any backup','Backup verified',downgrade),
 ('historical-allow-cross-package-claim',h,'validPackageName(requested) && requested == signedPackageName','true',historical),
 ('historical-allow-higher-minsdk',h,'minSdk != null && minSdk > deviceSdk -> Compatibility.INCOMPATIBLE','false -> Compatibility.INCOMPATIBLE',historical),
 ('historical-ignore-abi-mismatch',h,'abi != null && normalizedAbis.isNotEmpty() && abi !in normalizedAbis','false',historical),
 ('historical-promote-unchecked-splits',h,'!checkedSignedSplitLayout -> Compatibility.UNKNOWN','false -> Compatibility.UNKNOWN',historical),
 ('historical-forge-android-success',h,'val finalAndroidInstallConfirmed: Boolean = false','val finalAndroidInstallConfirmed: Boolean = true',historical),
 ('historical-forge-preserved-data',h,'val dataPreservationGuaranteed: Boolean = false','val dataPreservationGuaranteed: Boolean = true',historical),
]
for label,src,old,new,guard in negatives:
    need(old in src and not guard(src.replace(old,new,1)),'security negative not rejected '+label)
# Each P02 wiring regression must be rejected by an executable contract.
def p02_decision_guard(x):return all(t in x for t in (
    'downgradeSafety.installedIdentityBlocked',
    'downgradeSafety.separateDowngradeConsentRequired',
    'downgradeSafety.separateDataRiskAcknowledgementRequired',
    '!review.userAcknowledgedDataLossRisk',
    'Blocker.DOWNGRADE_DATA_LOSS_RISK_ACK_REQUIRED'))
def p02_session_guard(x):return (
    'userAcknowledgedDataLossRisk = approvedDataLossRisk' in x and
    x.count('ArtifactApkVerifier.revalidateForInstall(context, imported, cancelled)')==2 and
    'params.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_REQUIRED)' in x)
def p02_ui_guard(x):return x.count('dataRiskAcknowledgement.isChecked = false')==2 and all(t in x for t in (

    'ArtifactReviewPresentation.consentNeedsDataRisk(facts)',
    'userAcknowledgedDataLossRisk = dataRiskAcknowledgement.isChecked',
    'approved, unknown, downgrade, dataRisk)'))
wiring_negatives=[
 ('risk-authorizer-omitted',decision,'!review.userAcknowledgedDataLossRisk','false',p02_decision_guard),
 ('risk-blocker-removed',decision,'Blocker.DOWNGRADE_DATA_LOSS_RISK_ACK_REQUIRED','Blocker.DOWNGRADE_CONSENT_REQUIRED',p02_decision_guard),
 ('risk-installer-not-passed',session,'userAcknowledgedDataLossRisk = approvedDataLossRisk','userAcknowledgedDataLossRisk = true',p02_session_guard),
 ('risk-no-second-revalidation',session,'ArtifactApkVerifier.revalidateForInstall(context, imported, cancelled)','// bypassed',p02_session_guard),
 ('risk-accept-without-ui-ack',ui,'userAcknowledgedDataLossRisk = dataRiskAcknowledgement.isChecked','userAcknowledgedDataLossRisk = true',p02_ui_guard),
 ('risk-inherited',ui,'dataRiskAcknowledgement.isChecked = false','dataRiskAcknowledgement.isChecked = true',p02_ui_guard),
]
for label,src,old,new,guard in wiring_negatives:
    need(old in src and not guard(src.replace(old,new,1)),'P02 wiring-negative not rejected '+label)
for forbidden in ('PackageInstaller.commit(', 'Runtime.getRuntime().exec(', 'su -c', 'pm uninstall',
                  'DELETE_ALL_USER_DATA', 'PlayVerifiedEvidenceStore('):
    need(forbidden not in h+d+test,'read-only boundary violated '+forbidden)
print(f'R3D_P01_P02_SOURCE_AND_{len(negatives)+len(wiring_negatives)}_NEGATIVE_MUTATIONS_PASS: 25 hosted JVM methods; bounded manual version discovery, strict source labels, package/version match, conservative SDK/ABI preflight and P02 signer/consent/data-loss gates')
