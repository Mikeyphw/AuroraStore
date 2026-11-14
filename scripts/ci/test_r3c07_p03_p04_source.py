#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R3C07 P03/P04 consolidated safety and exact opt-in source contract."""
from __future__ import annotations
from pathlib import Path
import ast,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
FLOW=(ROOT/'.github/workflows/aurora-r1d-emulator.yml').read_text()
RUNNER=(ROOT/'scripts/ci/r3c03_c02_emulator_ci.sh').read_text()
AGG=(ROOT/'scripts/ci/test_r3c04_full_import.py').read_text()
HOST=(ROOT/'scripts/ci/r3c07_p03_talkback.py').read_text()
P04=(ROOT/'scripts/ci/r3c07_p04_os_receipt.py').read_text()
TEST=(ROOT/'app/src/androidTest/java/com/aurora/store/data/artifact/ArtifactTalkBackLiveDeviceTest.kt').read_text()

def require(ok,why):
    if not ok:raise AssertionError('R3C07_P03_P04_SOURCE_REFUSED: '+why)

for path,code in [('host',HOST),('p04',P04)]:
    ast.parse(code,filename=path)

def safe_source(workflow:str,runner:str,host:str,p04:str,device:str)->bool:
    return all((
        workflow.count('r3c07_live_talkback:')==1,
        workflow.count('r3c07_live_installer:')==1,
        workflow.count('uses: ReactiveCircus/android-emulator-runner@')==2,
        workflow.count('script: bash scripts/ci/r1d2_emulator_ci.sh')==1,
        workflow.count("inputs.r3c07_live_installer == true")>=4,
        workflow.count('R3C07_ALLOW_LIVE_TALKBACK:')==1,
        workflow.count('R3C06_ALLOW_LIVE_INSTALL:')==1,
        'inputs.r3c07_live_talkback == true' in workflow,
        "if: ${{ inputs.r3c07_live_installer == true }}" in workflow,
        workflow.count('R3C07_P04_ACTUAL_OS_OUTCOMES_RECEIPT.json')==1,
        workflow.count('scripts/ci/r3c07_p04_os_receipt.py')==1,
        workflow.count('scripts/ci/test_r3c07_p03_p04_source.py')==1,
        workflow.count('R3C07_P03_P04_REFUSED_CONCURRENT_LIVE_GATES')==1,
        "inputs.r3c07_live_talkback }}' == 'true'" in workflow,
        "inputs.r3c07_live_installer }}' == 'true'" in workflow,
        runner.count('bash scripts/ci/r3c07_p02b_api36.sh "$RUNNER" "$OUT"')==1,
        runner.count('scripts/ci/r3c07_p03_talkback.py --run')==1,
        'if [[ "${R3C07_ALLOW_LIVE_TALKBACK:-no}" == yes ]]; then' in runner,
        0 <= runner.find('bash scripts/ci/r3c07_p02b_api36.sh')<
         runner.find('scripts/ci/r3c07_p03_talkback.py --run'),
        "R3C07_ALLOW_LIVE_TALKBACK')=='yes'" in host,
        "getprop','ro.kernel.qemu')=='1'" in host,
        "getprop','ro.build.version.sdk')=='36'" in host,
        'adb(\'shell\',\'dumpsys\',\'accessibility\'' in host,
        "changed=True # arm cleanup BEFORE first mutating command" in host,
        "if restored!=baseline:failures.append('secure settings postimage mismatch')" in host,
        'real_accessibility_focus_gestures_verified' in host,
        'actual_instrumentation_tests\':2' in host,
        "upstream.validate_live(live,sha,run)" in p04,
        "'system_denial_and_acceptance_verified':True" in p04,
        "'fixture_package':upstream.PACKAGE" in p04,
        '--logs "$RUNNER_TEMP/aurora-r3c03-c02"' in workflow,
        device.count('@Test fun ')==2,
        'getUiAutomation(UiAutomation.FLAG_DONT_SUPPRESS_ACCESSIBILITY_SERVICES)' in device,
        'AccessibilityEvent.TYPE_VIEW_ACCESSIBILITY_FOCUSED' in device,
        'manager.getEnabledAccessibilityServiceList(AccessibilityServiceInfo.FEEDBACK_ALL_MASK)' in device,
        'automation.injectInputEvent(event, true)' in device,
        'assertThat(focused[0]).isNotEqualTo(focused[1])' in device,
    ))

require(safe_source(FLOW,RUNNER,HOST,P04,TEST), 'opt-in system, historical gates, actual service/focus and OS receipt incomplete')
for name,which,old,new in [
 ('emulator graph duplicated','flow','script: bash scripts/ci/r1d2_emulator_ci.sh',
  'script: bash scripts/ci/r1d2_emulator_ci.sh\n          script: bash scripts/ci/r1d2_emulator_ci.sh'),
 ('TalkBack flag removed','runner','if [[ "${R3C07_ALLOW_LIVE_TALKBACK:-no}" == yes ]]; then','if true; then'),
 ('concurrent OS guards bypassed','flow','R3C07_P03_P04_REFUSED_CONCURRENT_LIVE_GATES','R3C07_P03_P04_UNSAFE_PARALLEL'),
 ('live install input removed','flow','r3c07_live_installer:','r3c07_unqualified_installer:'),
 ('font/process inherited gate removed','runner','bash scripts/ci/r3c07_p02b_api36.sh "$RUNNER" "$OUT"','echo skip'),
 ('TalkBack no longer checks emulator','host',"getprop','ro.kernel.qemu')=='1'", "getprop','ro.kernel.qemu')=='0'"),
 ('settings cleanup disabled','host',"if restored!=baseline:failures.append('secure settings postimage mismatch')",'pass'),
 ('OS evidence validator removed','p04','upstream.validate_live(live,sha,run)','pass'),
 ('focus tests removed','device','assertThat(focused[0]).isNotEqualTo(focused[1])','assertThat(focused).hasSize(2)'),
]:
    w,r,h,p,d=FLOW,RUNNER,HOST,P04,TEST
    value={'flow':w,'runner':r,'host':h,'p04':p,'device':d}[which]
    require(old in value,'negative anchor absent '+name)
    value=value.replace(old,new,1)
    if which=='flow':w=value
    if which=='runner':r=value
    if which=='host':h=value
    if which=='p04':p=value
    if which=='device':d=value
    require(not safe_source(w,r,h,p,d),'unsafe source mutation accepted '+name)

require(AGG.count("'test_r3c07_p03_p04_source.py'")==1,
        'new source test must run in historical aggregate')
require(AGG.index("'test_r3c07_p02b_source.py'") <
        AGG.index("'test_r3c07_p03_p04_source.py'"),
        'P02B inherited source contracts must run first')
for script,marker in [
 ('scripts/ci/r3c07_p03_talkback.py','R3C07_P03_TALKBACK_RECEIPT_SELFTEST_PASS'),
 ('scripts/ci/r3c07_p04_os_receipt.py','R3C07_P04_OS_RECEIPT_SELFTEST_PASS'),
]:
    result=subprocess.run([sys.executable,'-B',str(ROOT/script),'--selftest'],
                          cwd=ROOT,capture_output=True,text=True,timeout=30)
    require(result.returncode==0 and marker in result.stdout,
            'actual receipt selftest refused '+script+': '+(result.stdout+result.stderr)[-1200:])
print('R3C07_P03_P04_SOURCE_CONTRACT_PASS: 9 safety mutations, two actual receipt selftests, manual-only live TalkBack and OS installation')
