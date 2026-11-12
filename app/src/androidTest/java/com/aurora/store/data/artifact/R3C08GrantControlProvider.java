/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.artifact;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.os.Binder;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import java.util.Arrays;

/**
 * Instrumentation-APK-only control endpoint. Runs in the TEST APK's own process.
 * Uses only Android/Java APIs: this process is not entitled to use the target
 * app's Kotlin runtime. A missing Kotlin runtime must never crash Binder.
 * No production, Play, or installation capability is exposed.
 */
public final class R3C08GrantControlProvider extends ContentProvider {
    private static final String TARGET = "com.aurora.store.debug";
    private static final Uri DOCUMENT = Uri.parse(
            "content://com.aurora.store.r3c08.document/signed.apk");

    @Override public boolean onCreate() { return true; }

    @Override public Bundle call(String method, String arg, Bundle extras) {
        final android.content.Context ctx = getContext();
        if (ctx == null) throw new SecurityException("No fixture context");
        final String[] packages = ctx.getPackageManager().getPackagesForUid(Binder.getCallingUid());
        // Exact Android-authenticated caller UID, not a string supplied in extras.
        final boolean allowed = packages != null && Arrays.asList(packages).contains(TARGET);
        if (!allowed || arg != null || (extras != null && !extras.isEmpty())) {
            throw new SecurityException("Only the exact instrumented target may control test grants");
        }
        if ("grant".equals(method)) {
            ctx.grantUriPermission(TARGET, DOCUMENT, Intent.FLAG_GRANT_READ_URI_PERMISSION);
        } else if ("revoke".equals(method)) {
            ctx.revokeUriPermission(TARGET, DOCUMENT, Intent.FLAG_GRANT_READ_URI_PERMISSION);
        } else {
            throw new IllegalArgumentException("Unknown fixture control");
        }
        final Bundle reply = new Bundle();
        reply.putString("r3c08_result", method);
        return reply;
    }

    @Override public String getType(Uri uri) { return null; }
    @Override public Cursor query(Uri uri, String[] projection, String selection,
                                  String[] selectionArgs, String sortOrder) { return null; }
    @Override public ParcelFileDescriptor openFile(Uri uri, String mode) {
        throw new SecurityException("Control endpoint cannot serve document bytes");
    }
    @Override public Uri insert(Uri uri, ContentValues values) {
        throw new UnsupportedOperationException("No writes");
    }
    @Override public int update(Uri uri, ContentValues values, String selection,
                                String[] selectionArgs) {
        throw new UnsupportedOperationException("No writes");
    }
    @Override public int delete(Uri uri, String selection, String[] selectionArgs) {
        throw new UnsupportedOperationException("No writes");
    }
}
