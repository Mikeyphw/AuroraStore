/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.room.play

import android.content.Context
import android.os.Build
import android.util.Base64
import androidx.room.withTransaction
import com.aurora.store.data.installer.verification.R3bVerifiedProof
import com.aurora.store.data.model.DownloadStatus
import com.aurora.store.data.model.PlayAccountFingerprint
import com.aurora.store.data.model.PlayExactVersionOutcomePolicy
import com.aurora.store.data.room.AuroraDatabase
import com.aurora.store.data.room.download.DownloadDao
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject

/**
 * C02's separate transaction boundary; C01's Play-only URL/failed-result DAO remains unchanged.
 * No generic API for callers to assert VERIFIED_SET or EXPLICIT_EXACT_VERSION_DELIVERY_REFUSAL.
 */
internal class PlayVerifiedEvidenceStore @Inject constructor(
    private val database: AuroraDatabase,
    private val evidenceDao: PlayDeliveryEvidenceDao,
    private val downloadDao: DownloadDao,
    @ApplicationContext private val context: Context
) {
    private val policy = PlayExactVersionOutcomePolicy

    /** Receiving all declared files is weaker than verifying their APK signatures. */
    suspend fun bytesReceived(
        key: PlayExactVersionOutcomePolicy.RequestKey,
        selectedAccount: String,
        resolvedFileCount: Int
    ): Boolean = advance(key, selectedAccount, resolvedFileCount, proof = null)

    /** Requires an unforgeable in-process receipt from R3B's production verifier. */
    suspend fun verified(
        key: PlayExactVersionOutcomePolicy.RequestKey,
        selectedAccount: String,
        proof: R3bVerifiedProof
    ): Boolean {
        if (proof.packageName != key.packageName) return false
        if (proof.versionCode != key.versionCode) return false
        if (proof.attemptGeneration != key.attemptGeneration) return false
        return advance(key, selectedAccount, proof.resolvedFileCount, proof)
    }

    /** Strictly verified BASE APK minSdk; a missing manifest value is UNKNOWN, never a refusal. */
    suspend fun verifiedSdkIncompatible(
        key: PlayExactVersionOutcomePolicy.RequestKey,
        selectedAccount: String,
        proof: R3bVerifiedProof
    ): Boolean {
        val minSdk = proof.verifiedMinSdk ?: return false
        if (minSdk <= Build.VERSION.SDK_INT) return false
        if (proof.packageName != key.packageName) return false
        if (proof.versionCode != key.versionCode) return false
        if (proof.attemptGeneration != key.attemptGeneration) return false
        return advance(key, selectedAccount, proof.resolvedFileCount, proof, sdkRefusal = true)
    }

    private suspend fun advance(
        key: PlayExactVersionOutcomePolicy.RequestKey,
        selectedAccount: String,
        resolvedFileCount: Int,
        proof: R3bVerifiedProof?,
        sdkRefusal: Boolean = false
    ): Boolean = database.withTransaction {
        if (key.source != PlayExactVersionOutcomePolicy.Source.GOOGLE_PLAY) {
            return@withTransaction false
        }
        if (resolvedFileCount <= 0) return@withTransaction false
        if (evidenceDao.currentProcessingAttempt(
                key.packageName,
                key.versionCode,
                key.attemptGeneration
            ) != 1
        ) {
            return@withTransaction false
        }
        if (evidenceDao.selectedAccountIdentity(key.packageName) != selectedAccount) {
            return@withTransaction false
        }
        val current = downloadDao.getDownload(key.packageName)
        if (current.status != DownloadStatus.VERIFYING) return@withTransaction false
        if (current.versionCode != key.versionCode) return@withTransaction false
        if (current.downloadedAt != key.attemptGeneration) return@withTransaction false
        if (current.fileList.size != resolvedFileCount) return@withTransaction false
        val existing = evidenceDao.latest(key.packageName) ?: return@withTransaction false
        if (existing.key() != key) return@withTransaction false
        val event = when {
            sdkRefusal -> PlayExactVersionOutcomePolicy.Event.VerifiedManifestSdkIncompatible(
                key,
                key.versionCode
            )
            proof != null -> PlayExactVersionOutcomePolicy.Event.R3bVerifiedSet(
                key,
                proof.versionCode,
                resolvedFileCount
            )
            else -> PlayExactVersionOutcomePolicy.Event.BytesDownloaded(
                key,
                key.versionCode,
                resolvedFileCount
            )
        }
        val next = policy.reduce(key, existing.snapshot(), event) ?: return@withTransaction false
        evidenceDao.put(PlayDeliveryEvidence.from(next))
        true
    }

    /**
     * Only an already-accepted installer callback can record installation failure.
     * The receiver first performs DownloadDao.transitionInstallAttempt() with the exact
     * package/version/generation; this transaction rechecks that identity and account.
     */
    suspend fun installerFailed(packageName: String, versionCode: Long, attempt: Long): Boolean =
        database.withTransaction {
            val current = runCatching { downloadDao.getDownload(packageName) }.getOrNull()
                ?: return@withTransaction false
            if (current.versionCode != versionCode) return@withTransaction false
            if (current.downloadedAt != attempt) return@withTransaction false
            val allowedStatus = current.status in setOf(
                DownloadStatus.FAILED,
                DownloadStatus.AWAITING_INSTALL
            )
            if (!allowedStatus) return@withTransaction false
            val evidence = evidenceDao.latest(packageName) ?: return@withTransaction false
            val key = evidence.key()
            if (key.versionCode != versionCode) return@withTransaction false
            if (key.attemptGeneration != attempt) return@withTransaction false
            if (evidence.verifiedApkVersion != versionCode) return@withTransaction false
            if (key.source != PlayExactVersionOutcomePolicy.Source.GOOGLE_PLAY) {
                return@withTransaction false
            }
            // Aurora account ids can be e-mail addresses. Never persist a raw identifier.
            val secret = context.getSharedPreferences(
                "play_evidence_identity",
                Context.MODE_PRIVATE
            ).getString("key", null) ?: return@withTransaction false
            val secretBytes = runCatching { Base64.decode(secret, Base64.NO_WRAP) }.getOrNull()
                ?: return@withTransaction false
            val selected = evidenceDao.selectedAccountIdentity(packageName)
            val fingerprint = runCatching {
                PlayAccountFingerprint.hmacHex(secretBytes, selected)
            }.getOrNull() ?: return@withTransaction false
            if (key.accountBinding != fingerprint) return@withTransaction false
            val next = policy.reduce(
                key,
                evidence.snapshot(),
                PlayExactVersionOutcomePolicy.Event.InstallFailed(key, versionCode)
            ) ?: return@withTransaction false
            evidenceDao.put(PlayDeliveryEvidence.from(next))
            true
        }
}
