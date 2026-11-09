/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.room.play

import android.content.Context
import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.aurora.store.data.room.AuroraDatabase
import com.aurora.store.data.room.MigrationHelper
import com.aurora.store.data.room.account.AccountConverter
import com.aurora.store.data.room.download.DownloadConverter
import com.google.common.truth.Truth.assertThat
import kotlinx.serialization.json.Json
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Real Room upgrade of a populated schema-v15 on-device SQLite database.
 * The DDL and identity hash are taken from the committed, Room-generated 15.json.
 * This tests on-device migration; it does not certify a generated v16 schema file.
 */
@RunWith(AndroidJUnit4::class)
class RoomV15ToV16MigrationDeviceTest {
    private val context: Context
        get() = InstrumentationRegistry.getInstrumentation().targetContext

    @Test
    fun populatedV15SurvivesRealRoomMigrationToV16() {
        context.deleteDatabase(DB_NAME)
        try {
            context.openOrCreateDatabase(DB_NAME, Context.MODE_PRIVATE, null).use { legacy ->
                V15_TABLES.forEach { legacy.execSQL(it) }
                legacy.execSQL(
                    "CREATE INDEX IF NOT EXISTS `index_app_account_binding_accountId` " +
                        "ON `app_account_binding` (`accountId`)"
                )
                legacy.execSQL(
                    "CREATE TABLE IF NOT EXISTS room_master_table " +
                        "(id INTEGER PRIMARY KEY,identity_hash TEXT)"
                )
                legacy.execSQL(
                    "INSERT OR REPLACE INTO room_master_table (id,identity_hash) " +
                        "VALUES(42, '$V15_IDENTITY_HASH')"
                )
                legacy.execSQL(
                    "INSERT INTO `download` VALUES " +
                        "('com.aurora.migration.fixture', 737, 0, 0, 'v15 persisted', '', " +
                        "8, 0, 'FAILED', 0, 0, 0, 1, 0, '[]', '[]', 23, 9001, 0)"
                )
                legacy.execSQL(
                    "INSERT INTO `account` " +
                        "(`id`, `type`, `email`, `tokenType`, `authViaMicroG`, " +
                        "`isDefault`, `addedAt`) VALUES " +
                        "('v15-account', 'ANONYMOUS', '', 'NONE', 0, 1, 1234)"
                )
                legacy.execSQL(
                    "INSERT INTO `app_account_binding` VALUES " +
                        "('com.aurora.migration.fixture', 'v15-account')"
                )
                legacy.version = 15
                assertThat(legacy.version).isEqualTo(15)
            }
            val migrated = Room.databaseBuilder(context, AuroraDatabase::class.java, DB_NAME)
                .addMigrations(MigrationHelper.MIGRATION_15_16)
                .addTypeConverter(DownloadConverter(Json { ignoreUnknownKeys = true }))
                .addTypeConverter(AccountConverter())
                .build()
            try {
                val db = migrated.openHelper.writableDatabase
                assertThat(db.version).isEqualTo(16)
                db.query(
                    "SELECT `versionCode`, `downloadedAt`, `displayName` FROM " +
                        "`download` WHERE `packageName`='com.aurora.migration.fixture'"
                ).use { row ->
                    assertThat(row.moveToFirst()).isTrue()
                    assertThat(row.getLong(0)).isEqualTo(737L)
                    assertThat(row.getLong(1)).isEqualTo(9001L)
                    assertThat(row.getString(2)).isEqualTo("v15 persisted")
                    assertThat(row.moveToNext()).isFalse()
                }
                db.query("SELECT `id`, `addedAt` FROM `account`").use { row ->
                    assertThat(row.moveToFirst()).isTrue()
                    assertThat(row.getString(0)).isEqualTo("v15-account")
                    assertThat(row.getLong(1)).isEqualTo(1234L)
                }
                db.query("SELECT `accountId` FROM `app_account_binding`").use { row ->
                    assertThat(row.moveToFirst()).isTrue()
                    assertThat(row.getString(0)).isEqualTo("v15-account")
                }
                db.query("SELECT COUNT(*) FROM `play_delivery_evidence`").use { row ->
                    assertThat(row.moveToFirst()).isTrue()
                    assertThat(row.getInt(0)).isEqualTo(0)
                }
            } finally {
                migrated.close()
            }
        } finally {
            context.deleteDatabase(DB_NAME)
        }
    }

