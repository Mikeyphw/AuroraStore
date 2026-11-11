#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""P5 contract: opt-in-only existing R1D workflow; no green from missing OS or matrix evidence."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / '.github/workflows/aurora-r1d-emulator.yml'
R1D = WORKFLOW.read_text(encoding='utf-8')
RUNNER = (ROOT/'scripts/ci/r3c03_c02_emulator_ci.sh').read_text(encoding='utf-8')
CI = (ROOT/'scripts/ci/test_r3c04_full_import.py').read_text(encoding='utf-8')
SCRIPT = ROOT/'scripts/ci/r3c06_p5_manual_receipt.py'
NEGATIVE = ROOT/'scripts/ci/test_r3c06_p5_manual_receipt.py'

for token in ('workflow_dispatch:', 'r3c06_live_install:', 'r3c06_bundletool_matrix:',
              'type: boolean', 'default: false',
              'bundletool-all-1.18.3.jar',
              'a099cfa1543f55593bc2ed16a70a7c67fe54b1747bb7301f37fdfd6d91028e29',
              "R3C06_ALLOW_LIVE_INSTALL:", 'r3c06_p5_manual_receipt.py',
              'R3C06_P5_MANUAL_RECEIPT.json', 'git rev-parse HEAD',
              ':app:bundleVanillaDebug', 'platforms;android-36'):
    assert token in R1D, 'R3C06_P5_SOURCE_REFUSED missing exact workflow guard '+token
for token in ('R3C06_ALLOW_LIVE_INSTALL:-no', 'r3c06_api36_live_install.py',
              'r3c06_bundletool_matrix.py'):
    assert token in RUNNER, 'R3C06_P5_SOURCE_REFUSED inherited real tests lost '+token
