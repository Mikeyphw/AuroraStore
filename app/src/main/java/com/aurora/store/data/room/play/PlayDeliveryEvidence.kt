/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.room.play

import androidx.room.Entity
import androidx.room.PrimaryKey
import com.aurora.store.data.model.PlayExactVersionOutcomePolicy

/** One current evidence snapshot per package. Never stores Play URLs, tokens or e-mail. */
@Entity(tableName = "play_delivery_evidence")
data class PlayDeliveryEvidence(
    @PrimaryKey val packageName: String,
    val versionCode: Long,
    val attemptGeneration: Long,
    val accountBinding: String,
    val variant: String,
    val state: String,
    val verifiedApkVersion: Long?,
    val unavailableVersion: Long?,
    val resolvedFileCount: Int
) {
    internal fun key(): PlayExactVersionOutcomePolicy.RequestKey =
        PlayExactVersionOutcomePolicy.RequestKey(
            packageName = packageName,
            versionCode = versionCode,
            attemptGeneration = attemptGeneration,
            accountBinding = accountBinding,
            variant = variant
        )

    internal fun snapshot(): PlayExactVersionOutcomePolicy.Snapshot =
        PlayExactVersionOutcomePolicy.Snapshot(
            key = key(),
            state = PlayExactVersionOutcomePolicy.State.valueOf(state),
            verifiedApkVersion = verifiedApkVersion,
            unavailableVersion = unavailableVersion,
            resolvedFileCount = resolvedFileCount
        )

    companion object {
        internal fun from(snapshot: PlayExactVersionOutcomePolicy.Snapshot): PlayDeliveryEvidence =
            PlayDeliveryEvidence(
                packageName = snapshot.key.packageName,
                versionCode = snapshot.key.versionCode,
                attemptGeneration = snapshot.key.attemptGeneration,
                accountBinding = requireNotNull(snapshot.key.accountBinding),
                variant = requireNotNull(snapshot.key.variant),
                state = snapshot.state.name,
                verifiedApkVersion = snapshot.verifiedApkVersion,
                unavailableVersion = snapshot.unavailableVersion,
                resolvedFileCount = snapshot.resolvedFileCount
            )
    }
}
