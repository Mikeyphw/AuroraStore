#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""P09 source and workflow fault-injection suite; no Android/Play access."""
from __future__ import annotations
from pathlib import Path
import copy
import r4_p09_session_source_contract as m

ROOT=Path(__file__).resolve().parents[2]


def fixtures():
    # Synthetic check inputs are deliberately small; CI also checks the real
    # Android source tree when all entries exist at repository root.
    return {
      'account': '''
fun getLoginToken(context: Context): Pair<String, TokenType>? {
if (email.isBlank() || (aasToken.isBlank() && authToken.isBlank())) return null
return Pair(aasToken.ifBlank { authToken }, tokenType)
}
fun login(context: Context) {
require(email.isNotBlank() && token.isNotBlank())
val editor = Preferences.getPrefs(context).edit()
editor.putBoolean(Constants.ACCOUNT_SIGNED_IN, true)
editor.putString(Constants.ACCOUNT_EMAIL_PLAIN, email)
editor.putString(Constants.ACCOUNT_TYPE, accountType.name)
if (tokenType == TokenType.AAS) {
editor.putString(Constants.ACCOUNT_AAS_PLAIN, token)
editor.remove(Constants.ACCOUNT_AUTH_PLAIN)
} else {
editor.putString(Constants.ACCOUNT_AUTH_PLAIN, token)
editor.remove(Constants.ACCOUNT_AAS_PLAIN)
}
editor.apply()
}
fun logout(context: Context) {
val editor = Preferences.getPrefs(context).edit()
editor.remove(PREFERENCE_AUTH_DATA)
editor.remove(Constants.ACCOUNT_SIGNED_IN)
editor.remove(Constants.ACCOUNT_TYPE)
editor.remove(Constants.ACCOUNT_EMAIL_PLAIN)
editor.remove(Constants.ACCOUNT_AAS_PLAIN)
editor.remove(Constants.ACCOUNT_AUTH_PLAIN)
editor.remove(Preferences.PREFERENCE_AUTH_VIA_MICROG)
editor.apply()
}
''',
      'google': '''
if (addAccount) {
viewModel.addGoogleAuthData(event.email, event.token)
} else {
viewModel.buildGoogleAuthData(event.email, event.token, TokenType.AAS)
}
Toast.makeText(context, event.error ?: resources.getString(R.string.toast_aas_token_failed), Toast.LENGTH_LONG)
viewModel.accountAdded.collect { error ->
if (error != null) Toast.makeText(context, error, Toast.LENGTH_LONG).show()
onNavigateTo(Destination.Accounts)
}
''',
      'auth': '''
private val _accountAdded = MutableSharedFlow<String?>()
authProvider.persistAccount(makeDefault = false)
authProvider.syncDefaultToPrefs()
_accountAdded.emit(result.exceptionOrNull())
TokenType.AAS
''',
      'spoof': '''
SnackbarResult.ActionPerformed -> onNavigateTo(Destination.Splash())
onRequestNavigateToSplash = ::onRequestNavigateToSplash
''',
      'device':'onRequestNavigateToSplash()',
      'locale':'onRequestNavigateToSplash()',
      'androidtest':'''@Before
val editor = Preferences.getPrefs(context).edit()
check(editor.commit())
@After
'''+('    @Test\n'*9),
      'runner':"run_suite 'r4-offline-account-session' \\\n  'com.aurora.store.data.providers.R4OfflineAccountSessionDeviceTest' \\\n  'app/src/androidTest/java/com/aurora/store/data/providers/R4OfflineAccountSessionDeviceTest.kt' 9\n",
      'auditor':"'r4-offline-account-session': 9\nR4_P09_REAL_EMULATOR_52_TESTS_AND_25_SCREENSHOTS_NONBLANK_UNIQUE_THEME_PASS\n'physical_arm64_qualified':False\n'real_google_account_login_qualified': False\n",
      'workflow':'''permissions:
  contents: read
  actions: read
python3 -B scripts/ci/test_r4_p09_session_source_contract.py
python3 -B scripts/ci/r4_p09_session_source_contract.py --root .
bash scripts/ci/r4_p05_emulator_acceptance.sh
python3 -B scripts/ci/r4_p08_retained_decisions.py --repo .
'''
    }


