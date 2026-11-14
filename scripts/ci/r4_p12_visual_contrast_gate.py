#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""P12 source-gated image-contrast fix; not manual upstream visual signoff.

The P09 emulator artifact demonstrates the defect, not acceptance of the P12
source. The hosted emulator must produce a NEW 64-test/37-image receipt on HEAD.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

P11 = '9632c29bc19248bb905d1aaa257469118576312d'
P09 = 'ecb9c4db5d347f5073ceacc4ef0555f9d6e52608'
REPO = 'Mikeyphw/AuroraStore'
WORKFLOW = '.github/workflows/aurora-r4-p05-device-ux.yml'
STATUS = 'docs/r4/R4_P12_VISUAL_STATUS.json'
PLACEHOLDER = 'app/src/main/java/com/aurora/store/compose/composable/Placeholder.kt'
PIXEL_AUDIT = 'scripts/ci/r4_p05_screenshot_audit.py'
PIXEL_TESTS = 'scripts/ci/test_r4_p06_screenshot_audit.py'
POPULATED_TEST = 'app/src/androidTest/java/com/aurora/store/compose/ui/r4/R4PopulatedCatalogDeviceTest.kt'
SMALL_EXPOSURES = {
    'app/src/main/java/com/aurora/store/compose/ui/apps/TopChartsPage.kt': ('private fun TopChartsBody(', 'internal fun TopChartsBody('),
    'app/src/main/java/com/aurora/store/compose/ui/apps/CategoriesPage.kt': ('private fun CategoriesBody(', 'internal fun CategoriesBody('),
    'app/src/main/java/com/aurora/store/compose/ui/search/SearchScreen.kt': ('private fun SearchResultListItem(', 'internal fun SearchResultListItem('),
}
ALLOWED = frozenset({
    PLACEHOLDER, PIXEL_AUDIT, PIXEL_TESTS, POPULATED_TEST, *SMALL_EXPOSURES,
    'scripts/ci/r4_p07_source_parity.py', 'scripts/ci/r4_p05_emulator_acceptance.sh',
    'scripts/ci/r4_p08_retained_decisions.py',
    'scripts/ci/r4_p10_readiness_gate.py',
    'scripts/ci/r4_p11_pr_review_gate.py',
    'scripts/ci/r4_p12_visual_contrast_gate.py',
    'scripts/ci/test_r4_p12_visual_contrast_gate.py',
    STATUS, 'docs/r4/R4_P12_VISUAL_AUDIT.md', WORKFLOW,
})
OLD = '''        Text(
            text = message,
            style = MaterialTheme.typography.bodyLarge,
            textAlign = TextAlign.Center
        )'''
NEW = '''        Text(
            text = message,
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurface,
            textAlign = TextAlign.Center
        )'''
FALSE = (
    'fresh_p12_hosted_result_qualified', 'all_upstream_visual_parity_approved',
    'populated_catalog_visuals_qualified', 'live_google_play_qualified',
    'physical_arm64_qualified', 'real_installer_qualified',
    'production_signing_qualified', 'automatic_merge_allowed', 'release_qualified',
)

class Refused(RuntimeError):
    pass

def need(cond: bool, reason: str):
    if not cond: raise Refused('R4_P12_REFUSED_' + reason)

def git(root: Path, *args: str) -> str:
    p = subprocess.run(['git', *args], cwd=root, capture_output=True, text=True)
    need(p.returncode == 0, 'GIT_' + str(args[0]) + '_' + p.stderr[-180:])
    return p.stdout.strip()

def check_status(d: dict):
    need(isinstance(d, dict) and d.get('schema') == 1 and
         d.get('kind') == 'aurora-r4-p12-actual-pixel-contrast-remediation' and
         d.get('repository') == REPO and d.get('pr_number') == 2 and
         d.get('pr_must_remain_draft') is True and d.get('p11_parent_sha') == P11 and
         d.get('p09_original_sha') == P09 and
         d.get('p09_original_emulator_run') == 43498499144 and
         d.get('p09_screenshot_artifact_id') == 14072889339 and
         d.get('old_background_rgb') == [18,19,24] and
         d.get('old_glyph_rgb') == [0,0,0] and
         d.get('source_patch') == 'explicit-onSurface-Placeholder-message' and
         d.get('pixel_test') == 'dark-updates-text-region-bright-pixels' and
         d.get('fresh_p12_emulator_required') is True and
         d.get('old_p09_evidence_only_historical') is True and
         d.get('offline_populated_test_count_per_theme') == 6 and
         d.get('offline_populated_hosted_executions_expected') == 12 and
         d.get('total_hosted_executions_expected') == 64 and
         d.get('offline_populated_screenshot_count_expected') == 12 and
         d.get('total_hosted_screenshots_expected') == 37 and
         d.get('populated_component_fixtures_only') is True and
         d.get('full_catalog_navigation_qualified') is False,
         'STATUS_IDENTITY')
    for key in FALSE:
        need(d.get(key) is False, 'FALSE_APPROVAL_' + key)
    need(re.fullmatch('[a-f0-9]{64}', str(d.get('p09_screenshot_artifact_digest_sha256',''))) is not None,
         'ARCHIVED_ARTIFACT_DIGEST')

