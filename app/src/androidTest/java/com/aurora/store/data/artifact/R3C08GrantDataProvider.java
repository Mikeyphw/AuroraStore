/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.artifact;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import android.os.Process;
import android.util.Log;
import java.io.File;
import java.io.FileNotFoundException;

/**
 * Instrumentation-APK-only SAF document. Real Android URI grants are required.
 * Use Java/Android framework APIs exclusively because this provider runs in the
 * test APK process, not the target app's Kotlin-enabled class loader.
 */
public final class R3C08GrantDataProvider extends ContentProvider {
    private static final String TAG = "R3C08RemoteProvider";
    @Override public boolean onCreate() {
        Log.i(TAG, "R3C08_PROVIDER_START pid=" + Process.myPid());
        return true;
    }

    private File fixture(Uri uri) throws FileNotFoundException {
        if (!"com.aurora.store.r3c08.document".equals(uri.getAuthority())
                || !("/signed.apk".equals(uri.getPath()) || "/crash.apk".equals(uri.getPath()))) {
            throw new FileNotFoundException("Unknown isolated SAF test URI");
        }
        final android.content.Context ctx = getContext();
        if (ctx == null) throw new FileNotFoundException("No fixture context");
        return new File(ctx.getApplicationInfo().sourceDir);
    }

    @Override public Cursor query(Uri uri, String[] projection, String selection,
                                  String[] selectionArgs, String sortOrder) {
        final File file;
        try { file = fixture(uri); }
        catch (FileNotFoundException error) { throw new IllegalArgumentException("Unknown document", error); }
        final String[] cols = projection != null ? projection :
                new String[] { OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE };
        final Object[] row = new Object[cols.length];
        for (int i = 0; i < cols.length; i++) {
            if (OpenableColumns.DISPLAY_NAME.equals(cols[i])) row[i] = "r3c08-test-signed.apk";
            else if (OpenableColumns.SIZE.equals(cols[i])) row[i] = file.length();
            else throw new IllegalArgumentException("Unsupported fixture metadata column");
        }
        final MatrixCursor result = new MatrixCursor(cols);
        result.addRow(row);
        return result;
    }
    @Override public String getType(Uri uri) {
        try { fixture(uri); }
        catch (FileNotFoundException error) { throw new IllegalArgumentException("Unknown document", error); }
        return "application/vnd.android.package-archive";
    }
    @Override public ParcelFileDescriptor openFile(Uri uri, String mode)
            throws FileNotFoundException {
        if (!"r".equals(mode)) throw new FileNotFoundException("Read-only test fixture");
        final File content = fixture(uri);
        if ("/crash.apk".equals(uri.getPath())) {
            // Test-APK-only remote process deliberately dies while serving the
            // stream. The app, instrumentation runner and control provider
            // live in DIFFERENT processes and must remain alive.
            Log.e(TAG, "R3C08_PROVIDER_KILL pid=" + Process.myPid());
            Process.killProcess(Process.myPid());
            throw new FileNotFoundException("Remote test provider terminated");
        }
        return ParcelFileDescriptor.open(content, ParcelFileDescriptor.MODE_READ_ONLY);
    }
    @Override public Uri insert(Uri uri, ContentValues values) {
        throw new UnsupportedOperationException("Read-only fixture");
    }
    @Override public int update(Uri uri, ContentValues values, String selection,
                                String[] selectionArgs) {
        throw new UnsupportedOperationException("Read-only fixture");
    }
    @Override public int delete(Uri uri, String selection, String[] selectionArgs) {
        throw new UnsupportedOperationException("Read-only fixture");
    }
}
