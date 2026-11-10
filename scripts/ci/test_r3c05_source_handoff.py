#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R3C05 source and staleness contracts. No GitHub scrape or Play API network call."""
from pathlib import Path
root = Path(__file__).resolve().parents[2]
a = root / 'app/src/main/java/com/aurora/store/data/artifact'
t = root / 'app/src/test/java/com/aurora/store/data/artifact'
d = root / 'app/src/androidTest/java/com/aurora/store/data/artifact'


def need(cond, detail):
    if not cond:
        raise SystemExit('R3C05_REFUSED: ' + detail)


def source(file):
    path = a / file
    need(path.is_file(), 'missing '+file)
    return path.read_text()

provider = source('ArtifactProviderDiscovery.kt')
activity = source('ArtifactImportActivity.kt')
claim = source('ArtifactHandoffClaimPolicy.kt')
origin = source('ArtifactOriginBoundary.kt')
install = source('ArtifactInstallSession.kt')
play = (root / 'app/src/main/java/com/aurora/store/data/room/play/PlayVerifiedEvidenceStore.kt').read_text()
for needle in ('GOOGLE_PLAY', 'LOCAL_DOCUMENT', 'DEVELOPER_WEBSITE', 'GITHUB_RELEASE',
               'APKMIRROR', 'FDROID', 'APKPURE', 'Route.PLAY_LISTING',
               'ArtifactSourceHandoff.parse(', 'allowAlternativeThisTime',
               'fossEligibilityAcknowledged', '!apkPureEnabled', 'packageName.matches(userInput)',
               'claimedSource: ArtifactSource?', 'exact-version availability is UNKNOWN' if False else 'availability is UNKNOWN'):
    need(needle.lower() in provider.lower(), 'missing provider guard '+needle)
for needle in ('ArtifactProviderDiscovery.decide(', 'alternativeConsent.isChecked',
               'fossAcknowledgement.isChecked', 'apkpure_opt_in", false',
               'selectedProvider().source ?: ArtifactSource.LOCAL_DOCUMENT',
               'ArtifactHandoffClaimPolicy.afterSuccessfulLaunch(',
               'ArtifactHandoffClaimPolicy.selection(',
               'nowMonotonicMs = pickedAtMonotonicMs', 'Browser links are manual handoffs',
               'ActivityResultContracts.OpenDocument()', 'unknownPublisherConsent',
               'downgradeConsent', 'startActivity(Intent(Intent.ACTION_VIEW',
               'lastBrowserLaunch = null'):
    need(needle in activity, 'missing actual UI/chooser integration '+needle)
for needle in ('MAX_CLAIM_AGE_MS', 'openedAtMonotonicMs', 'alternativeConsent',
               'nowMonotonicMs >= launched.openedAtMonotonicMs',
               'selected != ArtifactSource.APKPURE_OPT_IN || apkPureOptIn',
               'launched.exactInput == enteredUrl'):
    need(needle in claim, 'stale/source revocation guard removed '+needle)
need('class GooglePlayVerified private constructor()' in origin, 'Play proof capability open')
need('class OfficialDeveloperVerified private constructor()' in origin and
     'class GitHubReleaseVerified private constructor()' in origin,
     'browser URL can mint official developer proof')
need('PlayVerifiedEvidenceStore' not in (provider + activity + claim), 'browser/chooser writes Play evidence')
need('PlayExactVersionOutcomePolicy.Source.GOOGLE_PLAY' in play, 'Play-specific proof gate regressed')
need('ArtifactApkVerifier.revalidateForInstall(' in install and
     'PackageInstaller.SessionParams.MODE_FULL_INSTALL' in install,
     'signing/consent installer contract changed')
need('java.net.URLConnection' not in provider and 'OkHttpClient' not in provider and
     'HttpURLConnection' not in provider and 'retrofit' not in provider,
     'provider unexpectedly downloads or scrapes')
unit = (t / 'ArtifactProviderDiscoveryTest.kt').read_text()
claim_tests = (t / 'ArtifactHandoffClaimPolicyTest.kt').read_text()
device = (d / 'ArtifactProviderDiscoveryDeviceTest.kt').read_text()
need(unit.count('@Test') >= 12 and claim_tests.count('@Test') >= 10,
     'provider and stale-claim negative JVM tests missing')
need(device.count('@Test') >= 3 and 'ActivityScenario.launch' in device,
     'read-only API36 provider UI tests missing')
need((root / 'docs/R3C05_PROVIDER_DISCOVERY.md').is_file(), 'provider qualification and limitations docs missing')
runner=(root / 'scripts/ci/r3c03_c02_emulator_ci.sh').read_text()
for marker in ('ArtifactPrivateStagerDeviceTest','ArtifactApkVerifierDeviceTest',
               'ArtifactInstallSessionDeviceTest','ArtifactImportActivityDeviceTest',
               'ArtifactProviderDiscoveryDeviceTest', 'R3C05_API36_PROVIDER_UI_PASS',
               "^OK \\(3 tests\\)"):
    need(marker in runner, 'missing additive existing API36 gate: '+marker)
print('R3C05_SOURCE_PASS: seven explicit routes, alternative opt-in, Play separation, URLs, browser claim expiry, manual picker, consent, negative tests')
