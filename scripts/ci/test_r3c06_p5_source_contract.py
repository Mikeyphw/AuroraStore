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
assert R1D.count('uses: ReactiveCircus/android-emulator-runner@') == 1, 'duplicate emulator graph'
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
assert 'Ran 17 tests' in result.stderr, 'P5 acceptance negative test count stale'

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
print('R3C06_P5_SOURCE_CONTRACT_PASS: manual R1D opt-in, pinned bundletool, foreground OS consent, private signing-key hygiene, 17 receipt regressions')
