// SPDX-License-Identifier: GPL-3.0-or-later
plugins { id("com.android.dynamic-feature") }
android {
    namespace = "com.aurora.r3c06.featurefixture.featureproof"
    compileSdk { version = release(36) }
    defaultConfig { minSdk { version = release(23) } }
}
dependencies { implementation(project(":app")) }
