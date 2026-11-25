#!/usr/bin/env python3
"""Source contract for bundled R1D2; hosted JVM/emulator CI validates behavior."""
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import re
import sys
from xml.etree import ElementTree
r = Path(__file__).resolve().parents[2]
def read(path): return (r/path).read_text()
worker = read('app/src/main/java/com/aurora/store/data/work/DownloadWorker.kt')
policy = read('app/src/main/java/com/aurora/store/data/work/ResumeRangePolicy.kt')
unit = read('app/src/test/java/com/aurora/store/data/work/ResumeRangePolicyTest.kt')
http = read('app/src/androidTest/java/com/aurora/store/data/work/OfflineHttpResumeDeviceTest.kt')
work = read('app/src/androidTest/java/com/aurora/store/data/work/OfflineWorkManagerDeviceTest.kt')
debug = read('app/src/debug/java/com/aurora/store/data/work/OfflineAttemptWorker.kt')
manifest = read('app/src/debug/AndroidManifest.xml')
net = read('app/src/debug/res/xml/r1d2_debug_network_security.xml')
script = read('scripts/ci/r1d2_emulator_ci.sh')
flow = read('.github/workflows/aurora-r1d-emulator.yml')


def debug_loopback_only(document):
    """Require exact debug cleartext scope; reject subdomain/broad-domain expansion."""
    try:
        root = ElementTree.fromstring(document)
    except ElementTree.ParseError:
        return False
    if root.tag != 'network-security-config' or root.attrib or len(root) != 2:
        return False
    base, domain_config = root
    if (base.tag != 'base-config' or
        base.attrib != {'cleartextTrafficPermitted': 'false'} or len(base)):
        return False
    if (domain_config.tag != 'domain-config' or
        domain_config.attrib != {'cleartextTrafficPermitted': 'true'} or
        len(domain_config) != 2):
        return False
    domains = list(domain_config)
    if any(domain.tag != 'domain' or len(domain) or
           domain.attrib != {'includeSubdomains': 'false'} for domain in domains):
        return False
    return sorted((domain.text or '').strip() for domain in domains) == [
        '127.0.0.1', 'localhost'
    ]


# Negative fixtures are validated on every source-contract invocation.
# Relaxing this checker must not allow broadened or malformed debug cleartext.
negative_xml = {
    'base-cleartext': net.replace('cleartextTrafficPermitted="false"',
                                  'cleartextTrafficPermitted="true"', 1),
    'wildcard-subdomains': net.replace('includeSubdomains="false"',
                                      'includeSubdomains="true"', 1),
    'omitted-subdomain-guard': net.replace(' includeSubdomains="false"', '', 1),
    'non-loopback-domain': net.replace('localhost', 'example.org', 1),
    'additional-domain': net.replace('</domain-config>',
        '<domain includeSubdomains="false">example.org</domain></domain-config>', 1),
    'missing-loopback': net.replace(
        '<domain includeSubdomains="false">localhost</domain>', '', 1),
    'extra-debug-overrides': net.replace('</network-security-config>',
        '<debug-overrides /></network-security-config>', 1),
    'malformed-xml': net[:len(net)//2],
}
if not debug_loopback_only(net) or any(
    debug_loopback_only(candidate) for candidate in negative_xml.values()
):
    print('R1D2_LOOPBACK_SECURITY_REGRESSION_FAIL', file=sys.stderr)
    sys.exit(1)
print(f'R1D2_LOOPBACK_SECURITY_NEGATIVE_PASS cases={len(negative_xml)}')

checks = {
 'range validated before append': 'ResumeRangePolicy.matches(range, existingBytes)' in worker and 'if (returnedStart != existingBytes)' in worker,
 'zero-offset 206 validated': 'ResumeRangePolicy.matches(response.header("Content-Range"), 0L)' in worker,
 '416 handled through strict policy': 'ResumeRangePolicy.requiresRestart(code, existingBytes)' in worker,
 'bounds and total checked': 'start == expectedStart && end >= start' in ' '.join(policy.split()) and 'end < total' in policy,
 'five executable JVM tests': len(re.findall(r'@Test\s+fun ',unit)) == 5,
 'six offline HTTP socket device tests': len(re.findall(r'@Test\s+fun ',http)) == 6 and 'ServerSocket(' in http and 'call.cancel()' in http,
 'four real WorkManager device tests': len(re.findall(r'@Test\s+fun ',work)) == 4 and 'WorkManager.getInstance(context)' in work,
 'worker fixture debug-only and executable': 'class OfflineAttemptWorker' in debug and 'OfflineAttemptWorker>()' in work,
 'process restart executed between WorkManager phases': 'adb shell am force-stop "$TARGET"' in script and script.index('run_suite work-seed ') < script.index('adb shell am force-stop ') < script.index('run_suite work-reopen '),
 'cleartext limited to debug loopback': 'r1d2_debug_network_security' in manifest and debug_loopback_only(net),
 'old and new cases required': 'bash scripts/ci/r1d_emulator_ci.sh' in script and 'run_suite http "$HTTP" 6' in script and "'total_device_tests': 24" in script,
 'fail-closed command, exact test counts': 'INSTRUMENTATION_FAILED' in script and 'expected $expected successful tests' in script and "'overall': 'PASS'" in script,
 'one existing pinned API36 workflow': 'script: bash scripts/ci/r1d2_emulator_ci.sh' in flow and 'python3 -B scripts/ci/check_r1d2.py' in flow and 'api-level: 36' in flow and 'ReactiveCircus/android-emulator-runner@a421e43855164a8197daf9d8d40fe71c6996bb0d' in flow,
 'both receipts uploaded': 'R1D2_EMULATOR_RECEIPT.json' in flow and 'aurora-r1d-emulator/' in flow and 'aurora-r1d2-emulator/' in flow,
 'no live production download is claimed': "'google_play_delivery_performed': False" in script and "'production_download_worker_executed': False" in script,
}
for name, ok in checks.items(): print(('PASS ' if ok else 'FAIL ') + name)
if not all(checks.values()):
    print('R1D2_CONTRACT_FAIL',file=sys.stderr)
    sys.exit(1)
print(f'R1D2_CONTRACT_PASS checks={len(checks)}')
