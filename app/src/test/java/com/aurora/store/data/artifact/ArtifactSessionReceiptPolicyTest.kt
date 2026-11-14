/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import com.aurora.store.data.artifact.ArtifactSessionReceiptPolicy.Event
import com.aurora.store.data.artifact.ArtifactSessionReceiptPolicy.State
import com.google.common.truth.Truth.assertThat
import org.junit.Test

class ArtifactSessionReceiptPolicyTest {
    @Test
    fun pendingCannotRepeatAndTriggerDuplicateDialog() {
        val waiting = ArtifactSessionReceiptPolicy.next(State.AWAITING_ANDROID, Event.USER_APPROVAL_REQUIRED)
        assertThat(waiting).isEqualTo(State.AWAITING_USER_APPROVAL)
        assertThat(ArtifactSessionReceiptPolicy.next(waiting!!, Event.USER_APPROVAL_REQUIRED)).isNull()
    }
    @Test
    fun installedIsTerminal() {
        assertThat(ArtifactSessionReceiptPolicy.next(State.AWAITING_ANDROID, Event.INSTALLED))
            .isEqualTo(State.INSTALLED_BY_ANDROID)
        for (event in Event.entries) {
            assertThat(ArtifactSessionReceiptPolicy.next(State.INSTALLED_BY_ANDROID, event)).isNull()
        }
    }
    @Test
    fun rejectedIsTerminal() {
        assertThat(ArtifactSessionReceiptPolicy.next(State.AWAITING_USER_APPROVAL, Event.REJECTED))
            .isEqualTo(State.ANDROID_REJECTED)
        for (event in Event.entries) {
            assertThat(ArtifactSessionReceiptPolicy.next(State.ANDROID_REJECTED, event)).isNull()
        }
    }
    @Test
    fun presentationFailureMayBeRetriedOnlyByNewAndroidCallback() {
        val refused = ArtifactSessionReceiptPolicy.next(
            State.AWAITING_USER_APPROVAL, Event.APPROVAL_PRESENTATION_FAILED
        )
        assertThat(refused).isEqualTo(State.APPROVAL_UI_UNAVAILABLE)
        assertThat(ArtifactSessionReceiptPolicy.next(refused!!, Event.USER_APPROVAL_REQUIRED))
            .isEqualTo(State.AWAITING_USER_APPROVAL)
    }
    @Test
    fun presentationFailureBeforePendingCannotChangeReceipt() {
        assertThat(ArtifactSessionReceiptPolicy.next(
            State.AWAITING_ANDROID, Event.APPROVAL_PRESENTATION_FAILED
        )).isNull()
    }
    @Test
    fun successBeforePendingIsAllowedWhenAndroidHasNoPrompt() {
        assertThat(ArtifactSessionReceiptPolicy.next(State.AWAITING_ANDROID, Event.INSTALLED))
            .isEqualTo(State.INSTALLED_BY_ANDROID)
    }
}
