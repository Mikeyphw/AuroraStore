#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Strict exact-SHA/run receipt: twenty-one ACTUAL AndroidJUnitRunner read-only cases.

Source-only self-tests do not qualify Android. The real hosted workflow supplies
instrumentation and package inventories, and validates these before publication.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

CLASS='com.aurora.store.data.artifact.ArtifactR3C08AdversarialDeviceTest'
METHODS=(
 'p02_cancelledLeaseRejectsNewStreamAndClosesOwnedInput',
 'p02_preCancelledPrivateStagingCleansNewDirectory',
 'p02_providerOpenFailureCleansPrivateStageAndDisablesInstall',
 'p02_remoteProviderDeathRefusesImportAndRestartsInNewProcess',
 'p02_failedProviderRetryResetsAllApprovalsAndCleansCache',
 'p03_traversalZipRejectedBeforeExtraction',
 'p03_archiveMetadataCannotOverrideSignedIdentity',
 'p03_conflictingSignedSplitTargetsNeverAutoSelect',
 'p03_localHeaderCrcTamperingRefusedBeforeStaging',
 'p03_centralDirectoryExtentTamperingRefusedBeforeStaging',
 'p03_featureDependencyCyclesAndMissingSplitsRefused',
 'p03_platformIdentityAndSignerHistoryCannotGrantCompatibility',
 'p03_unsupportedAbiAndOrphanConfigTargetsRefused',
 'p04_forgedPublisherEvidenceCannotMintPlayProof',
 'p04_browserAttributionExpiresAndRejectsChangedHostOrSource',
 'p04_apkpureRequiresCurrentOptInAndAlternativeConsent',
 'p04_unverifiedInstalledIdentityAndIndependentApprovalMatrix',
 'p04_terminalInstallerReceiptReplayRefusedByStatePolicy',
 'p04_consentCannotOverrideSignerMismatch',
 'p04_browserClaimsNeverProducePlayOrPublisherProof',
 'p04_downgradeAndUnknownPublisherRequireIndependentConsent',
)
class Refused(ValueError):pass

def need(ok,msg):
    if not ok:raise Refused(msg)
def hashof(b):return hashlib.sha256(b).hexdigest()