assert 'test_r3c06_p5_source_contract.py' in CI, 'P5 missing from targeted source contract'
assert 'import android' not in SCRIPT.read_text(), 'P5 host receipt must remain pure Python'
assert 'aurora-r1d-emulator.yml' in WORKFLOW.as_posix(), 'workflow path mismatch'
assert R1D.count("name: Execute 40 R1D through R1G Android device tests and screenshots") == 1
assert R1D.count('name: Upload source-bound emulator receipt and offline test logs') == 1
# HF05: one clean-snapshot bootstrap, one historical qualification runner.
# Both actions are SHA pinned. The bootstrap must not run any acceptance test.
_emulator_action = 'uses: ReactiveCircus/android-emulator-runner@a421e43855164a8197daf9d8d40fe71c6996bb0d'
_bootstrap_name = '      - name: Generate pre-install AVD snapshot only on cache miss\n'
_qualifier_name = '      - name: Execute 40 R1D through R1G Android device tests and screenshots (KVM/API 36)\n'
_post_name = '      - name: Verify explicitly opted-in R3C06 P5 evidence (no auto-qualification)\n'
assert R1D.count('uses: ReactiveCircus/android-emulator-runner@') == 2, 'duplicate emulator graph'
assert R1D.count(_emulator_action) == 2, 'emulator action identity changed or graph duplicated'
assert all(R1D.count(n) == 1 for n in (_bootstrap_name, _qualifier_name, _post_name)), 'ambiguous emulator step boundaries'
_bootstrap = R1D.split(_bootstrap_name, 1)[1].split(_qualifier_name, 1)[0]
_qualification = R1D.split(_qualifier_name, 1)[1].split(_post_name, 1)[0]
assert _bootstrap.count(_emulator_action) == 1 and _qualification.count(_emulator_action) == 1, 'duplicate qualification emulator graph'
assert _bootstrap.count("if: steps.avd-cache.outputs.cache-hit != 'true'") == 2, 'AVD bootstrap/save not both cache-miss only'
assert 'R3C07_HF03_PREINSTALL_AVD_SNAPSHOT_INITIALIZED' in _bootstrap, 'AVD bootstrap not read-only'
assert R1D.count('uses: actions/cache/restore@8b402f58fbc84540c8b491a91e594a4576fec3d7') == 1, 'clean AVD restore missing'
assert R1D.index('uses: actions/cache/restore@') < R1D.index(_bootstrap_name), 'AVD cache restore not before initializer'
assert _bootstrap.count('uses: actions/cache/save@8b402f58fbc84540c8b491a91e594a4576fec3d7') == 1, 'clean AVD save missing before qualification'
assert _bootstrap.index('R3C07_HF03_PREINSTALL_AVD_SNAPSHOT_INITIALIZED') < _bootstrap.index('uses: actions/cache/save@'), 'AVD cache saved before initializer'
assert 'uses: actions/cache/save@' not in _qualification, 'test state may enter cache'
assert 'bash scripts/ci/r1d2_emulator_ci.sh' not in _bootstrap, 'acceptance tests run in bootstrap'
assert 'bash scripts/ci/r1d2_emulator_ci.sh' in _qualification, 'qualification entrypoint missing'
assert '-no-snapshot-save' in _qualification, 'qualification device state may be saved'
assert R1D.count('bash scripts/ci/r1d2_emulator_ci.sh') == 1, 'qualification entrypoint duplicated'
assert 'R3C06_ALLOW_LIVE_INSTALL' not in R1D.split('name: Build vanillaDebug application and instrumentation APKs')[0], 'non-opted default must be non-destructive'
# P5 HF03: Android 36 'pm path' returns rc=1 for absent package on the
# hosted emulator. A successful, populated user-0 package inventory (including
# Aurora) is required before concluding the fixture is absent. Existing P4
# host-test assertions are updated alongside the driver, not removed.
LIVE = (ROOT/'scripts/ci/r3c06_api36_live_install.py').read_text(encoding='utf-8')
P4_SOURCE = (ROOT/'scripts/ci/test_r3c06_p4_qualification.py').read_text(encoding='utf-8')
P4_TEST = (ROOT/'scripts/ci/test_r3c06_p4_python.py').read_text(encoding='utf-8')
for token in ("'pm', 'list', 'packages', '--user', '0'",
              "'package:' + AURORA in records",
              "return 'package:' + TARGET in records",
              'len(records) == len(set(records))'):
    assert token in LIVE, 'R3C06_P5_HF03_REFUSED weak package-state check: '+token
assert "'pm','path',TARGET" not in LIVE, 'stale Android 36 package-state check'
assert 'test_unexpected_absent_inventory_is_not_evidence_of_package_absence' in P4_TEST
assert 'test_instrumentation_nonzero_retains_failure_log' in P4_TEST
assert 'test_instrumentation_timeout_retains_failure_log' in P4_TEST
assert 'test_prefix_collision_does_not_qualify_fixture_as_installed' in P4_TEST
assert "'pm', 'list', 'packages', '--user', '0'" in P4_SOURCE
assert SCRIPT.is_file() and NEGATIVE.is_file()
result=subprocess.run([sys.executable,'-B',str(NEGATIVE)],cwd=ROOT,
                      capture_output=True,text=True,timeout=30)
assert result.returncode==0, 'R3C06_P5_SOURCE_REFUSED negative regression failed: '+(result.stdout+result.stderr)[-2500:]
assert 'Ran 29 tests' in result.stderr, 'P5 acceptance negative test count stale'

