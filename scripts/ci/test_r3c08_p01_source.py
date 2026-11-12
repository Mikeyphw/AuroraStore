#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R3C08 P01 fail-closed source/host/fixture policy; real device is a separate gate."""
from __future__ import annotations
import pathlib
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=pathlib.Path(__file__).resolve().parents[2]
A=ROOT/'app/src/main/java/com/aurora/store/data/artifact/ArtifactImportActivity.kt'
MANIFEST=ROOT/'app/src/androidTest/AndroidManifest.xml'
TEST=ROOT/'app/src/androidTest/java/com/aurora/store/data/artifact/ArtifactR3C08P01DeviceTest.kt'
DATA=ROOT/'app/src/androidTest/java/com/aurora/store/data/artifact/R3C08GrantDataProvider.java'
RETIRED_DATA=ROOT/'app/src/androidTest/java/com/aurora/store/data/artifact/R3C08GrantDataProvider.kt'
CONTROL=ROOT/'app/src/androidTest/java/com/aurora/store/data/artifact/R3C08GrantControlProvider.java'
RETIRED_CONTROL=ROOT/'app/src/androidTest/java/com/aurora/store/data/artifact/R3C08GrantControlProvider.kt'
RUNNER=ROOT/'scripts/ci/r3c03_c02_emulator_ci.sh'
HOST=ROOT/'scripts/ci/r3c08_p01_api36.sh'
RECEIPT=ROOT/'scripts/ci/r3c08_p01_receipt.py'
CI=ROOT/'.github/workflows/aurora-targeted.yml'
AGG=ROOT/'scripts/ci/test_r3c04_full_import.py'
NS='{http://schemas.android.com/apk/res/android}'

def need(ok: bool, why: str):
    if not ok: raise AssertionError('R3C08_P01_SOURCE_REFUSED: '+why)

for file in (A,MANIFEST,TEST,DATA,CONTROL,RETIRED_DATA,RETIRED_CONTROL,RUNNER,HOST,RECEIPT,CI,AGG):
    need(file.is_file(), 'missing '+str(file))
activity=A.read_text();manifest=MANIFEST.read_text();test=TEST.read_text()
data=DATA.read_text();control=CONTROL.read_text();runner=RUNNER.read_text()
host=HOST.read_text();ci=CI.read_text();agg=AGG.read_text()
retired_data=RETIRED_DATA.read_text();retired_control=RETIRED_CONTROL.read_text()

callback=activity.split('registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->',1)
need(len(callback)==2,'no real picker callback')
callback=callback[1].split('override fun onCreate(',1)[0]
need('invalidateCurrentImport("Document picker closed. No file selected or installed.")' in callback,
     'picker cancellation fails to revoke active verification/cancellation lease')
need('clearReview("Document picker closed.' not in callback,'picker cancel still only repaints UI')
need(callback.count('offerManualRetry()')==1,
     'P03B manual retry must survive picker-dismissal cancellation')
need('cancellation.cancel()' in activity and 'active?.discard()' in activity and
     'requestSerial += 1' in activity,'actual invalidation must invalidate bytes and workers')

tree=ET.fromstring(manifest)
need(len(tree.findall('application/provider'))==2,'fixture/control must be separate test APK providers')
providers={e.get(NS+'authorities'):e for e in tree.findall('application/provider')}
doc=providers.get('com.aurora.store.r3c08.document')
ctl=providers.get('com.aurora.store.r3c08.control')
need(doc is not None and ctl is not None,'test APK providers not registered')
need(doc.get(NS+'readPermission')=='com.aurora.store.r3c08.TEST_SAF_READ' and
     doc.get(NS+'grantUriPermissions')=='true' and doc.get(NS+'exported')=='true',
     'data provider must be protected by a real Android read permission')
need(ctl.get(NS+'exported')=='true' and ctl.get(NS+'readPermission') is None,
     'isolated grant-control provider not reachable by exact target')
need('android:protectionLevel="signature"' in manifest,'private test read permission missing')
need('R3C08GrantDataProvider' not in (ROOT/'app/src/main/AndroidManifest.xml').read_text() and
     'R3C08GrantDataProvider' not in (ROOT/'app/src/debug/AndroidManifest.xml').read_text(),
     'adversarial fixture leaked into production/debug app')
need('getPackagesForUid(Binder.getCallingUid())' in control and
     'Arrays.asList(packages).contains(TARGET)' in control and
     'if (!allowed || arg != null' in control and
     'ctx.grantUriPermission(' in control and 'ctx.revokeUriPermission(' in control and
     'public final class R3C08GrantControlProvider extends ContentProvider' in control,
     'framework-only control provider must authenticate exact target UID and issue/revoke OS grants')