    companion object {
        private const val DB_NAME = "aurora_r3c03_migration_test.db"
        private const val V15_IDENTITY_HASH = "61507a0aeabcbbd5d6114872e5bd0462"

        // Exact v15 CREATE TABLE definitions. Source CI checks these against 15.json.
        private val V15_TABLES = listOf(
            """
                CREATE TABLE IF NOT EXISTS `download` (`packageName` TEXT NOT NULL,
                `versionCode` INTEGER NOT NULL, `offerType` INTEGER NOT NULL,
                `isInstalled` INTEGER NOT NULL, `displayName` TEXT NOT NULL,
                `iconURL` TEXT NOT NULL, `size` INTEGER NOT NULL, `id` INTEGER NOT NULL,
                `downloadStatus` TEXT NOT NULL, `progress` INTEGER NOT NULL,
                `speed` INTEGER NOT NULL, `timeRemaining` INTEGER NOT NULL,
                `totalFiles` INTEGER NOT NULL, `downloadedFiles` INTEGER NOT NULL,
                `fileList` TEXT NOT NULL, `sharedLibs` TEXT NOT NULL,
                `targetSdk` INTEGER NOT NULL, `downloadedAt` INTEGER NOT NULL,
                `requiresGMS` INTEGER NOT NULL, PRIMARY KEY(`packageName`))
            """.trimIndent(),
            """
                CREATE TABLE IF NOT EXISTS `favourite` (`packageName` TEXT NOT NULL,
                `displayName` TEXT NOT NULL, `iconURL` TEXT NOT NULL,
                `added` INTEGER NOT NULL, `mode` TEXT NOT NULL, PRIMARY KEY(`packageName`))
            """.trimIndent(),
            """
                CREATE TABLE IF NOT EXISTS `update` (`packageName` TEXT NOT NULL,
                `versionCode` INTEGER NOT NULL, `versionName` TEXT NOT NULL,
                `displayName` TEXT NOT NULL, `iconURL` TEXT NOT NULL,
                `changelog` TEXT NOT NULL, `id` INTEGER NOT NULL,
                `developerName` TEXT NOT NULL, `size` INTEGER NOT NULL,
                `updatedOn` TEXT NOT NULL, `hasValidCert` INTEGER NOT NULL,
                `offerType` INTEGER NOT NULL, `fileList` TEXT NOT NULL,
                `sharedLibs` TEXT NOT NULL, `targetSdk` INTEGER NOT NULL,
                `isIncompatible` INTEGER NOT NULL, `downloadSize` INTEGER NOT NULL,
                `newPermissions` TEXT NOT NULL, PRIMARY KEY(`packageName`))
            """.trimIndent(),
            """
                CREATE TABLE IF NOT EXISTS `ignored_update` (`packageName` TEXT NOT NULL,
                `ignoredVersionCode` INTEGER, PRIMARY KEY(`packageName`))
            """.trimIndent(),
            """
                CREATE TABLE IF NOT EXISTS `review` (`packageName` TEXT NOT NULL,
                `accountEmail` TEXT NOT NULL, `title` TEXT NOT NULL, `comment` TEXT NOT NULL,
                `rating` INTEGER NOT NULL, `commentId` TEXT NOT NULL,
                `userName` TEXT NOT NULL, `userPhotoUrl` TEXT NOT NULL,
                `appVersion` TEXT NOT NULL, `timeStamp` INTEGER NOT NULL,
                `synced` INTEGER NOT NULL, PRIMARY KEY(`packageName`, `accountEmail`))
            """.trimIndent(),
            """
                CREATE TABLE IF NOT EXISTS `account` (`id` TEXT NOT NULL,
                `type` TEXT NOT NULL, `email` TEXT NOT NULL, `displayName` TEXT,
                `profilePicUrl` TEXT, `aasToken` TEXT, `authToken` TEXT,
                `tokenType` TEXT NOT NULL, `authViaMicroG` INTEGER NOT NULL,
                `authDataJson` TEXT, `isDefault` INTEGER NOT NULL, `addedAt` INTEGER NOT NULL,
                PRIMARY KEY(`id`))
            """.trimIndent(),
            """
                CREATE TABLE IF NOT EXISTS `app_account_binding` (`packageName` TEXT NOT NULL,
                `accountId` TEXT NOT NULL, PRIMARY KEY(`packageName`),
                FOREIGN KEY(`accountId`) REFERENCES `account`(`id`) ON UPDATE NO ACTION ON DELETE CASCADE )
            """.trimIndent(),
            """
                CREATE TABLE IF NOT EXISTS `exodus_tracker` (`id` INTEGER NOT NULL,
                `name` TEXT NOT NULL, `url` TEXT NOT NULL, `signature` TEXT NOT NULL,
                `date` TEXT NOT NULL, `categories` TEXT NOT NULL, PRIMARY KEY(`id`))
            """.trimIndent(),
            """
                CREATE TABLE IF NOT EXISTS `notification` (`id` TEXT NOT NULL,
                `type` TEXT NOT NULL, `title` TEXT NOT NULL, `body` TEXT NOT NULL,
                `packageName` TEXT, `url` TEXT, `timestamp` INTEGER NOT NULL,
                `isRead` INTEGER NOT NULL, PRIMARY KEY(`id`))
            """.trimIndent()
        )
    }
}