# R3C06 P5 HF04: Android test app UID must stage and remove only its exact
# bounded, hashed synthetic fixture. The ADB shell cannot write app cache.
_live_hf04 = (ROOT / 'scripts/ci/r3c06_api36_live_install.py').read_text(encoding='utf-8')
_test_hf04 = (ROOT / 'app/src/androidTest/java/com/aurora/store/data/artifact/ArtifactActualInstallAcceptanceDeviceTest.kt').read_text(encoding='utf-8')
_p4_hf04 = (ROOT / 'scripts/ci/test_r3c06_p4_python.py').read_text(encoding='utf-8')
assert 'stage_fixture(adb, runner, fixture, evidence)' in _live_hf04, 'HF04 stage missing'
assert 'cleanup_fixture(adb,runner,fixture_digest,evidence)' in _live_hf04, 'HF04 cleanup missing'
assert 'private_app_uid_staging_verified' in _live_hf04, 'HF04 private stage receipt missing'
assert "'run-as'" not in _live_hf04, 'HF04 unsafe run-as cache transfer still present'
assert _test_hf04.count('@Test') == 3, 'HF04 exact three opted-in methods missing'
assert 'context.cacheDir.canonicalFile' in _test_hf04 and 'fileDigest(file) == expected' in _test_hf04
assert _p4_hf04.count('def test_') >= 24, 'HF04 negative source tests missing'
_receipt_hf04=(ROOT/'scripts/ci/r3c06_p5_manual_receipt.py').read_text(encoding='utf-8')
assert "doc.get('private_app_uid_staging_verified') is True" in _receipt_hf04, 'HF04 receipt staging proof missing'
assert "doc.get('private_fixture_cleanup_verified') is True" in _receipt_hf04, 'HF04 receipt cleanup proof missing'
# R3C06 P5 HF05: app-side println is NOT admissible identity evidence.
assert 'sendStatus(0, status)' in _test_hf04, 'HF05 app instrumentation status missing'
for name in ('r3c06_fixture_stage_sha256','r3c06_fixture_cleanup_sha256','r3c06_os_result'):
    assert name in _test_hf04 and name in _live_hf04, 'HF05 structured proof missing '+name
assert 'run_fixture_instrumentation(' in _live_hf04 and 'r3c06-live-install' in _live_hf04
assert 'original acceptance failure:' in _live_hf04, 'HF05 primary error masking still present'
assert "doc.get('instrumentation_status_proof_verified') is True" in _receipt_hf04
for token in ('showForegroundImport(inst)', 'r3c06_foreground_activity', 'hasWindowFocus()'):
    assert token in _test_hf04, 'HF06 background activity guard absent: '+token
for token in ('provision_hosted_unknown_sources(adb)', 'require_foreground_receipt(output)',
              'shutil.rmtree(work)', 'capture_ui_failure_diagnostics(adb, work, scenario)',
              'emulator_unknown_sources_preprovisioned'):
    assert token in _live_hf04, 'HF06 hosted environment/diagnostic guard absent: '+token
assert "doc.get('emulator_unknown_sources_preprovisioned') is True" in _receipt_hf04
assert "r.get('foreground_activity_verified') is True" in _receipt_hf04
# HF07: shell command text cannot substitute for the target app's authoritative
# canRequestPackageInstalls() check. The same AndroidJUnitRunner test must
# transmit an exact, uniquely attested ALLOWED status or remain unqualified.
assert 'packageManager.canRequestPackageInstalls()' in _test_hf04
assert 'reportStatus("r3c06_unknown_sources_effective"' in _test_hf04
assert 'require(canRequest)' in _test_hf04
assert 'r3c06_unknown_sources_effective=ALLOWED' in _live_hf04
assert 'emulator_unknown_sources_effective_verified' in _live_hf04
assert "doc.get('emulator_unknown_sources_effective_verified') is True" in _receipt_hf04
assert 'test_stage_requires_exact_effective_capability_from_target_app' in _p4_hf04
assert 'test_missing_effective_permission_attestation_refuses_live_pass' in NEGATIVE.read_text()
assert "['shell', 'appops', 'set', '--uid', AURORA" in _live_hf04, 'hosted opt-in setter absent'
# HF08: the API36 DENY callback is actually persisted as a typed enum.
# A human-readable lastResult() is not the enum spelling: checking the latter
# in display text caused a false 180-second timeout despite OS REJECTED status.
for token in ('stateForInstallSession(context, session)',
              'preferences.getInt("last_session", -1) == session',
              'preferences.getString(key + "package", null)',
              'preferences.getLong(key + "generation", -1L) > 0L',
              'ArtifactSessionReceiptPolicy.State.entries.firstOrNull',
              'state == ArtifactSessionReceiptPolicy.State.ANDROID_REJECTED',
              'state == ArtifactSessionReceiptPolicy.State.INSTALLED_BY_ANDROID',
              'state == ArtifactSessionReceiptPolicy.State.APPROVAL_UI_UNAVAILABLE',
              'assertThat(state).isEqualTo(ArtifactSessionReceiptPolicy.State.ANDROID_REJECTED)',
              'assertThat(state).isEqualTo(ArtifactSessionReceiptPolicy.State.INSTALLED_BY_ANDROID)'):
    assert token in _test_hf04, 'HF08 exact session state/OS callback missing: '+token
