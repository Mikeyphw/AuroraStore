#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""C04-07 interface and receipt fail-closed source contracts; not UI runtime proof."""
from pathlib import Path

root = Path(__file__).resolve().parents[2]
base = root / "app/src/main/java/com/aurora/store/data/artifact"

def need(path, needles):
    content = path.read_text()
    for needle in needles:
        if needle not in content:
            raise SystemExit("R3C04_C07_REFUSED: " + str(path) + " missing " + needle)
    return content

presentation = need(base / "ArtifactReviewPresentation.kt", [
    "VERIFIED APK FILES — NOT INSTALLED", "APK signature valid; developer/publisher identity NOT independently verified", "androidFailureReason",
    "unverified reference", "Android reported installation SUCCESS", "Installation NOT confirmed",
    "consentNeedsUnknownPublisher", "consentNeedsDowngrade", "Signer continuity", "SHA-256"
])
activity = need(base / "ArtifactImportActivity.kt", [
    "ViewCompat.setOnApplyWindowInsetsListener", "WindowInsetsCompat.Type.systemBars()",
    "ArtifactReviewPresentation.verification", "ArtifactInstallSession.lastResult",
    "configureConsent(result)", "updateConsentState()", "Review the receipt",
    "unknownPublisherConsent.visibility", "downgradeConsent.visibility",
    "installButton.isEnabled = blockers.isEmpty()", "clearReview(",
    "Refresh Android install outcome", "ActivityResultContracts.OpenDocument()"
])
install = need(base / "ArtifactInstallSession.kt", [
    'key(sessionId, "source_sha256")', 'key(sessionId, "trust")',
    'key(sessionId, "source_reference")', 'key(sessionId, "apk_count")',
    'key(sessionId, "consent_install")', 'key(sessionId, "consent_unknown")',
    'key(sessionId, "consent_downgrade")',
    'ArtifactReviewPresentation.androidResult(state)',
    'ArtifactSessionReceiptPolicy.State.ANDROID_REJECTED',
    'ArtifactApkVerifier.revalidateForInstall(', 'session.commit(pending.intentSender)'
])
settings = need(root / "app/src/main/java/com/aurora/store/compose/ui/preferences/SettingsScreen.kt", [
    "ArtifactImportActivity::class.java", "Import and verify APKs", "Review signing, source and install consent"
])
unit = (root / "app/src/test/java/com/aurora/store/data/artifact/ArtifactReviewPresentationTest.kt").read_text()
device = (root / "app/src/androidTest/java/com/aurora/store/data/artifact/ArtifactImportActivityDeviceTest.kt").read_text()
if unit.count("@Test") < 10 or device.count("@Test") != 3:
    raise SystemExit("R3C04_C07_REFUSED: presentation/UI negative test inventory incomplete")
if "PlayVerifiedEvidenceStore" in presentation + activity + install:
    raise SystemExit("R3C04_C07_REFUSED: non-Play review must not use Play evidence store")
if 'trustedPublisherAnchor = false' not in activity + install:
    raise SystemExit("R3C04_C07_REFUSED: C04 cannot mint trusted publisher anchor")
if 'installedSignerMatches = verified.signerMatchesInstalled' not in activity:
    raise SystemExit("R3C04_C07_REFUSED: current receipt must govern consent")
if 'lastReceipt.text = ArtifactInstallSession.lastResult' not in activity:
    raise SystemExit("R3C04_C07_REFUSED: Android receipt must refresh after callback")
if '"INSTALLED_BY_ANDROID"' in activity or '"ANDROID_REJECTED"' in activity:
    raise SystemExit("R3C04_C07_REFUSED: raw state string UI / conflated status")
print("R3C04_C07_SOURCE_PASS: Settings, verified receipt, unanchored trust, scoped approval, OS result, insets; 10 JVM + 3 device tests authored")
