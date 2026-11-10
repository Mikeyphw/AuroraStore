#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""C04-04 fail-closed session, installed signer, platform callback and consent audit."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ART=ROOT/'app/src/main/java/com/aurora/store/data/artifact'
TESTS=ROOT/'app/src/test/java/com/aurora/store/data/artifact'
DEVICE=ROOT/'app/src/androidTest/java/com/aurora/store/data/artifact'

def require(pred,reason):
 if not pred: raise SystemExit('R3C04_C04_REFUSED: '+reason)
def get(root,name):
 f=root/name
 require(f.is_file(),'missing '+str(f))
 return f.read_text()
install=get(ART,'ArtifactInstallSession.kt')
verifier=get(ART,'ArtifactApkVerifier.kt')
receiver=get(ART,'ArtifactInstallStatusReceiver.kt')
receipt=get(ART,'ArtifactSessionReceiptPolicy.kt')
review=get(ART,'ArtifactImportDecision.kt')
activity=get(ART,'ArtifactImportActivity.kt')
case=get(TESTS,'ArtifactImportDecisionTest.kt')
state=get(TESTS,'ArtifactSessionReceiptPolicyTest.kt')
device=get(DEVICE,'ArtifactInstallSessionDeviceTest.kt')
runner=(ROOT/'scripts/ci/r3c03_c02_emulator_ci.sh').read_text()
for key in ('approvedInstall: Boolean','userApprovedInstall = approvedInstall',
            'ArtifactApkVerifier.revalidateForInstall(context, imported, cancelled)',
            'USER_ACTION_REQUIRED','PACKAGE_SOURCE_LOCAL_FILE',
            'writtenHash.update(buffer, 0, n)','session.fsync(out)',
            'if (cancelled()) throw ApkVerificationException("Import cancelled before commit")'):
 require(key in install,'C04 session missing '+key)
require('userApprovedInstall = true' not in install,'hard-coded consent bypass')
require('ArtifactInstallSession.install(this, receipt, approved, unknown, downgrade)' in activity,
        'UI approval not passed to session layer')
for key in ('"Installed app changed after import review"',
            '"Installed app signer changed after import review"',
            '"Private APK changed before installation"',
            'ApkSetPolicy.check(attempt.packageName, attempt.versionCode',
            'signerFor(manager, part.file, identity)','installed(manager, attempt.packageName)',
            '"Verified split or signer identity changed"'):
 require(key in verifier,'missing post-consent check '+key)
require('review.installedVersion != null && review.installedSignerMatches != true' in review,
        'unknown installed signer can bypass match')
require('SIGNER_MISMATCH' in case and 'installedUnknownSignerCannotBeAuthorizedByPublisherConsent' in case,
        'installed identity negative tests missing')
for key in ('key(sessionId, "generation")','key(sessionId, "state")',
            'key(sessionId, "signer")','key(sessionId, "source")','key(sessionId, "package")',
            'key(sessionId, "version")', 'last_session',
            'osSession != session',
            'ArtifactSessionReceiptPolicy.next(previous, event)',
            'recordPresentationFailure('):
 require(key in install, 'session receipt missing '+key)
require('putInt("session", sessionId)' not in install, 'global session slot still present')
require('PackageInstaller.EXTRA_SESSION_ID' in receiver and
        'ArtifactInstallSession.recordPresentationFailure' in receiver,
        'Android session ID or missing approval UI not tracked')
for key in ('State.INSTALLED_BY_ANDROID, State.ANDROID_REJECTED -> null',
            'Event.USER_APPROVAL_REQUIRED -> null',
            'State.APPROVAL_UI_UNAVAILABLE'):
 require(key in receipt, 'terminal/replay policy missing '+key)
require(state.count('@Test') >= 6, 'receipt JVM negative tests missing')
require(device.count('@Test') == 5 and 'foreignSessionAndCallbackReplayAreRejected' in device and 'separateSessionsRetainSeparateReceiptState' in device,
        'API36 consent/revalidation device suite missing')
require('ArtifactInstallSessionDeviceTest' in runner and
        'R3C04_HF02_SESSION_PASS' in runner,
        'existing API36 periodic gate does not run C04-04 device suite')
for source in (install,verifier,receipt,review,receiver,activity):
 require('PlayVerifiedEvidenceStore' not in source,'local install touched Play proof storage')
print('R3C04_C04_SECURITY_PASS: fresh signer revalidation, strict consent, per-session CAS, no Play evidence')