for obsolete in ('if ("INSTALLED_BY_ANDROID" in state || "ANDROID_REJECTED" in state)',
                 'assertThat(state).contains("ANDROID_REJECTED")',
                 'assertThat(state).contains("INSTALLED_BY_ANDROID")'):
    assert obsolete not in _test_hf04, 'HF08 stale UI-text state comparison returned'
assert 'test_real_os_terminal_state_reads_exact_session_not_formatted_receipt' in P4_TEST


# HF09: the prior apksigner v2-only *default output string* was not an
# independent cryptographic proof. Enforce SDK-scoped v2 + real API36 +
# immutable .apks origin + one signer, with a 20-case negative suite. Never
# remove this gate because bundletool (or a matrix fixture) cannot certify
# publisher identity or a device install.
MATRIX = ROOT / 'scripts/ci/r3c06_bundletool_matrix.py'
MATRIX_NEGATIVE = ROOT / 'scripts/ci/test_r3c06_bundletool_security.py'
matrix_src = MATRIX.read_text(encoding='utf-8')
manual_src = SCRIPT.read_text(encoding='utf-8')
for needle in ('def verify_extracted_apk(', 'def archive_apk_index(',
               'minimum=24,maximum=27', 'minimum=36,maximum=36',
               'v2_api24_27_verified', 'api36_verified', 'signed_archive_sha256',
               'signer_sha256', 'fixture_certificate_sha256', 'archive_member', 'filehash(apk)==digest_before',
               'refused_targeting_does_not_count_as_coverage'):
    assert needle in matrix_src, 'HF09 signed matrix evidence missing '+needle
for needle in ("doc.get('run_id') == run_id", 'signed_archive_sha256',
               "require(cov[label] is derived[label]", 'v2_api24_27_verified',
               'results/coverage inventory mismatch'):
    assert needle in manual_src, 'HF09 receipt validator missing '+needle
assert MATRIX_NEGATIVE.is_file(), 'HF09 20 negative tests missing'
security = subprocess.run([sys.executable, '-B', str(MATRIX_NEGATIVE)],
                          cwd=ROOT, capture_output=True,text=True,timeout=30)
assert security.returncode == 0 and 'Ran 37 tests' in security.stderr, \
    'HF10 bundletool security suite failed: '+(security.stdout+security.stderr)[-3000:]
# HF10: a new apksigner label cannot silently evade certificate verification.
for needle in ('OFFICIAL_SHA', 'CERT_RE', 'SIGNER_COUNT_RE',
               'unrecognized certificate signer label',
               'different certificates across signing schemes'):
    assert needle in matrix_src, 'HF10 SDK37 signer evidence missing '+needle
for needle in ('test_sdk37_single_v2_scheme_certificate_parses',
               'test_sdk37_realistic_three_window_selection_is_signed',
               'test_sdk37_multiple_scheme_signers_disagree_refused',
               'test_sdk37_api36_invalid_signature_rc_still_refused'):
    assert needle in MATRIX_NEGATIVE.read_text(), 'HF10 regression missing '+needle
assert 'test_r3c06_p5_source_contract.py' in CI
print('R3C06_P5_SOURCE_CONTRACT_PASS: manual R1D opt-in, pinned bundletool, effective Android permission, foreground OS consent, private signing-key hygiene, 29 receipt regressions and 37 bundletool negatives')
