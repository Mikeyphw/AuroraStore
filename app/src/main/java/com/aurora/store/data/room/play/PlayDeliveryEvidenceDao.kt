/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.room.play

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import com.aurora.store.data.model.PlayExactVersionOutcomePolicy

@Dao
interface PlayDeliveryEvidenceDao {
    /** Account selection is the stable opaque Room account id, not a credential or token. */
    @Query(
        """
        SELECT COALESCE(
            (SELECT accountId FROM app_account_binding WHERE packageName = :packageName),
            (SELECT id FROM account WHERE isDefault = 1 LIMIT 1),
            'unbound'
        )
        """
    )
    suspend fun selectedAccountIdentity(packageName: String): String

    @Query(
        """
        SELECT COUNT(*) FROM download
        WHERE packageName = :packageName AND versionCode = :versionCode
          AND downloadedAt = :attemptGeneration
          AND downloadStatus IN ('QUEUED', 'PURCHASING', 'DOWNLOADING', 'VERIFYING')
        """
    )
    suspend fun currentProcessingAttempt(
        packageName: String,
        versionCode: Long,
        attemptGeneration: Long
    ): Int

    @Query("SELECT * FROM play_delivery_evidence WHERE packageName = :packageName")
    suspend fun latest(packageName: String): PlayDeliveryEvidence?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun put(evidence: PlayDeliveryEvidence)

    /**
     * Database-serialized compare-and-set against the *live* download and selected account.
     * A different account/offer for the same generation is never silently rebound.
     */
    @Transaction
    suspend fun accept(
        packageName: String,
        versionCode: Long,
        attemptGeneration: Long,
        accountBinding: String,
        selectedAccount: String,
        variant: String,
        outcome: String,
        fileCount: Int = 0
    ): Boolean {
        if (currentProcessingAttempt(packageName, versionCode, attemptGeneration) != 1 ||
            selectedAccountIdentity(packageName) != selectedAccount
        ) {
            return false
        }
        val key = PlayExactVersionOutcomePolicy.RequestKey(
            packageName = packageName,
            versionCode = versionCode,
            attemptGeneration = attemptGeneration,
            accountBinding = accountBinding,
            variant = variant
        )
        // selectedAccount is transient and never persisted as an e-mail/account id.
        val event = if (outcome == "URLS_RESOLVED") {
            PlayExactVersionOutcomePolicy.Event.UrlsResolved(key, versionCode, fileCount)
        } else {
            val failure = runCatching {
                PlayExactVersionOutcomePolicy.Failure.valueOf(outcome)
            }.getOrNull() ?: return false
            PlayExactVersionOutcomePolicy.Event.Failed(key, failure)
        }
        val stored = latest(packageName)
        if (stored != null && stored.attemptGeneration == attemptGeneration &&
            stored.key() != key
        ) {
            return false
        }
        val prior = if (stored?.key() == key) {
            runCatching { stored.snapshot() }.getOrNull() ?: return false
        } else {
            null
        }
        val next = PlayExactVersionOutcomePolicy.reduce(key, prior, event) ?: return false
        put(PlayDeliveryEvidence.from(next))
        return true
    }
}
