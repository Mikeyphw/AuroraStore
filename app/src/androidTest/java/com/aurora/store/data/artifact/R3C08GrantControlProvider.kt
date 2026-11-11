/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.artifact

import android.content.ContentProvider
import android.content.ContentValues
import android.content.Intent
import android.database.Cursor
import android.net.Uri
import android.os.Binder
import android.os.Bundle

/** Only in the test APK. The real provider owner issues and revokes actual OS URI grants.
 * This control channel is limited to the exact target-app UID, even on a test device.
 */
class R3C08GrantControlProvider : ContentProvider() {
    private val document = Uri.parse("content://com.aurora.store.r3c08.document/signed.apk")
    private val targetPackage = "com.aurora.store.debug"
    override fun onCreate(): Boolean = true
    override fun call(method: String, arg: String?, extras: Bundle?): Bundle {
        val ctx = requireNotNull(context)
        val packages = ctx.packageManager.getPackagesForUid(Binder.getCallingUid()).orEmpty()
        if (targetPackage !in packages || arg != null || (extras != null && !extras.isEmpty)) {
            throw SecurityException("Only the exact instrumented target may request fixture grants")
        }
        when (method) {
            "grant" -> ctx.grantUriPermission(targetPackage, document, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            "revoke" -> ctx.revokeUriPermission(targetPackage, document, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            else -> throw IllegalArgumentException("Unknown fixture control")
        }
        return Bundle().apply { putString("r3c08_result", method) }
    }
    override fun getType(uri: Uri): String? = null
    override fun query(uri: Uri, projection: Array<out String>?, selection: String?,
        selectionArgs: Array<out String>?, sortOrder: String?): Cursor? = null
    override fun openFile(uri: Uri, mode: String): android.os.ParcelFileDescriptor =
        throw SecurityException("Control endpoint cannot serve document bytes")
    override fun insert(uri: Uri, values: ContentValues?): Uri? =
        throw UnsupportedOperationException("No writes")
    override fun update(uri: Uri, values: ContentValues?, selection: String?,
        selectionArgs: Array<out String>?): Int = throw UnsupportedOperationException("No writes")
    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?): Int =
        throw UnsupportedOperationException("No writes")
}