def validate(lograw,before,after,head,run_id,provider_log):
    need(re.fullmatch('[a-f0-9]{40}',head) is not None,'invalid exact Git SHA')
    need(run_id.isdecimal() and int(run_id)>0,'missing exact Actions run identity')
    need(250<=len(lograw)<=3_000_000,'instrumentation log absent/oversized')
    try: log=lograw.decode('utf-8')
    except UnicodeError as e:raise Refused('not UTF8 Android log') from e
    for marker in ('FAILURES!!!','INSTRUMENTATION_FAILED','Process crashed',
                   'INSTRUMENTATION_CODE: 0','INSTRUMENTATION_STATUS_CODE: -1',
                   'INSTRUMENTATION_STATUS_CODE: -2'):
        need(marker not in log,'Android failure: '+marker)
    need(CLASS in log,'wrong test class')
    # The provider is a separate instrumentation-APK-owned process. Prove
    # that the intentional exit happened in a different PID than the revived
    # provider. A mere FileNotFoundException is NOT process-death evidence.
    need(100<=len(provider_log)<=200_000,'remote provider lifecycle log missing/oversized')
    try: lifecycle=provider_log.decode('utf-8')
    except UnicodeError as e:raise Refused('provider log not UTF8') from e
    proc_events=re.findall(r'R3C08_PROVIDER_(START|KILL) pid=([0-9]{1,9})',lifecycle)
    need(len(proc_events)>=3, 'missing remote Android provider death/restart trace')
    # Android may kill/restart a flaky isolated provider more than once. Check
    # complete, ordered START -> KILL -> START cycles; never compare the first
    # restart to the LAST killed PID. Every KILL must match the live PID and
    # every revival must use a different PID. Final START need not be killed.
    active=None
    pending_dead=None
    cycles=[]
    for event,pid_s in proc_events:
        pid=int(pid_s)
        need(pid>1, 'invalid remote provider PID')
        if event=='START':
            need(active is None, 'multiple provider starts without an intervening kill')
            if pending_dead is not None:
                need(pid!=pending_dead, 'provider did not restart in a distinct Android process')
                cycles.append((pending_dead,pid))
                pending_dead=None
            active=pid
        else:
            need(active==pid and pending_dead is None,
                 'provider kill is not paired with its live START PID')
            pending_dead=pid
            active=None
    need(len(cycles)>=1 and active is not None and pending_dead is None,
         'provider was not restarted in a distinct real Android process')
    test_markers=re.findall(r'^INSTRUMENTATION_STATUS: test=([A-Za-z0-9_]+)\s*$',log,re.M)
    need(len(test_markers)==42 and set(test_markers)==set(METHODS),
         'missing, duplicate or unexpected Android test marker')
    events=re.findall(r'^INSTRUMENTATION_STATUS: test=([A-Za-z0-9_]+)\s*\n'
                      r'INSTRUMENTATION_STATUS_CODE: ([01])\s*$',log,re.M)
    need(len(events)==42,'real Android start/completion event pairs incomplete')
    for method in METHODS:
        found=[c for name,c in events if name==method]
        need(found==['1','0'],'Android test start/finish missing or reordered: '+method)
    need(len(re.findall(r'^INSTRUMENTATION_STATUS_CODE: 1\s*$',log,re.M))==21,
         'unexpected extra Android test starts')
    need(len(re.findall(r'^INSTRUMENTATION_STATUS_CODE: 0\s*$',log,re.M))==21,
         'unexpected extra Android completion events')
    need(len(re.findall(r'^OK \(21 tests\)\s*$',log,re.M))==1,
         'exact 21-test JUnit success count absent')
    need(len(re.findall(r'^INSTRUMENTATION_CODE: -1\s*$',log,re.M))==1,
         'Android instrumentation final code is not a single success')
    need(before==after and 0<len(before)<=100_000,'OS package inventory changed or absent')
    need(b'\x00' not in before and b'\r' not in before,
         'invalid OS package inventory encoding')
    try: text=before.decode('utf-8')
    except UnicodeError as e:raise Refused('invalid inventory UTF8') from e
    rows=text.splitlines()
    need(rows==sorted(set(rows)) and all(x.startswith('package:') for x in rows),
         'unsorted, repeated or unrecognized package inventory')
    return {'overall':'PASS','phase':'R3C08_P02_P04_ADVERSARIAL_ANDROID_READONLY',
            'source_sha':head,'run_id':run_id,'android_api':36,
            'actual_instrumentation_tests':21,'test_class':CLASS,
            'log_sha256':hashof(lograw),'package_inventory_sha256':hashof(before),
            'isolated_provider_lifecycle_log_sha256':hashof(provider_log),
            'isolated_provider_verified_restart_cycles':len(cycles),
            'package_inventory_unchanged':True,
            'p02_bounded_cancellation_and_controlled_provider_failure_tested':True,
            'p02_isolated_test_provider_actual_process_death_and_restart_tested':True,
            'p02_retry_reset_and_private_cleanup_tested':True,
            'p03_traversal_signed_split_and_metadata_refusals_tested':True,
            'p03_local_and_central_zip_header_corruption_tested':True,
            'p03_feature_dependency_cycle_and_missing_veto_tested':True,
            'p03_signer_history_platform_identity_and_abi_refusals_tested':True,
            'p04_nonplay_consent_and_signer_refusals_tested':True,
            'p04_synthetic_forged_publisher_and_browser_lease_refusals_tested':True,
            'p04_os_session_terminal_state_replay_policy_tested':True,
            'actual_provider_process_death_qualified':False,
            'actual_install_rollback_qualified':False,
            'physical_device_qualified':False,'release_qualified':False,
            'publisher_authenticated':False,'play_delivery_verified':False}

