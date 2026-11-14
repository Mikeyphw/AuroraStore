#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Source-constrained hosted P09 review: offline auth storage and UI wiring.

No credential exchange, Google Play login, real device or privileged installer.
Actual AccountProvider preference semantics are tested separately with JUnit
on a hosted API36 emulator. The UI checks here are SOURCE-LEVEL only.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import re
import sys

PATHS={
 'account':'app/src/main/java/com/aurora/store/data/providers/AccountProvider.kt',
 'google':'app/src/main/java/com/aurora/store/compose/ui/accounts/GoogleLoginScreen.kt',
 'auth':'app/src/main/java/com/aurora/store/viewmodel/auth/AuthViewModel.kt',
 'spoof':'app/src/main/java/com/aurora/store/compose/ui/spoof/SpoofScreen.kt',
 'device':'app/src/main/java/com/aurora/store/compose/ui/spoof/DevicePage.kt',
 'locale':'app/src/main/java/com/aurora/store/compose/ui/spoof/LocalePage.kt',
 'androidtest':'app/src/androidTest/java/com/aurora/store/data/providers/R4OfflineAccountSessionDeviceTest.kt',
 'runner':'scripts/ci/r4_p05_emulator_acceptance.sh',
 'auditor':'scripts/ci/r4_p05_screenshot_audit.py',
 'workflow':'.github/workflows/aurora-r4-p05-device-ux.yml',
}

class Refused(RuntimeError): pass

def need(ok:bool, code:str):
 if not ok:raise Refused('R4_P09_REFUSED_'+code)

def section(text:str, start:str, stop:str):
 need(text.count(start)==1,'UNIQUE_START_'+start[:36])
 after=text.split(start,1)[1]
 need(stop in after,'SECTION_END_'+stop[:36])
 return after.split(stop,1)[0]

