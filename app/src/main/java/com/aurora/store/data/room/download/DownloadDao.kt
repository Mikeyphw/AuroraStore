/*
 * SPDX-FileCopyrightText: 2026 Aurora OSS
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

package com.aurora.store.data.room.download

import androidx.paging.PagingSource
import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.RawQuery
import androidx.sqlite.db.SupportSQLiteQuery
import com.aurora.gplayapi.model.AppFile
import com.aurora.store.data.model.DownloadStatus
import kotlinx.coroutines.flow.Flow

@Dao
interface DownloadDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(download: Download)

    @Query("UPDATE download SET downloadStatus=:downloadStatus WHERE packageName=:packageName")
    suspend fun updateStatus(packageName: String, downloadStatus: DownloadStatus)

    /** Cancel only the selected version before asking WorkManager to stop its worker. */
    @Query(
        """
        UPDATE download SET downloadStatus = 'CANCELLED'
        WHERE packageName = :packageName AND versionCode = :versionCode
          AND downloadedAt = :attemptKey
          AND downloadStatus IN ('QUEUED', 'PURCHASING', 'DOWNLOADING', 'VERIFYING', 'COMPLETED')
        """
    )
    suspend fun cancelActiveDownload(packageName: String, versionCode: Long, attemptKey: Long): Int

    /** A new retry gets a new persisted generation even when the version is unchanged. */
    @Query(
        """
        UPDATE download SET downloadStatus = 'QUEUED',
            downloadedAt = CASE WHEN downloadedAt >= :now THEN downloadedAt + 1 ELSE :now END,
            progress = 0, speed = 0, timeRemaining = 0
        WHERE packageName = :packageName AND versionCode = :versionCode
          AND downloadedAt = :previousAttempt
          AND downloadStatus IN ('FAILED', 'CANCELLED', 'UNAVAILABLE',
                                 'COMPLETED', 'INSTALLED', 'AWAITING_INSTALL')
        """
    )
    suspend fun retryWithNewAttempt(
        packageName: String,
        versionCode: Long,
        previousAttempt: Long,
        now: Long
    ): Int

    /** A stale worker may not resurrect a cancelled, replaced or installing download. */
    @Query(
        """
        UPDATE download SET downloadStatus = :downloadStatus
        WHERE packageName = :packageName AND versionCode = :versionCode
          AND downloadedAt = :attemptKey
          AND downloadStatus IN ('QUEUED', 'PURCHASING', 'DOWNLOADING', 'VERIFYING', 'COMPLETED')
        """
    )
    suspend fun updateWorkerStatus(
        packageName: String,
        versionCode: Long,
        attemptKey: Long,
        downloadStatus: DownloadStatus
    ): Int

    /** Free a serialized download slot only when no live worker owns it. */
    @Query(
        """
        UPDATE download SET downloadStatus = 'FAILED'
        WHERE packageName = :packageName AND versionCode = :versionCode
          AND downloadedAt = :attemptKey
          AND downloadStatus IN ('PURCHASING', 'DOWNLOADING', 'VERIFYING')
        """
    )
    suspend fun failOrphanedDownload(packageName: String, versionCode: Long, attemptKey: Long): Int

    @Query(
        "DELETE FROM download WHERE packageName = :packageName " +
            "AND versionCode = :versionCode AND downloadedAt = :attemptKey"
    )
    suspend fun deleteVersion(packageName: String, versionCode: Long, attemptKey: Long): Int

    @Query("UPDATE download SET fileList=:fileList WHERE packageName=:packageName")
    suspend fun updateFiles(packageName: String, fileList: List<AppFile>)

    @Query(
        """
        UPDATE download SET fileList = :fileList
        WHERE packageName = :packageName AND versionCode = :versionCode
          AND downloadedAt = :attemptKey
          AND downloadStatus IN ('QUEUED', 'PURCHASING', 'DOWNLOADING', 'VERIFYING')
        """
    )
    suspend fun updateWorkerFiles(
        packageName: String,
        versionCode: Long,
        attemptKey: Long,
        fileList: List<AppFile>
    ): Int

    @Query("UPDATE download SET sharedLibs=:sharedLibs WHERE packageName=:packageName")
    suspend fun updateSharedLibs(packageName: String, sharedLibs: List<SharedLib>)

    @Query(
        """
        UPDATE download SET sharedLibs = :sharedLibs
        WHERE packageName = :packageName AND versionCode = :versionCode
          AND downloadedAt = :attemptKey
          AND downloadStatus IN ('QUEUED', 'PURCHASING', 'DOWNLOADING', 'VERIFYING')
        """
    )
    suspend fun updateWorkerSharedLibs(
        packageName: String,
        versionCode: Long,
        attemptKey: Long,
        sharedLibs: List<SharedLib>
    ): Int

    @Query(
        """
        UPDATE download
        SET progress=:progress, speed=:speed, timeRemaining=:timeRemaining
        WHERE packageName=:packageName
        """
    )
    suspend fun updateProgress(packageName: String, progress: Int, speed: Long, timeRemaining: Long)

    @Query(
        """
        UPDATE download SET progress = :progress, speed = :speed, timeRemaining = :timeRemaining
        WHERE packageName = :packageName AND versionCode = :versionCode
          AND downloadedAt = :attemptKey
          AND downloadStatus IN ('QUEUED', 'PURCHASING', 'DOWNLOADING', 'VERIFYING', 'COMPLETED')
        """
    )
    suspend fun updateWorkerProgress(
        packageName: String,
        versionCode: Long,
        attemptKey: Long,
        progress: Int,
        speed: Long,
        timeRemaining: Long
    ): Int

    @Query("SELECT * FROM download")
    fun downloads(): Flow<List<Download>>

    @Query(
        """
        SELECT * FROM download
        WHERE downloadStatus = 'AWAITING_INSTALL'
        ORDER BY downloadedAt DESC
        """
    )
    fun pendingInstalls(): Flow<List<Download>>

    @RawQuery(observedEntities = [Download::class])
    fun pagedDownloads(query: SupportSQLiteQuery): PagingSource<Int, Download>

    @Query("SELECT * FROM download WHERE packageName = :packageName")
    suspend fun getDownload(packageName: String): Download

    @Query("DELETE FROM download WHERE packageName = :packageName")
    suspend fun delete(packageName: String)

    @Query("DELETE FROM download")
    suspend fun deleteAll()
}
