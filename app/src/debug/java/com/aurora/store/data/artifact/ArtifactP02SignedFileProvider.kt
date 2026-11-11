/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
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

/**
 * Debug-only, non-exported SAF fixture: exposes the installed, actually signed
 * debug base APK to this app's own document-import activity. No external caller
 * can access this provider, and it never grants install/approval permission.
 */
class ArtifactP02SignedFileProvider : ContentProvider() {
    override fun onCreate(): Boolean = true

    private fun fileFor(uri: Uri): File {
        val app = context ?: throw FileNotFoundException("Provider not initialized")
        return when (uri.path) {
            "/signed.apk" -> File(app.applicationInfo.sourceDir)
            "/invalid.apk" -> File(app.cacheDir, "r3c07-p02-invalid.apk").apply {
                // An intentionally unsigned, bounded file for negative verification.
                if (!isFile || length() != 128L) writeBytes(ByteArray(128) { 0x2a.toByte() })
            }
            else -> throw FileNotFoundException("Unknown test document")
        }
    }

    override fun query(
        uri: Uri,
        projection: Array<out String>?,
        selection: String?,
        selectionArgs: Array<out String>?,
        sortOrder: String?
    ): Cursor {
        val file = fileFor(uri)
        val columns = projection ?: arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE)
        if (columns.any { it != OpenableColumns.DISPLAY_NAME && it != OpenableColumns.SIZE }) {
            throw IllegalArgumentException("Unsupported fixture metadata column")
        }
        return MatrixCursor(columns).apply {
            // Explicit element type: DISPLAY_NAME is String and SIZE is Long.
            // Kotlin 2.4 cannot reify their inferred intersection in toTypedArray().
            val row = Array<Any?>(columns.size) { index ->
                when (columns[index]) {
                    OpenableColumns.DISPLAY_NAME -> if (uri.path == "/signed.apk") {
                        "r3c07-signed-debug.apk"
                    } else {
                        "r3c07-unsigned.apk"
                    }
                    OpenableColumns.SIZE -> file.length()
                    else -> throw IllegalArgumentException("Unsupported column")
                }
            }
            addRow(row)
        }
    }

    override fun getType(uri: Uri): String {
        fileFor(uri)
        return "application/vnd.android.package-archive"
    }

    override fun openFile(uri: Uri, mode: String): ParcelFileDescriptor {
        if (mode != "r") throw FileNotFoundException("Fixture is read-only")
        return ParcelFileDescriptor.open(fileFor(uri), ParcelFileDescriptor.MODE_READ_ONLY)
    }

    override fun insert(uri: Uri, values: ContentValues?): Uri? =
        throw UnsupportedOperationException("Fixture is read-only")

    override fun update(uri: Uri, values: ContentValues?, selection: String?,
                        selectionArgs: Array<out String>?): Int =
        throw UnsupportedOperationException("Fixture is read-only")

    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?): Int =
        throw UnsupportedOperationException("Fixture is read-only")
}