def check(s:dict[str,str]):
 need(set(s)==set(PATHS),'SOURCE_INVENTORY')
 account=s['account']
 get=section(account,'fun getLoginToken(context: Context)', 'fun login(')
 login=section(account,'fun login(', 'fun logout(')
 logout=account.split('fun logout(',1)[1]
 need('if (email.isBlank() || (aasToken.isBlank() && authToken.isBlank())) return null' in get,
      'EMAIL_OR_MISSING_TOKEN_REJECTED')
 need('return Pair(aasToken.ifBlank { authToken }, tokenType)' in get,
      'TOKEN_TYPE_SELECTION_DRIFT')
 need('require(email.isNotBlank() && token.isNotBlank())' in login,
      'EMPTY_LOGIN_CANNOT_BE_REJECTED')
 need('val editor = Preferences.getPrefs(context).edit()' in login and
      'editor.putBoolean(Constants.ACCOUNT_SIGNED_IN, true)' in login and
      'editor.putString(Constants.ACCOUNT_EMAIL_PLAIN, email)' in login and
      'editor.putString(Constants.ACCOUNT_TYPE, accountType.name)' in login,
      'LOGIN_NOT_SINGLE_TRANSACTION')
 need('if (tokenType == TokenType.AAS)' in login and
      'editor.putString(Constants.ACCOUNT_AAS_PLAIN, token)' in login and
      'editor.remove(Constants.ACCOUNT_AUTH_PLAIN)' in login and
      'editor.putString(Constants.ACCOUNT_AUTH_PLAIN, token)' in login and
      'editor.remove(Constants.ACCOUNT_AAS_PLAIN)' in login and
      'editor.apply()' in login,
      'STALE_TOKEN_SWITCH_OR_COMMIT')
 need('val editor = Preferences.getPrefs(context).edit()' in logout and
      'editor.apply()' in logout and all('editor.remove('+key+')' in logout for key in (
          'PREFERENCE_AUTH_DATA','Constants.ACCOUNT_SIGNED_IN',
          'Constants.ACCOUNT_TYPE','Constants.ACCOUNT_EMAIL_PLAIN',
          'Constants.ACCOUNT_AAS_PLAIN','Constants.ACCOUNT_AUTH_PLAIN',
          'Preferences.PREFERENCE_AUTH_VIA_MICROG')),
      'LOGOUT_TOKEN_OR_IDENTITY_RETAINED')
 google=s['google'];auth=s['auth'];spoof=s['spoof']
 need(re.search(r'if \(addAccount\)\s*\{\s*viewModel\.addGoogleAuthData\(event\.email, event\.token\)\s*\}\s*else\s*\{\s*viewModel\.buildGoogleAuthData\(',google),
      'GOOGLE_ADD_ACCOUNT_DEFAULT_SESSION_SEPARATION')
 need('TokenType.AAS' in google and
      'event.error ?: resources.getString(R.string.toast_aas_token_failed)' in google,
      'GOOGLE_V4_AAS_OR_ERROR_PRESENTATION')
 need('viewModel.accountAdded.collect { error ->' in google and
      'if (error != null) Toast.makeText(context, error, Toast.LENGTH_LONG).show()' in google and
      'onNavigateTo(Destination.Accounts)' in google,
      'GOOGLE_ADD_ACCOUNT_COMPLETION')
 need('makeDefault = false' in auth and
      'authProvider.syncDefaultToPrefs()' in auth and
      '_accountAdded.emit(' in auth and
      'MutableSharedFlow<String?>()' in auth and
      'TokenType.AAS' in auth,
      'AUTH_VIEWMODEL_NONDEFAULT_OR_ERROR_FLOW')
 need('SnackbarResult.ActionPerformed -> onNavigateTo(Destination.Splash())' in spoof and
      'viewModel.logout()' not in spoof and 'onLogout()' not in spoof,
      'SPOOF_RESTART_MUST_NOT_IMPLICITLY_LOGOUT')
 need('onRequestNavigateToSplash = ::onRequestNavigateToSplash' in spoof and
      'onRequestNavigateToSplash()' in s['device'] and
      'onRequestNavigateToSplash()' in s['locale'],
      'SPOOF_DEVICE_LOCALE_RESTART_WIRING')
 device=s['androidtest'];runner=s['runner'];audit=s['auditor'];workflow=s['workflow']
 need(device.count('    @Test\n')==9 and
      'Preferences.getPrefs(context).edit()' in device and
      'check(editor.commit())' in device and
      '@Before' in device and '@After' in device,
      'REAL_EMULATOR_TEST_INVENTORY_OR_CLEANUP')
 need("run_suite 'r4-offline-account-session'" in runner and
      'R4OfflineAccountSessionDeviceTest.kt\' 9' in runner,
      'HOSTED_ACCOUNT_SUITE_NOT_INVOKED')
 need("'r4-offline-account-session': 9" in audit and
      "R4_P09_REAL_EMULATOR_52_TESTS_AND_25_SCREENSHOTS_NONBLANK_UNIQUE_THEME_PASS" in audit and
      "'physical_arm64_qualified':False" in audit and
      "'real_google_account_login_qualified': False" in audit,
      'REAL_EMULATOR_RECEIPT_WEAKENED')
 for marker in ('python3 -B scripts/ci/test_r4_p09_session_source_contract.py',
                'python3 -B scripts/ci/r4_p09_session_source_contract.py --root .',
                'bash scripts/ci/r4_p05_emulator_acceptance.sh',
                'python3 -B scripts/ci/r4_p08_retained_decisions.py --repo .'):
  need(workflow.count(marker)==1,'HOSTED_WORKFLOW_SOURCE_GATE_DRIFT_'+marker)
 need(re.search(r'^  actions: read\b',workflow,re.M) is not None and
      re.search(r'^  contents: read\b',workflow,re.M) is not None and
      re.search(r'^  actions: write\b',workflow,re.M) is None,
      'HOSTED_GITHUB_PERMISSION_DRIFT')
 return {'offline_preference_assertions':9,'screenshot_count':25,
         'total_emulator_assertions':52,'ui_wiring_review':'SOURCE_ONLY',
         'google_play_login_qualified':False,'spoof_restart_ui_qualified':False,
         'physical_arm64_qualified':False,'real_installer_qualified':False,
         'release_qualified':False}

def load(root:Path):
 return {key:(root/path).read_text(encoding='utf-8') for key,path in PATHS.items()}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path('.'))
 args=p.parse_args();result=check(load(args.root.resolve(strict=True)))
 print('R4_P09_ACCOUNT_TOKEN_ISOLATION_AND_ATOMIC_SWITCH_SOURCE_PASS')
 print('R4_P09_GOOGLE_ADD_ACCOUNT_AND_SPOOF_RESTART_SOURCE_ONLY_PASS')
 print('R4_P09_HOSTED_52_TEST_25_SCREENSHOT_OFFLINE_CONTRACT_PASS',result)

if __name__=='__main__':
 try:main()
 except (Refused,OSError) as exc:
  print(str(exc),file=sys.stderr);sys.exit(2)
