/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.artifact

import android.content.ContentProvider
import android.content.ContentValues
import android.database.Cursor
import android.database.MatrixCursor
import android.net.Uri
import android.os.ParcelFileDescriptor
import android.provider.OpenableColumns
import java.io.File
import java.io.FileNotFoundException

/** Instrumentation-APK-only SAF fixture, protected by a real Android URI grant.
 * The signing-valid bytes are the instrumentation APK; no installer is invoked.
 */
class R3C08GrantDataProvider : ContentProvider() {
    override fun onCreate(): Boolean = true
    private fun fixture(uri: Uri): File {
        if (uri.authority != "com.aurora.store.r3c08.document" || uri.path != "/signed.apk") {
            throw FileNotFoundException("Unknown isolated SAF test URI")
        }
        return File(requireNotNull(context).applicationInfo.sourceDir)
    }
    override fun query(uri: Uri, projection: Array<out String>?, selection: String?,
        selectionArgs: Array<out String>?, sortOrder: String?): Cursor {
        val file = fixture(uri)
        val columns = projection ?: arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE)
        require(columns.all { it == OpenableColumns.DISPLAY_NAME || it == OpenableColumns.SIZE })
        return MatrixCursor(columns).apply {
            val row = Array<Any?>(columns.size) { index ->
                if (columns[index] == OpenableColumns.DISPLAY_NAME) "r3c08-test-signed.apk"
                else file.length()
            }
            addRow(row)
        }
    }
    override fun getType(uri: Uri): String {
        fixture(uri)
        return "application/vnd.android.package-archive"
    }
    override fun openFile(uri: Uri, mode: String): ParcelFileDescriptor {
        if (mode != "r") throw FileNotFoundException("Read-only test fixture")
        return ParcelFileDescriptor.open(fixture(uri), ParcelFileDescriptor.MODE_READ_ONLY)
    }
    override fun insert(uri: Uri, values: ContentValues?): Uri? =
        throw UnsupportedOperationException("Read-only fixture")
    override fun update(uri: Uri, values: ContentValues?, selection: String?,
        selectionArgs: Array<out String>?): Int = throw UnsupportedOperationException("Read-only fixture")
    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?): Int =
        throw UnsupportedOperationException("Read-only fixture")
}
