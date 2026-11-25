/*
 * SPDX-FileCopyrightText: 2026 Aurora OSS
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

package com.aurora.store.data.providers

import androidx.test.ext.junit.runners.AndroidJUnit4
import com.google.common.truth.Truth.assertThat
import dagger.hilt.android.testing.HiltAndroidRule
import dagger.hilt.android.testing.HiltAndroidTest
import java.util.Locale
import java.util.Properties
import javax.inject.Inject
import org.junit.After
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@HiltAndroidTest
@RunWith(AndroidJUnit4::class)
class SpoofProviderTest {

    @get:Rule
    var hiltAndroidRule = HiltAndroidRule(this)

    @Inject
    lateinit var spoofProvider: SpoofProvider

    @Before
    fun setup() {
        hiltAndroidRule.inject()
    }

    @After
    fun tearDown() {
        spoofProvider.setLanguages(emptyList())
        spoofProvider.removeSpoofDeviceProperties()
    }

    @Test
    fun testSpoofingDeviceLocale() {
        spoofProvider.setLanguages(listOf(Locale.JAPAN, Locale.GERMANY, Locale.JAPAN))
        assertThat(spoofProvider.languages).containsExactly(Locale.JAPAN, Locale.GERMANY).inOrder()
        assertThat(spoofProvider.additionalLocales).containsExactly(Locale.GERMANY)
        assertThat(spoofProvider.locale == Locale.JAPAN).isTrue()
    }

    @Test
    fun testSpoofingDeviceLocaleDropsRegionUnknownToPlay() {
        spoofProvider.setLanguages(listOf(Locale.forLanguageTag("es-419")))
        assertThat(spoofProvider.locale).isEqualTo(Locale.forLanguageTag("es"))
    }

    @Test
    fun testSpoofingDeviceProperties() {
        assertThat(spoofProvider.isDeviceSpoofEnabled).isFalse()

        val properties = Properties().apply {
            setProperty("UserReadableName", "Test")
        }
        spoofProvider.setSpoofDeviceProperties(properties)
        assertThat(spoofProvider.isDeviceSpoofEnabled).isTrue()
        assertThat(spoofProvider.deviceProperties == properties).isTrue()
    }
}
