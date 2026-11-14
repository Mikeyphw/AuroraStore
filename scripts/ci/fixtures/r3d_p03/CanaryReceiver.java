/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.r3d.fixture.history;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/** Deliberately disposable receiver. No production application includes this class. */
public final class CanaryReceiver extends BroadcastReceiver {
    private static final String ACTION = "com.aurora.r3d.fixture.history.CANARY";
    private static final String PREFS = "r3d_disposable_canary";
    @Override public void onReceive(Context context, Intent intent) {
        if (intent == null || !ACTION.equals(intent.getAction())) {
            setResultCode(2);
            setResultData("INVALID_ACTION");
            return;
        }
        String operation = intent.getStringExtra("operation");
        if ("WRITE".equals(operation)) {
            String value = intent.getStringExtra("value");
            if (value == null || !value.matches("[a-f0-9]{48}")) {
                setResultCode(3);
                setResultData("INVALID_CANARY");
                return;
            }
            boolean saved = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().putString("canary", value).commit();
            if (!saved) {
                setResultCode(4);
                setResultData("WRITE_FAILED");
                return;
            }
        } else if (!"READ".equals(operation)) {
            setResultCode(5);
            setResultData("INVALID_OPERATION");
            return;
        }
        String value = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString("canary", null);
        if (value == null) {
            setResultCode(6);
            setResultData("MISSING_CANARY");
            return;
        }
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                .digest(value.getBytes(StandardCharsets.US_ASCII));
            StringBuilder hex = new StringBuilder("sha256:");
            for (byte b : digest) {
                int unsigned = b & 0xff;
                hex.append(Character.forDigit(unsigned >>> 4, 16));
                hex.append(Character.forDigit(unsigned & 0x0f, 16));
            }
            setResultCode(-1);
            setResultData(hex.toString());
        } catch (Exception error) {
            setResultCode(7);
            setResultData("DIGEST_ERROR");
        }
    }
}