def fake():
    parts=['INSTRUMENTATION_STATUS: class='+CLASS]
    for m in METHODS:
        parts.extend(['INSTRUMENTATION_STATUS: test='+m,'INSTRUMENTATION_STATUS_CODE: 1',
                      'INSTRUMENTATION_STATUS: test='+m,'INSTRUMENTATION_STATUS_CODE: 0'])
    parts.extend(['OK (21 tests)','INSTRUMENTATION_CODE: -1','#'*180])
    return ('\n'.join(parts)+'\n').encode()

def selftest():
    log=fake();before=b'package:com.aurora.store.debug\npackage:com.aurora.store.debug.test\n'
    provider=b'R3C08_PROVIDER_START pid=101\nR3C08_PROVIDER_KILL pid=101\nR3C08_PROVIDER_START pid=102\n'+b'#'*100
    validate(log,before,before,'a'*40,'123',provider)
    substitutions={
      'missing-test':log.replace(METHODS[1].encode(),b'renamedTest',1),
      'duplicate-start':log.replace(b'INSTRUMENTATION_STATUS_CODE: 0',b'INSTRUMENTATION_STATUS_CODE: 1',1),
      'missing-finish':log.replace(b'INSTRUMENTATION_STATUS_CODE: 0',b'not finished',1),
      'extra-test':log+(b'INSTRUMENTATION_STATUS: test=unknown\nINSTRUMENTATION_STATUS_CODE: 1\n'),
      'swapped-order':log.replace(('test='+METHODS[2]+'\nINSTRUMENTATION_STATUS_CODE: 1').encode(),
                                  ('test='+METHODS[2]+'\nINSTRUMENTATION_STATUS_CODE: 0').encode(),1),
      'bad-count':log.replace(b'OK (21 tests)',b'OK (20 tests)'),
      'wrong-terminal':log.replace(b'INSTRUMENTATION_CODE: -1',b'INSTRUMENTATION_CODE: 0'),
      'duplicate-terminal':log+b'INSTRUMENTATION_CODE: -1\n',
      'crashed':log+b'Process crashed.\n',
      'failure':log+b'FAILURES!!!\n',
      'bad-utf8':log+b'\xff',
      'wrong-class':log.replace(CLASS.encode(),b'other.TestClass'),
    }
    # P04-specific fail-closed negative replays: none of the five new
    # adversarial device methods may be omitted or renamed in a passing receipt.
    for p04_method in (
        'p04_forgedPublisherEvidenceCannotMintPlayProof',
        'p04_browserAttributionExpiresAndRejectsChangedHostOrSource',
        'p04_apkpureRequiresCurrentOptInAndAlternativeConsent',
        'p04_unverifiedInstalledIdentityAndIndependentApprovalMatrix',
        'p04_terminalInstallerReceiptReplayRefusedByStatePolicy',
    ):
        broken = log.replace(('INSTRUMENTATION_STATUS: test='+p04_method).encode(),
                             b'INSTRUMENTATION_STATUS: test=removed_P04_case')
        need(broken!=log, 'missing P04 negative replay anchor '+p04_method)
        substitutions['removed-P04-'+p04_method] = broken
    for label,mutant in substitutions.items():
        try:validate(mutant,before,before,'a'*40,'123',provider)
        except Refused:pass
        else:raise AssertionError('unsafe log mutation accepted '+label)
    others=[('wrong-sha',log,before,before,'A'*40,'123'),
            ('wrong-run',log,before,before,'a'*40,'0'),
            ('changed-inventory',log,before,before+b'package:evil\n','a'*40,'123'),
            ('missing-inventory',log,b'',b'','a'*40,'123'),
            ('duplicated-package',log,before+before,before+before,'a'*40,'123'),
            ('unsorted-package',log,bytes(reversed(before.splitlines()[0]))+b'\n',bytes(reversed(before.splitlines()[0]))+b'\n','a'*40,'123')]
    for label,l,b,a,s,r in others:
        try:validate(l,b,a,s,r,provider)
        except Refused:pass
        else:raise AssertionError('unsafe inventory/identity mutation accepted '+label)
    repeated=(b'R3C08_PROVIDER_START pid=101\nR3C08_PROVIDER_KILL pid=101\n'
              b'R3C08_PROVIDER_START pid=102\nR3C08_PROVIDER_KILL pid=102\n'
              b'R3C08_PROVIDER_START pid=103\n')
    need(validate(log,before,before,'a'*40,'123',repeated)['isolated_provider_verified_restart_cycles']==2,
         'two independent true provider crash/restart cycles must qualify')
    for label,mut in (
      ('second-kill-without-start', repeated.replace(b'START pid=102',b'START pid=104')),
      ('second-restart-same-pid', repeated.replace(b'START pid=103',b'START pid=102')),
      ('trailing-kill-no-recovery', repeated.replace(b'START pid=103\n',b'')),
      ('duplicate-start-no-kill', repeated.replace(b'KILL pid=102',b'START pid=102')),
      ('unknown-intermediate-kill', repeated.replace(b'KILL pid=102',b'KILL pid=999')),
    ):
        try:validate(log,before,before,'a'*40,'123',mut)
        except Refused:pass
        else:raise AssertionError('unsafe multicycle provider mutation accepted '+label)
    for name, altered in (
        ('no-kill',provider.replace(b'R3C08_PROVIDER_KILL pid=101',b'R3C08_PROVIDER_IGNORE pid=101')),
        ('same-pid',provider.replace(b'R3C08_PROVIDER_START pid=102',b'R3C08_PROVIDER_START pid=101')),
        ('bad-kill-pid',provider.replace(b'R3C08_PROVIDER_KILL pid=101',b'R3C08_PROVIDER_KILL pid=555')),
        ('reverse-process-order',b'R3C08_PROVIDER_KILL pid=101\nR3C08_PROVIDER_START pid=101\nR3C08_PROVIDER_START pid=102\n'+b'#'*100),
        ('no-provider-log',b''),
        ('bad-provider-utf8',provider+b'\xff'),
    ):
        try:validate(log,before,before,'a'*40,'123',altered)
        except Refused:pass
        else:raise AssertionError('remote provider evidence mutation accepted '+name)
    print('R3C08_P02_P04_RECEIPT_SELFTEST_PASS: 1 synthetic positive, '+str(len(substitutions)+len(others)+11)+' negatives (NOT device evidence)')

