#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R3C07 P03A HF03: source assertions, inherited R3C05 guard and mutations.

This is not Android runtime acceptance; Kotlin/JUnit execution is hosted Gradle.
"""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'app/src/main/java/com/aurora/store/data/artifact'
TEST = ROOT / 'app/src/test/java/com/aurora/store/data/artifact/ArtifactProviderDisclosureTest.kt'
WORKFLOW = ROOT / '.github/workflows/aurora-targeted.yml'

class Refused(AssertionError):
    pass

def require(condition: bool, why: str) -> None:
    if not condition:
        raise Refused('R3C07_P03A_SOURCE_REFUSED: ' + why)

def sound(disclosure: str, discovery: str, unit: str, workflow: str) -> bool:
    needed = (
        'enum class Listing { NOT_CHECKED, NOT_APPLICABLE }',
        'enum class Availability { UNKNOWN }',
        'enum class DownloadedBytes { NOT_SELECTED }',
        'enum class Signature { NOT_VERIFIED }',
        'enum class Publisher { NOT_AUTHENTICATED }',
        'enum class Compatibility { NOT_ASSESSED }',
        'enum class InstallResult { NOT_REQUESTED }',
        'Listing.NOT_APPLICABLE\n            } else {\n                Listing.NOT_CHECKED',
        'availability = Availability.UNKNOWN',
        'downloadedBytes = DownloadedBytes.NOT_SELECTED',
        'signature = Signature.NOT_VERIFIED',
        'publisher = Publisher.NOT_AUTHENTICATED',
        'compatibility = Compatibility.NOT_ASSESSED',
        'installResult = InstallResult.NOT_REQUESTED',
        'Exact-version availability: ${facts.availability}',
        'Downloaded bytes: NOT SELECTED; APK signature: NOT VERIFIED',
        'Publisher identity: not authenticated',
        'Android install result: NOT REQUESTED',
    )
    return (
        all(n in disclosure for n in needed)
        and 'fun beforeSelection(provider: ArtifactProviderDiscovery.Provider)' in disclosure
        and 'fun summary(provider: ArtifactProviderDiscovery.Provider)' in disclosure
        and 'return providerNote + "\\n" + ArtifactProviderDisclosure.summary(provider)' in discovery
        and 'availability is UNKNOWN' in discovery
        and 'ArtifactSourceHandoff.parse(userInput, source, apkPureEnabled)' in discovery
        and 'if (provider.isAlternative && !allowAlternativeThisTime)' in discovery
        and 'if (provider == Provider.APKPURE && !apkPureEnabled)' in discovery
        and unit.count('@Test fun ') == 5
        and 'for (provider in providers)' in unit
        and 'is ArtifactProviderDiscovery.Outcome.Refused' in unit
        and workflow.count('python3 -B scripts/ci/test_r3c07_p03a_source.py') == 1
        and workflow.count('app:testVanillaDebugUnitTest') == 1
        and workflow.count('com.aurora.store.data.artifact.ArtifactProviderDisclosureTest') == 1
        and workflow.count('python3 -B scripts/ci/aurora_ci_policy.py run-targeted') == 1
        and 'python3 -B scripts/ci/test_r3c07_hf03_optimization.py' in workflow
    )

d = (APP / 'ArtifactProviderDisclosure.kt').read_text()
p = (APP / 'ArtifactProviderDiscovery.kt').read_text()
t = TEST.read_text()
w = WORKFLOW.read_text()
require(sound(d,p,t,w), 'missing or weakened independent pre-selection facts, consent, or CI')

negatives = (
    ('fabricated availability', d.replace('enum class Availability { UNKNOWN }', 'enum class Availability { AVAILABLE }'), p, t, w),
    ('fabricated signature', d.replace('signature = Signature.NOT_VERIFIED', 'signature = Signature.VERIFIED'), p, t, w),
    ('fabricated publisher', d.replace('publisher = Publisher.NOT_AUTHENTICATED', 'publisher = Publisher.VERIFIED'), p, t, w),
    ('fabricated install success', d.replace('installResult = InstallResult.NOT_REQUESTED', 'installResult = InstallResult.INSTALLED_BY_ANDROID'), p, t, w),
    ('incorrect local listing', d.replace('Listing.NOT_APPLICABLE', 'Listing.NOT_CHECKED', 1), p, t, w),
    ('status detached from UI', d, p.replace('ArtifactProviderDisclosure.summary(provider)', 'providerNote'), t, w),
    ('R3C05 inherited unknown availability guard removed', d, p.replace('availability is UNKNOWN', 'no historical version verified'), t, w),
    ('source consent bypass', d, p.replace('if (provider.isAlternative && !allowAlternativeThisTime)', 'if (false)'), t, w),
    ('APKPure opt-in bypass', d, p.replace('if (provider == Provider.APKPURE && !apkPureEnabled)', 'if (false)'), t, w),
    ('regression not in CI', d, p, t, w.replace('python3 -B scripts/ci/test_r3c07_p03a_source.py', 'true')),
    ('removed JVM matrix', d, p, t.replace('@Test fun ', 'fun ', 1), w),
    ('skip hosted JVM execution', d, p, t, w.replace('app:testVanillaDebugUnitTest', 'app:assembleVanillaDebug')),
)
for label, dm, pm, tm, wm in negatives:
    require((dm,pm,tm,wm) != (d,p,t,w) and not sound(dm,pm,tm,wm),
            'mutation escaped negative matrix: '+label)
# Additional HF01 UI lifecycle regression: after a picked file is actually
# verified, pre-selection UNKNOWN/NOT SELECTED text must not obscure the
# authoritative per-file receipt. Stale/cancelled workers cannot mint success.
ACT=(ROOT/'app/src/main/java/com/aurora/store/data/artifact/ArtifactImportActivity.kt').read_text()
def ui_truth(s: str) -> bool:
    return all(fragment in s for fragment in (
        'active != null -> "Provider choice alone does not authenticate this selected file.',
        '::selectButton.isInitialized && !selectButton.isEnabled ->',
        'refreshProviderPresentation()\n                        val facts = verifiedFacts(result)',
        'if (::status.isInitialized) showStatus(message)\n        refreshProviderPresentation()',
        'ArtifactReviewPresentation.summary(facts)',
        'ArtifactReviewPresentation.verification(facts)',
    ))
require(ui_truth(ACT), 'verified-file UI must replace pre-selection disclosure')
ui_negatives=(
    ('verified UI relabel disabled', 'active != null -> "Provider choice alone',
     'active == null -> "Provider choice alone'),
    ('in-progress status omitted', '::selectButton.isInitialized && !selectButton.isEnabled ->',
     'false ->'),
    ('verified selection not refreshed',
     'refreshProviderPresentation()\n                        val facts = verifiedFacts(result)',
     'val facts = verifiedFacts(result)'),
    ('preselection not restored on cancel',
     'if (::status.isInitialized) showStatus(message)\n        refreshProviderPresentation()',
     'if (::status.isInitialized) showStatus(message)'),
)
for label,old,new in ui_negatives:
    require(old in ACT, 'UI mutation anchor missing: '+label)
    mutated=ACT.replace(old,new,1)
    require(mutated!=ACT and not ui_truth(mutated), 'unsafe UI regression escaped: '+label)
print(f'R3C07_P03A_SOURCE_PASS: 5 JVM tests, {len(negatives)} source mutations + {len(ui_negatives)} verified-file UI mutations')
