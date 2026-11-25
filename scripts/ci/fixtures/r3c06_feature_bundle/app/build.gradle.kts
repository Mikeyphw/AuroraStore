// SPDX-License-Identifier: GPL-3.0-or-later
plugins { id("com.android.application") }
android {
    namespace = "com.aurora.r3c06.featurefixture"
    compileSdk { version = release(36) }
    defaultConfig {
        applicationId = "com.aurora.r3c06.featurefixture"
        minSdk { version = release(23) }
        targetSdk { version = release(36) }
        versionCode = 1
        versionName = "1.0-fixture-only"
    }
    dynamicFeatures.add(":featureproof")
}