need('ParcelFileDescriptor.MODE_READ_ONLY' in data and
     'public String getType(Uri uri)' in data and
     'final Object[] row = new Object[cols.length]' in data and
     'public final class R3C08GrantDataProvider extends ContentProvider' in data,
     'framework-only test provider must serve read-only actual APK bytes')
need(test.count('@Test fun ') == 3,
     'exact three independent R3C08 Android cases required')
for token in ('checkUriPermission(', 'PackageManager.PERMISSION_DENIED',
              'PackageManager.PERMISSION_GRANTED','openInputStream(doc)',
              'realAndroidUriGrantAndRevocationRejectFreshOpens',
              'revokedDocumentIsRefusedByProductionImportWithoutConsent',
              'cancellingVerifiedSignedFileDiscardsSelectionAndAllConsent',
              '@After fun revokeAnyOutstandingTestGrant()',
              'assertNoActiveSelection(activity)',
              'No verified files','content://com.aurora.store.debug.r3c07p02/signed.apk'):
    need(token in test,'real OS/importer acceptance missing '+token)
for forbidden in ('PackageInstaller.Session', 'su -c', 'adb shell pm install',
                  'PlayVerifiedEvidenceStore', 'startActivity(Intent.ACTION_VIEW'):
    need(forbidden not in test+host+data+control,
         'default R3C08 read-only gate contains unsafe '+forbidden)
need(host.count('adb shell am instrument')==1 and 'OK (3 tests)' in host and
     'INSTRUMENTATION_CODE: -1' in host and 'PIPESTATUS[@]' in host and
     'r3c08_p01_receipt.py' in host,'host does not require actual three Android tests')
need(runner.count('bash scripts/ci/r3c08_p01_api36.sh "$RUNNER" "$OUT"')==1,
     'R3C08 P01 must join the existing API36 emulator graph exactly once')
need(ci.count('python3 -B scripts/ci/test_r3c08_p01_source.py')==1 and
     agg.count("'test_r3c08_p01_source.py'")==1,
     'targeted and inherited source tests must execute new contract')
run=subprocess.run([sys.executable,'-B',str(RECEIPT),'--selftest'],
                   capture_output=True,text=True,timeout=20,cwd=ROOT)
need(run.returncode==0 and '13 negatives' in run.stdout,
     'receipt selftests failed: '+(run.stdout+run.stderr)[-1200:])
# Mutate the actual checker controls, not a disconnected fake implementation.
for label,source,needle,new in (
    ('cancel-only-UI',callback,'invalidateCurrentImport(','clearReview('),
    ('removed-private-read-permission',manifest,'android:readPermission=','android:fakePermission='),
    ('missing-revoke',control,'ctx.revokeUriPermission(','ctx.grantUriPermission('),
    ('removed-uid-auth',control,'Arrays.asList(packages).contains(TARGET)','true'),
    ('host-bypass-count',host,"grep -Fxq 'OK (3 tests)'",'true # unsafe'),
    ('runner-omitted',runner,'bash scripts/ci/r3c08_p01_api36.sh','echo skipped'),
):
    altered=source.replace(needle,new,1)
    need(altered!=source,'negative mutation anchor missing '+label)
    if label=='cancel-only-UI':need('invalidateCurrentImport("Document picker closed.' not in altered,
                                      'cancel-only mutation ineffective')
    elif label=='removed-private-read-permission':need('android:readPermission="com.aurora.store.r3c08.TEST_SAF_READ"' not in altered,
                                                       'manifest mutation ineffective')
    elif label=='missing-revoke':need('ctx.revokeUriPermission(' not in altered,'revoke mutation ineffective')
    elif label=='removed-uid-auth':need('Arrays.asList(packages).contains(TARGET)' not in altered,'UID mutation ineffective')
    elif label=='host-bypass-count':need("grep -Fxq 'OK (3 tests)'" not in altered,'host mutation ineffective')
    else:need('bash scripts/ci/r3c08_p01_api36.sh "$RUNNER" "$OUT"' not in altered,
              'runner mutation ineffective')
# HF02: never invoke the remote provider on the cancellation-only case;
# always preserve grant cleanup when a grant may have been issued. The host
# must capture AndroidRuntime crashes into the always-uploaded evidence folder.
for token in ('private var grantMayExist = false',
              'if (method == "grant") grantMayExist = true',
              'if (method == "revoke") grantMayExist = false',
              'if (grantMayExist) control("revoke")',
              'assertThat(grantMayExist).isFalse()'):
    need(token in test,'HF02 conditional grant cleanup absent: '+token)
for token in ('TARGET=' + chr(39) + 'com.aurora.store.debug' + chr(39),
              'adb shell am force-stop "$TARGET"',
              'trap ' + chr(39) + 'failure_diagnostics "$?"' + chr(39) + ' EXIT',
              'adb logcat -d -b crash',
              'r3c08_p01_android_crash_diagnostics.txt',
              'AndroidRuntime:E', 'tail -n 100 "$report"'):
    need(token in host,'HF02 bounded and artifact-uploaded failure diagnostics absent: '+token)
