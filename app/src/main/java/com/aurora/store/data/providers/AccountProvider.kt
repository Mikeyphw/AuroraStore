/*
 * SPDX-FileCopyrightText: 2021 Aurora OSS
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

package com.aurora.store.data.providers

import android.content.Context
import com.aurora.Constants
import com.aurora.gplayapi.session.TokenType
import com.aurora.store.data.model.AccountType
import com.aurora.store.util.Preferences
import com.aurora.store.util.Preferences.PREFERENCE_AUTH_DATA

object AccountProvider {

    fun getAccountType(context: Context): AccountType {
        val rawType = Preferences.getString(context, Constants.ACCOUNT_TYPE)
        return when (rawType) {
            "GOOGLE" -> AccountType.GOOGLE
            else -> AccountType.ANONYMOUS
        }
    }

    fun isLoggedIn(context: Context): Boolean =
        Preferences.getBoolean(context, Constants.ACCOUNT_SIGNED_IN, false)

    fun getLoginEmail(context: Context): String? {
        val email = Preferences.getString(context, Constants.ACCOUNT_EMAIL_PLAIN)
        return email.ifBlank { null }
    }

    fun getLoginToken(context: Context): Pair<String, TokenType>? {
        val email = Preferences.getString(context, Constants.ACCOUNT_EMAIL_PLAIN)
        val aasToken = Preferences.getString(context, Constants.ACCOUNT_AAS_PLAIN)
        val authToken = Preferences.getString(context, Constants.ACCOUNT_AUTH_PLAIN)

        // An email by itself is not a usable credential. Never return an empty token.
        if (email.isBlank() || (aasToken.isBlank() && authToken.isBlank())) return null

        val tokenType = if (aasToken.isBlank()) TokenType.AUTH else TokenType.AAS
        return Pair(aasToken.ifBlank { authToken }, tokenType)
    }

    fun login(
        context: Context,
        email: String,
        token: String,
        tokenType: TokenType,
        accountType: AccountType
    ) {
        require(email.isNotBlank() && token.isNotBlank()) {
            "Account identity and authentication token must be nonblank"
        }
        // Keep the account identity, token type and active credential in one
        // preferences transaction. A stale AAS token must not override a newer
        // AUTH login (or vice versa) after switching authentication modes.
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
        // Logout must not expose a partially cleared identity/token pair.
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
}