def main():
    p=argparse.ArgumentParser();p.add_argument('--selftest',action='store_true')
    for n in ('log','before','after','provider-log','sha','run-id','output'):p.add_argument('--'+n)
    a=p.parse_args()
    if a.selftest:selftest();return
    need(all(getattr(a,n.replace('-','_')) for n in ('log','before','after','provider-log','sha','run-id','output')),
         'missing hosted evidence arguments')
    paths={key:Path(getattr(a,key)) for key in ('log','before','after','provider_log')}
    for label,path in paths.items():
        need(path.is_file() and not path.is_symlink(), 'missing/symlinked evidence '+label)
    need(paths['log'].name=='r3c08_p02_p04_adversarial_ui.txt' and
         paths['before'].name=='r3c08_p02_p04_packages_before.txt' and
         paths['after'].name=='r3c08_p02_p04_packages_after.txt' and
         paths['provider_log'].name=='r3c08_p02_remote_provider_lifecycle.log','wrong evidence names')
    out=Path(a.output)
    need(out.resolve() not in {v.resolve() for v in paths.values()}, 'cannot overwrite as-run evidence')
    receipt=validate(paths['log'].read_bytes(),paths['before'].read_bytes(),
                     paths['after'].read_bytes(),a.sha,a.run_id,paths['provider_log'].read_bytes())
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print('R3C08_P02_P04_SOURCE_BOUND_ANDROID_RECEIPT_PASS sha='+a.sha+' run='+a.run_id)
if __name__=='__main__':
    try:main()
    except (Refused,AssertionError,OSError,ValueError) as e:
        print('R3C08_P02_P04_RECEIPT_REFUSED: '+str(e),file=sys.stderr)
        raise SystemExit(2)