def check_patch(preimage: str, current: str):
    need(preimage.count(OLD) == 1, 'PREIMAGE_TEXT_UNEXPECTED')
    need(current == preimage.replace(OLD, NEW, 1), 'PRODUCTION_CHANGE_BEYOND_CONTRAST_FIX')
    need(current.count('color = MaterialTheme.colorScheme.onSurface') == 1,
         'ON_SURFACE_COLOR_MISSING_OR_DUPLICATED')

def check_pixel_source(audit: str, tests: str):
    # Check the executable pixel path, not the mere presence of a repeated
    # identifier. In HF25 the old name appeared five times; changing only its
    # declaration was incorrectly accepted by a substring-only guard.
    required_pixel_implementation = (
        '    p12_dark_updates_label_bright_samples = 0',
        '                        p12_dark_updates_label_bright_samples += 1',
        "            'p12_dark_updates_label_bright_samples': p12_dark_updates_label_bright_samples,",
        "    require(pngs['dark/r4_activity_updates.png'].get(",
        "        'p12_dark_updates_label_bright_samples', 0) >= 50,",
        "        'R4_P12_DARK_UPDATES_EMPTY_LABEL_LOW_CONTRAST')",
        "path.name == 'r4_activity_updates.png'",
        "path.parent.name == 'dark'",
        'if height * 515 // 1000 <= y < height * 555 // 1000:',
        'if min(rgb) >= 110 and max(rgb) >= 155:',
    )
    for marker in required_pixel_implementation:
        need(marker in audit, 'PIXEL_AUDIT_MISSING_'+marker)
    need('R4_P12_DARK_UPDATES_EMPTY_LABEL_LOW_CONTRAST' in tests and
         'foreground=(0,0,0)' in tests,
         'PIXEL_NEGATIVE_NOT_ENFORCED')
    for marker in ("'r4-populated-light': 6", "'r4-populated-dark': 6",
                   'r4_populated_for_you.png', 'r4_populated_search.png',
                   'r4_populated_details.png', 'r4_populated_charts.png',
                   'r4_populated_categories.png', 'r4_populated_install_controls.png',
                   'R4_P12_REAL_EMULATOR_64_TESTS_AND_37_SCREENSHOTS'):
        need(marker in audit, 'POPULATED_CAPTURE_INVENTORY_'+marker)
    need("'r4-offline-account-session': 9" in audit and
         'real_device_tests' in audit and
         'R4_P09_REAL_EMULATOR_52_TESTS_AND_25_SCREENSHOTS_NONBLANK_UNIQUE_THEME_PASS' in audit,
         'OLD_DEVICE_RECEIPT_GATES_REMOVED')

def check_workflow(wf: str):
    for marker in (
        'python3 -B scripts/ci/test_r4_p12_visual_contrast_gate.py',
        'python3 -B scripts/ci/r4_p12_visual_contrast_gate.py --root .',
        'python3 -B scripts/ci/test_r4_p06_screenshot_audit.py',
        'python3 -B scripts/ci/test_r4_p11_pr_review_gate.py',
        'python3 -B scripts/ci/r4_p11_pr_review_gate.py --root .',
        'python3 -B scripts/ci/r4_p10_readiness_gate.py --repo .',
        'python3 -B scripts/ci/r4_p09_session_source_contract.py --root .',
        'python3 -B scripts/ci/r4_p08_retained_decisions.py --repo .',
        'bash scripts/ci/r4_p05_emulator_acceptance.sh',
    ):
        need(wf.count(marker) == 1, 'MISSING_WORKFLOW_STEP_'+marker)
    need(re.findall(r'^  (?:actions|contents):\s*write\b',wf,re.M)==[],
         'WORKFLOW_PERMISSION_ESCALATION')
    need('  contents: read' in wf and '  actions: read' in wf and
         '  push:\n' in wf and '  workflow_dispatch:\n' in wf and
         'if: always()' in wf,'WORKFLOW_REQUIRED_CONTROL_REMOVED')

def check_history_guards(p08: str, p10: str, p11: str):
    need('P11_SOURCE_CHECKPOINT' in p08 and
         "'diff','--name-only',REVIEW_HEAD,P11_SOURCE_CHECKPOINT" in p08 and
         'P11_SOURCE_CHECKPOINT,head' in p08,
         'HISTORICAL_P08_REVIEW_NOT_PINNED')
    need('P10_SOURCE_CHECKPOINT' in p10 and
         "'diff','--name-only',P09,P10_SOURCE_CHECKPOINT" in p10,
         'HISTORICAL_P10_REVIEW_NOT_PINNED')
    need('P11_SOURCE_CHECKPOINT' in p11 and
         "'diff','--name-status','--no-renames','-z',P10,P11_SOURCE_CHECKPOINT" in p11 and
         "'diff','--name-status','--no-renames','-z',P11_SOURCE_CHECKPOINT,head" in p11 and
         'p12.check_patch(' in p11,
         'P11_REVIEW_OR_P12_EXTENSION_NOT_PINNED')

