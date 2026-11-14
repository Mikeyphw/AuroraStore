/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.aurora.store.data.artifact

import com.aurora.store.data.installer.verification.ApkVerificationException

/** Pure structural veto after every APK's bytes and manifest have been authenticated.
 * A dependency declaration cannot make a missing split available, and is NOT an
 * authenticated bundletool device selector. The verifier repeats this at commit time.
 */
internal object ArtifactFeatureDependencyPolicy {
    private val splitPattern = Regex("[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}")

    fun check(splitIds: List<String?>, requiredSplit: List<String?>) {
        if (splitIds.size != requiredSplit.size || splitIds.count { it == null } != 1 ||
            splitIds.filterNotNull().distinct().size != splitIds.size - 1
        ) throw ApkVerificationException("Feature dependency identity is ambiguous")
        val present = splitIds.filterNotNull().toSet()
        val edges = mutableMapOf<String, String>()
        for ((index, id) in splitIds.withIndex()) {
            val dep = requiredSplit[index] ?: continue
            if (id == null || id.startsWith("config.") || ".config." in id ||
                !splitPattern.matches(dep) || dep == id || dep !in present ||
                dep.startsWith("config.") || ".config." in dep
            ) throw ApkVerificationException("Required feature split is unavailable or invalid")
            edges[id] = dep
        }
        for (name in edges.keys) {
            val visited = mutableSetOf<String>()
            var node: String? = name
            while (node != null) {
                if (!visited.add(node)) {
                    throw ApkVerificationException("Cyclic feature split dependencies")
                }
                node = edges[node]
            }
        }
    }
}