for label,actual,old,new in (
    ('cleanup-unguarded',test,'if (grantMayExist) control("revoke")',
      'control("revoke")'),
    ('grant-tracking-removed',test,'if (method == "grant") grantMayExist = true',
      'grantMayExist = false'),
    ('cleanup-reset-removed',test,'if (method == "revoke") grantMayExist = false',
      'grantMayExist = true'),
    ('no-force-stop',host,'adb shell am force-stop "$TARGET"',
      'echo forced'),
    ('missing-crash-collection',host,'adb logcat -d -b crash',
      'echo logcat'),
    ('missing-EXIT-trap',host,'trap ' + chr(39) + 'failure_diagnostics "$?"' + chr(39) + ' EXIT',
      'echo diagnostics'),
):
    altered=actual.replace(old,new,1)
    need(altered!=actual,'HF02 mutation anchor absent: '+label)
    need(old not in altered,'HF02 mutation ineffective: '+label)
print('R3C08_P01_HF02_GUARDED_CLEANUP_AND_CRASH_DIAGNOSTICS_PASS: six negative mutations')
# HF03: providers are actually loaded in the separate .test APK process;
# Kotlin's Intrinsics are not on its classpath. They MUST be framework-only Java.
for name,java,stub in (
    ('R3C08GrantDataProvider',data,retired_data),
    ('R3C08GrantControlProvider',control,retired_control),
):
    need(java.count('public final class '+name+' extends ContentProvider')==1,
         'HF03 separate-process Java ContentProvider absent: '+name)
    need('package com.aurora.store.data.artifact;' in java,
         'HF03 provider package differs from AndroidManifest: '+name)
    need('import kotlin.' not in java and 'kotlin.jvm.internal.' not in java,
         'HF03 test-APK provider links Kotlin runtime')
    need('R3C08_P01_HF03_PROVIDER_MOVED_TO_FRAMEWORK_ONLY_JAVA' in stub and
         'class '+name not in stub,
         'HF03 conflicting Kotlin ContentProvider still declared: '+name)
need('private static final String TARGET = "com.aurora.store.debug";' in control and
     'if (!allowed || arg != null || (extras != null && !extras.isEmpty()))' in control,
     'HF03 exact target package, caller authorization or extras rejection weakened')
need('"grant".equals(method)' in control and '"revoke".equals(method)' in control and
     'throw new IllegalArgumentException("Unknown fixture control")' in control,
     'HF03 missing exact grant/revoke/unknown-method policy')
need('!"r".equals(mode)' in data and '"/signed.apk".equals(uri.getPath())' in data,
     'HF03 read-only path/mode gate removed')
for label,whole,old,new,required in (
    ('reintroduce-Kotlin-control',retired_control,'// R3C08_P01_HF03_PROVIDER_MOVED_TO_FRAMEWORK_ONLY_JAVA',
        'class R3C08GrantControlProvider : ContentProvider()','class R3C08GrantControlProvider'),
    ('reintroduce-Kotlin-data',retired_data,'// R3C08_P01_HF03_PROVIDER_MOVED_TO_FRAMEWORK_ONLY_JAVA',
        'class R3C08GrantDataProvider : ContentProvider()','class R3C08GrantDataProvider'),
    ('remove-UID-gate',control,'Arrays.asList(packages).contains(TARGET)','true',
        'Arrays.asList(packages).contains(TARGET)'),
    ('remove-control-readonly',control,'throw new SecurityException("Control endpoint cannot serve document bytes")',
        'return null','throw new SecurityException("Control endpoint cannot serve document bytes")'),
    ('allow-write-data',data,'if (!"r".equals(mode))','if (false)',
        'if (!"r".equals(mode))'),
    ('remove-revoke',control,'ctx.revokeUriPermission(','ctx.grantUriPermission(',
        'ctx.revokeUriPermission('),
    ('remove-validation-method',control,'throw new IllegalArgumentException("Unknown fixture control")',
        'return new Bundle()','throw new IllegalArgumentException("Unknown fixture control")'),
):
    mutated=whole.replace(old,new,1)
    need(mutated != whole and (required in mutated if label.startswith('reintroduce-') else required not in mutated),
         'HF03 negative mutation ineffective: '+label)
print('R3C08_P01_HF03_JAVA_TEST_APK_CLASSLOADER_GUARD_PASS: 7 mutation cases')
print('R3C08_P01_SOURCE_PASS: independent actual Android URI grant/revoke fixture, fail-closed cancel, 3 API36 cases, 13 receipt negatives and 6 source mutations')