def check_populated_test(code: str):
    # Preserve six real Compose test methods, literal screenshot calls and
    # production components; no local Play, network or installer integrations.
    need(code.count('    @Test\n') == 6, 'POPULATED_SIX_TESTS')
    for marker in ('StreamCarousel(', 'SearchResultListItem(', 'Details(app = app)',
                   'TopChartsBody(', 'CategoriesBody(', 'AppUpdateItem(',
                   'R4ScreenshotEvidence.capture(', 'invalid.aurora.p12',
                   'r4_populated_for_you.png', 'r4_populated_search.png',
                   'r4_populated_details.png', 'r4_populated_charts.png',
                   'r4_populated_categories.png', 'r4_populated_install_controls.png'):
        need(marker in code, 'POPULATED_MISSING_'+marker)
    for forbidden in ('HttpURLConnection(', 'OkHttpClient(', 'PackageInstaller(',
                      'GPlayApi(', 'Thread.sleep(', 'adb install'):
        need(forbidden not in code, 'POPULATED_FORBIDDEN_'+forbidden)

def verify(root: Path):
    root=root.resolve(strict=True)
    head=git(root,'rev-parse','HEAD')
    need(re.fullmatch('[a-f0-9]{40}',head) is not None,'INVALID_HEAD')
    need(subprocess.run(['git','merge-base','--is-ancestor',P11,head],cwd=root).returncode==0,
         'P11_NOT_ANCESTOR')
    need(not git(root,'diff','--name-only','HEAD') and
         not git(root,'diff','--cached','--name-only'), 'DIRTY_TRACKED_TREE')
    paths=set(git(root,'diff','--name-only',P11,'HEAD').splitlines())
    need(paths==ALLOWED, 'P12_CHANGED_FILE_ALLOWLIST_'+repr(sorted(paths^ALLOWED)))
    preimage=git(root,'show',P11+':'+PLACEHOLDER)
    current=(root/PLACEHOLDER).read_text(encoding='utf-8').strip()
    check_patch(preimage,current)
    for path,(old,new) in SMALL_EXPOSURES.items():
        before=git(root,'show',P11+':'+path)
        after=(root/path).read_text(encoding='utf-8').strip()
        need(before.count(old)==1 and after==before.replace(old,new,1),
             'UNQUALIFIED_PRODUCTION_CHANGE_'+path)
    check_populated_test((root/POPULATED_TEST).read_text(encoding='utf-8'))
    runner=(root/'scripts/ci/r4_p05_emulator_acceptance.sh').read_text()
    need('run_suite "r4-populated-$mode"' in runner and
         'R4PopulatedCatalogDeviceTest.kt' in runner and
         all(name in runner for name in ('r4_populated_for_you.png','r4_populated_search.png',
            'r4_populated_details.png','r4_populated_charts.png',
            'r4_populated_categories.png','r4_populated_install_controls.png')),
         'HOSTED_POPULATED_CAPTURE_NOT_WIRED')
    check_pixel_source((root/PIXEL_AUDIT).read_text(),
                       (root/PIXEL_TESTS).read_text())
    check_history_guards(*[(root/path).read_text() for path in (
        'scripts/ci/r4_p08_retained_decisions.py',
        'scripts/ci/r4_p10_readiness_gate.py',
        'scripts/ci/r4_p11_pr_review_gate.py')])
    check_workflow((root/WORKFLOW).read_text())
    check_status(json.loads((root/STATUS).read_text()))
    import r4_p11_pr_review_gate as p11
    prior=p11.verify(root)
    need(prior.get('hosted_prior_p09_device_tests')==52 and
         prior.get('hosted_prior_p09_screenshots')==25 and
         prior.get('release_qualified') is False,'PRIOR_EVIDENCE_NOT_PRESERVED')
    return {'source_sha':head,'fix':'onSurface dark Updates label',
            'prior_p09_evidence_historical':True,'fresh_emulator_required':True,
            'all_upstream_visual_parity_approved':False,'release_qualified':False}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,default=Path('.'))
    args=ap.parse_args()
    out=verify(args.root)
    print('R4_P12_EXACT_P11_SOURCE_AND_CONTRAST_PATCH_PASS',out['source_sha'])
    print('R4_P12_FRESH_64_TEST_37_SCREENSHOT_EMULATOR_REQUIRED')
    print('R4_P12_MANUAL_UPSTREAM_PIXEL_FIDELITY_AND_RELEASE_NOT_QUALIFIED')

if __name__=='__main__':
    try: main()
    except (Refused,ValueError,OSError,KeyError,TypeError) as exc:
        print(str(exc),file=sys.stderr)
        sys.exit(2)
