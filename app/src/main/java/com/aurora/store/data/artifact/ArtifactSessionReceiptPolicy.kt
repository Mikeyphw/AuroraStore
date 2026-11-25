/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

/** Fail-closed state machine for each OS-owned PackageInstaller session. */
internal object ArtifactSessionReceiptPolicy {
    enum class State {
        AWAITING_ANDROID,
        AWAITING_USER_APPROVAL,
        APPROVAL_UI_UNAVAILABLE,
        INSTALLED_BY_ANDROID,
        ANDROID_REJECTED
    }

    enum class Event { USER_APPROVAL_REQUIRED, APPROVAL_PRESENTATION_FAILED, INSTALLED, REJECTED }

    fun next(current: State, event: Event): State? = when (current) {
        State.AWAITING_ANDROID -> when (event) {
            Event.USER_APPROVAL_REQUIRED -> State.AWAITING_USER_APPROVAL
            Event.INSTALLED -> State.INSTALLED_BY_ANDROID
            Event.REJECTED -> State.ANDROID_REJECTED
            Event.APPROVAL_PRESENTATION_FAILED -> null
        }
        State.AWAITING_USER_APPROVAL -> when (event) {
            Event.INSTALLED -> State.INSTALLED_BY_ANDROID
            Event.REJECTED -> State.ANDROID_REJECTED
            Event.APPROVAL_PRESENTATION_FAILED -> State.APPROVAL_UI_UNAVAILABLE
            Event.USER_APPROVAL_REQUIRED -> null // Do not pop a second system dialog.
        }
        State.APPROVAL_UI_UNAVAILABLE -> when (event) {
            Event.USER_APPROVAL_REQUIRED -> State.AWAITING_USER_APPROVAL
            Event.INSTALLED -> State.INSTALLED_BY_ANDROID
            Event.REJECTED -> State.ANDROID_REJECTED
            Event.APPROVAL_PRESENTATION_FAILED -> null
        }
        State.INSTALLED_BY_ANDROID, State.ANDROID_REJECTED -> null
    }
}