def refuse(changed, old, new, code):
    candidate=copy.deepcopy(changed)
    key,source=old
    assert candidate[key].count(source)>=1,(key,source)
    candidate[key]=candidate[key].replace(source,new,1)
    try:m.check(candidate)
    except m.Refused as e:
        assert code in str(e), (code,str(e))
    else:raise AssertionError('R4_P09_NEGATIVE_ACCEPTED_'+code)


def main():
    fixture=fixtures();doc=m.check(fixture)
    assert doc['offline_preference_assertions']==9
    assert doc['total_emulator_assertions']==52
    assert doc['screenshot_count']==25
    assert doc['release_qualified'] is False
    count=0
    checks=[
       ('account','if (email.isBlank() || (aasToken.isBlank() && authToken.isBlank())) return null','if (email.isBlank() && (aasToken.isBlank() || authToken.isBlank())) return null','EMAIL_OR_MISSING_TOKEN_REJECTED'),
       ('account','require(email.isNotBlank() && token.isNotBlank())','','EMPTY_LOGIN_CANNOT_BE_REJECTED'),
       ('account','editor.remove(Constants.ACCOUNT_AUTH_PLAIN)','// forgot to clear old token','STALE_TOKEN_SWITCH_OR_COMMIT'),
       ('account','editor.remove(Constants.ACCOUNT_AAS_PLAIN)','// forgot to clear old token','STALE_TOKEN_SWITCH_OR_COMMIT'),
       ('account','editor.putString(Constants.ACCOUNT_EMAIL_PLAIN, email)','editor.putString(Constants.ACCOUNT_EMAIL_PLAIN, "")','LOGIN_NOT_SINGLE_TRANSACTION'),
       ('account','editor.remove(PREFERENCE_AUTH_DATA)','// lost logout cleanup','LOGOUT_TOKEN_OR_IDENTITY_RETAINED'),
       ('account','editor.remove(Preferences.PREFERENCE_AUTH_VIA_MICROG)','// lost microG marker cleanup','LOGOUT_TOKEN_OR_IDENTITY_RETAINED'),
       ('google','viewModel.addGoogleAuthData(event.email, event.token)','viewModel.buildGoogleAuthData(event.email, event.token, TokenType.AAS)','GOOGLE_ADD_ACCOUNT_DEFAULT_SESSION_SEPARATION'),
       ('google','event.error ?: resources.getString(R.string.toast_aas_token_failed)','resources.getString(R.string.toast_aas_token_failed)','GOOGLE_V4_AAS_OR_ERROR_PRESENTATION'),
       ('google','viewModel.accountAdded.collect { error ->','viewModel.authState.collect { error ->','GOOGLE_ADD_ACCOUNT_COMPLETION'),
       ('auth','makeDefault = false','makeDefault = true','AUTH_VIEWMODEL_NONDEFAULT_OR_ERROR_FLOW'),
       ('spoof','SnackbarResult.ActionPerformed -> onNavigateTo(Destination.Splash())','SnackbarResult.ActionPerformed -> viewModel.logout()','SPOOF_RESTART_MUST_NOT_IMPLICITLY_LOGOUT'),
       ('runner',"R4OfflineAccountSessionDeviceTest.kt' 9", "R4OfflineAccountSessionDeviceTest.kt' 8", 'HOSTED_ACCOUNT_SUITE_NOT_INVOKED'),
       ('auditor',"'r4-offline-account-session': 9", "'r4-offline-account-session': 0", 'REAL_EMULATOR_RECEIPT_WEAKENED'),
       ('workflow','  actions: read','  actions: write','HOSTED_GITHUB_PERMISSION_DRIFT'),
    ]
    for key,old,new,marker in checks:
        refuse(fixture,(key,old),new,marker);count+=1
    assert count==15
    # This also runs on GitHub; never claim a source fixture is a real device test.
    if all((ROOT/path).is_file() for path in m.PATHS.values()):
        live=m.check(m.load(ROOT))
        assert live['offline_preference_assertions']==9
        print('R4_P09_ACTUAL_REPO_ACCOUNT_AND_UI_SOURCE_CONTRACT_PASS')
    print('R4_P09_FIFTEEN_SOURCE_AND_PERMISSION_MUTATION_REFUSALS_PASS')

if __name__=='__main__':main()
