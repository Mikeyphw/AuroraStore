/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.providers

import android.content.Context
import android.content.SharedPreferences
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.aurora.Constants
import com.aurora.gplayapi.session.TokenType
import com.aurora.store.data.model.AccountType
import com.aurora.store.util.Preferences
import com.google.common.truth.Truth.assertThat
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Real API36 emulator assertions against AccountProvider and private SharedPreferences.
 * Credentials are synthetic; no Play requests, network, Android accounts or APK installs.
 * The exact auth preference keys are restored after every test, even on failure.
 */
@RunWith(AndroidJUnit4::class)
class R4OfflineAccountSessionDeviceTest {
    private val context: Context
        get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val keys = listOf(
        Constants.ACCOUNT_SIGNED_IN,
        Constants.ACCOUNT_EMAIL_PLAIN,
        Constants.ACCOUNT_TYPE,
        Constants.ACCOUNT_AAS_PLAIN,
        Constants.ACCOUNT_AUTH_PLAIN,
        Preferences.PREFERENCE_AUTH_DATA,
        Preferences.PREFERENCE_AUTH_VIA_MICROG
    )
    private lateinit var prior: Map<String, Any?>

    @Before
    fun isolate() {
        val prefs = Preferences.getPrefs(context)
        prior = keys.associateWith { key -> prefs.all[key] }
        val editor = prefs.edit()
        keys.forEach { editor.remove(it) }
        check(editor.commit()) { "R4_P09_REFUSED_CANNOT_ISOLATE_ACCOUNT_PREFERENCES" }
    }

    @After
    fun restore() {
        // Restore only the seven auth fields, not unrelated feature preferences.
        val editor: SharedPreferences.Editor = Preferences.getPrefs(context).edit()
        for ((key, value) in prior) {
            when (value) {
                null -> editor.remove(key)
                is String -> editor.putString(key, value)
                is Boolean -> editor.putBoolean(key, value)
                else -> error("R4_P09_REFUSED_UNEXPECTED_AUTH_PREFERENCE_TYPE: $key")
            }
        }
        check(editor.commit()) { "R4_P09_REFUSED_ACCOUNT_PREFERENCE_RESTORE_FAILED" }
    }

    @Test
    fun emailWithoutTokenIsNotUsable() {
        Preferences.putString(context, Constants.ACCOUNT_EMAIL_PLAIN, "synthetic@example.invalid")
        assertThat(AccountProvider.getLoginToken(context)).isNull()
    }

    @Test
    fun tokenWithoutEmailIsNotUsable() {
        Preferences.putString(context, Constants.ACCOUNT_AAS_PLAIN, "synthetic-aas")
        Preferences.putString(context, Constants.ACCOUNT_AUTH_PLAIN, "synthetic-auth")
        assertThat(AccountProvider.getLoginToken(context)).isNull()
    }

    @Test
    fun whitespaceOnlyTokenIsNotUsable() {
        Preferences.putString(context, Constants.ACCOUNT_EMAIL_PLAIN, "synthetic@example.invalid")
        Preferences.putString(context, Constants.ACCOUNT_AAS_PLAIN, " ")
        Preferences.putString(context, Constants.ACCOUNT_AUTH_PLAIN, "   ")
        assertThat(AccountProvider.getLoginToken(context)).isNull()
    }

    @Test
    fun aasLoginStoresOnlyAasToken() {
        AccountProvider.login(context, "synthetic@example.invalid", "synthetic-aas", TokenType.AAS, AccountType.GOOGLE)
        assertThat(AccountProvider.isLoggedIn(context)).isTrue()
        assertThat(AccountProvider.getAccountType(context)).isEqualTo(AccountType.GOOGLE)
        assertThat(AccountProvider.getLoginToken(context)).isEqualTo("synthetic-aas" to TokenType.AAS)
        assertThat(Preferences.getString(context, Constants.ACCOUNT_AUTH_PLAIN)).isEmpty()
    }

    @Test
    fun authLoginStoresOnlyAuthToken() {
        AccountProvider.login(context, "synthetic@example.invalid", "synthetic-auth", TokenType.AUTH, AccountType.GOOGLE)
        assertThat(AccountProvider.getLoginToken(context)).isEqualTo("synthetic-auth" to TokenType.AUTH)
        assertThat(Preferences.getString(context, Constants.ACCOUNT_AAS_PLAIN)).isEmpty()
    }

    @Test
    fun switchingFromAasToAuthDiscardsOldAas() {
        AccountProvider.login(context, "synthetic@example.invalid", "old-aas", TokenType.AAS, AccountType.GOOGLE)
        AccountProvider.login(context, "synthetic@example.invalid", "new-auth", TokenType.AUTH, AccountType.GOOGLE)
        assertThat(AccountProvider.getLoginToken(context)).isEqualTo("new-auth" to TokenType.AUTH)
        assertThat(Preferences.getString(context, Constants.ACCOUNT_AAS_PLAIN)).isEmpty()
    }

    @Test
    fun switchingFromAuthToAasDiscardsOldAuth() {
        AccountProvider.login(context, "synthetic@example.invalid", "old-auth", TokenType.AUTH, AccountType.GOOGLE)
        AccountProvider.login(context, "synthetic@example.invalid", "new-aas", TokenType.AAS, AccountType.GOOGLE)
        assertThat(AccountProvider.getLoginToken(context)).isEqualTo("new-aas" to TokenType.AAS)
        assertThat(Preferences.getString(context, Constants.ACCOUNT_AUTH_PLAIN)).isEmpty()
    }

    @Test
    fun invalidLoginDoesNotWriteAnyIdentityOrToken() {
        var rejected = false
        try {
            AccountProvider.login(context, "synthetic@example.invalid", "   ", TokenType.AUTH, AccountType.GOOGLE)
        } catch (_: IllegalArgumentException) {
            rejected = true
        }
        assertThat(rejected).isTrue()
        assertThat(AccountProvider.isLoggedIn(context)).isFalse()
        assertThat(AccountProvider.getLoginEmail(context)).isNull()
        assertThat(AccountProvider.getLoginToken(context)).isNull()
    }

    @Test
    fun logoutRemovesBothCredentialsAndSessionMarkers() {
        AccountProvider.login(context, "synthetic@example.invalid", "synthetic-aas", TokenType.AAS, AccountType.GOOGLE)
        Preferences.putString(context, Constants.ACCOUNT_AUTH_PLAIN, "orphan-auth")
        Preferences.putString(context, Preferences.PREFERENCE_AUTH_DATA, "synthetic-session")
        Preferences.putBoolean(context, Preferences.PREFERENCE_AUTH_VIA_MICROG, true)
        AccountProvider.logout(context)
        assertThat(AccountProvider.isLoggedIn(context)).isFalse()
        assertThat(AccountProvider.getAccountType(context)).isEqualTo(AccountType.ANONYMOUS)
        assertThat(AccountProvider.getLoginEmail(context)).isNull()
        assertThat(AccountProvider.getLoginToken(context)).isNull()
        for (key in keys) assertThat(Preferences.getPrefs(context).contains(key)).isFalse()
    }
}
