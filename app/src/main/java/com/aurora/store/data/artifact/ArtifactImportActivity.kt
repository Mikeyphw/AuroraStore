/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import android.view.ViewGroup
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Spinner
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/** Visible entry from Settings; import verification never mutates Play's Room/worker state. */
class ArtifactImportActivity : AppCompatActivity() {
    private val worker = Executors.newSingleThreadExecutor()
    private var cancelled = AtomicBoolean(false)
    private var active: ArtifactApkVerifier.VerifiedImport? = null
    private lateinit var status: TextView
    private lateinit var review: TextView
    private lateinit var sources: Spinner
    private lateinit var sourceUrl: EditText
    private lateinit var apkPureEnabled: CheckBox
    private lateinit var installConsent: CheckBox
    private lateinit var unknownPublisherConsent: CheckBox
    private lateinit var downgradeConsent: CheckBox
    private lateinit var installButton: Button
    private lateinit var selectButton: Button
    private var provenanceHost: String? = null
    private val options = listOf(
        "Local document", "Official developer website (claimed)",
        "GitHub Releases (claimed)", "APKMirror web handoff",
        "F-Droid (conditional)", "APKPure (requires opt-in)"
    )
    private val kinds = listOf(
        ArtifactSource.LOCAL_DOCUMENT,
        ArtifactSource.DEVELOPER_WEBSITE,
        ArtifactSource.GITHUB_RELEASE,
        ArtifactSource.APKMIRROR_BROWSER_HANDOFF,
        ArtifactSource.FDROID_REPOSITORY,
        ArtifactSource.APKPURE_OPT_IN
    )
    private val picker = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) handlePickedFile(uri)
        else showStatus("No file selected; nothing installed")
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = "Import APK or bundle"
        val density = resources.displayMetrics.density
        val margin = (16 * density).toInt()
        val column = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(margin, margin, margin, margin)
        }
        fun label(text: String): TextView = TextView(this).apply {
            this.text = text
            textSize = 14f
            setPadding(0, margin / 2, 0, margin / 2)
            column.addView(this)
        }
        label(
            "Import APK/APKS/APKM/XAPK files. Bytes are copied to private storage, " +
                "verified, then installed by Android only after your approval."
        )
        sources = Spinner(this).apply {
            adapter = ArrayAdapter(this@ArtifactImportActivity, android.R.layout.simple_spinner_dropdown_item, options)
        }
        column.addView(sources)
        sourceUrl = EditText(this).apply {
            hint = "HTTPS page to open in browser (optional)"
            inputType = android.text.InputType.TYPE_CLASS_TEXT or
                android.text.InputType.TYPE_TEXT_VARIATION_URI
            setSingleLine(true)
        }
        column.addView(sourceUrl)
        apkPureEnabled = CheckBox(this).apply {
            text = "Enable APKPure browser handoff (off by default)"
            isChecked = getSharedPreferences("artifact_source_preferences", MODE_PRIVATE)
                .getBoolean("apkpure_opt_in", false)
            setOnCheckedChangeListener { _, checked ->
                getSharedPreferences("artifact_source_preferences", MODE_PRIVATE).edit()
                    .putBoolean("apkpure_opt_in", checked).apply()
            }
        }
        column.addView(apkPureEnabled)
        column.addView(Button(this).apply {
            text = "Open selected source in browser"
            setOnClickListener { openSourceInBrowser() }
        })
        label(
            "Browser links are manual handoffs, not direct downloads or trusted publisher " +
                "proof. F-Droid may use a different signing key. APKPure is off by default. " +
                "After downloading, use the system file picker below."
        )
        selectButton = Button(this).apply {
            text = "Choose downloaded file"
            setOnClickListener {
                cancelled.set(true)
                active?.discard()
                active = null
                installButton.isEnabled = false
                picker.launch(arrayOf("*/*"))
            }
        }
        column.addView(selectButton)
        column.addView(Button(this).apply {
            text = "Cancel current import"
            setOnClickListener {
                cancelled.set(true)
                active?.discard()
                active = null
                installButton.isEnabled = false
                showStatus("Import cancelled; no installation requested")
            }
        })
        status = label("Select a local file to begin; ${ArtifactInstallSession.lastResult(this)}")
        review = label("No staged or verified APK yet. Unknown publisher identity will be shown explicitly.")
        installConsent = CheckBox(this).apply {
            text = "I explicitly request installation of this verified APK set"
        }
        unknownPublisherConsent = CheckBox(this).apply {
            text = "I understand that a valid APK signer does not prove the developer's identity"
        }
        downgradeConsent = CheckBox(this).apply {
            text = "Allow requesting an older version (Android may refuse; do not uninstall or erase data)"
        }
        column.addView(installConsent)
        column.addView(unknownPublisherConsent)
        column.addView(downgradeConsent)
        installButton = Button(this).apply {
            text = "Request Android installation"
            isEnabled = false
            setOnClickListener { beginInstall() }
        }
        column.addView(installButton)
        setContentView(ScrollView(this).apply {
            isFillViewport = true
            addView(column, ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ))
        })
    }

    private fun showStatus(message: String) {
        status.text = message
    }

    private fun selectedSource(): ArtifactSource = kinds[sources.selectedItemPosition]

    private fun openSourceInBrowser() {
        val source = selectedSource()
        val handoff = ArtifactSourceHandoff.parse(
            sourceUrl.text.toString(), source, apkPureEnabled.isChecked
        )
        if (handoff == null) {
            showStatus("Enter an allowed HTTPS provider page. APKPure requires explicit opt-in.")
            return
        }
        provenanceHost = handoff.host
        runCatching {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(handoff.uri.toASCIIString())).apply {
                addCategory(Intent.CATEGORY_BROWSABLE)
            })
        }.onFailure { showStatus("No browser can open the provider page") }
    }

    private fun selectedFilename(uri: Uri): String {
        val cursor = contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
        val name = cursor?.use { result ->
            if (result.moveToFirst()) result.getString(0) else null
        }
        return name?.takeIf { it.length <= 240 } ?: "unknown"
    }

    private fun handlePickedFile(uri: Uri) {
        val name = runCatching { selectedFilename(uri) }.getOrDefault("unknown")
        val source = selectedSource()
        val host = provenanceHost?.takeIf { source != ArtifactSource.LOCAL_DOCUMENT }
        provenanceHost = null
        val sourceLabel = host ?: name.substringAfterLast('/').take(150)
        val provenance = ArtifactProvenance(source, sourceLabel)
        cancelled = AtomicBoolean(false)
        val thisCancel = cancelled
        active?.discard()
        active = null
        installButton.isEnabled = false
        selectButton.isEnabled = false
        installConsent.isChecked = false
        unknownPublisherConsent.isChecked = false
        downgradeConsent.isChecked = false
        showStatus("Copying selected file privately; do not close this screen")
        review.text = "Not yet verified"
        worker.execute {
            var staged: ArtifactPrivateStager.Staged? = null
            try {
                staged = ArtifactPrivateStager.stage(this, uri, name) { thisCancel.get() }
                val result = ArtifactApkVerifier.verify(this, staged, provenance) { thisCancel.get() }
                if (thisCancel.get()) throw IllegalStateException("Cancelled")
                runOnUiThread {
                    if (thisCancel.get() || isFinishing || isDestroyed) {
                        result.discard()
                    } else {
                        active?.discard()
                        active = result
                        installButton.isEnabled = true
                        selectButton.isEnabled = true
                        showStatus("APK signatures verified; installation not yet requested")
                        review.text = buildString {
                            append("Source claim: ${result.attempt.provenance.source}\n")
                            append("Package: ${result.attempt.packageName}\n")
                            append("Version: ${result.attempt.versionCode}\n")
                            append("APK files: ${result.files.size} · bytes: ${result.totalApkBytes}\n")
                            append("Source file SHA-256: ${result.staged.originalSha256}\n")
                            append("Signer SHA-256: ${result.signerSha256.sorted().joinToString()}\n")
                            append("Publisher trust: ${result.trustTier}\n")
                            append("Installed version: ${result.installedVersion ?: "none"}\n")
                            append("Signature continuity: ${result.signerMatchesInstalled ?: "not applicable"}\n")
                            append("ABI/split checks are conservative; Android remains final authority.")
                        }
                    }
                }
            } catch (error: Exception) {
                staged?.discard()
                runOnUiThread {
                    if (!isDestroyed) {
                        selectButton.isEnabled = true
                        showStatus("Import refused: ${error.message ?: "unsupported file"}")
                    }
                }
            }
        }
    }

    private fun beginInstall() {
        val receipt = active ?: return
        val approved = installConsent.isChecked
        val unknown = unknownPublisherConsent.isChecked
        val downgrade = downgradeConsent.isChecked
        val decision = ArtifactImportDecision.blockers(
            ArtifactImportDecision.Review(
                receipt.attempt.packageName,
                receipt.attempt.versionCode,
                signerVerified = true,
                installedSignerMatches = receipt.signerMatchesInstalled,
                installedVersion = receipt.installedVersion,
                trustedPublisherAnchor = false,
                userApprovedInstall = approved,
                userAcceptedUnknownPublisher = unknown,
                userApprovedDowngrade = downgrade
            )
        )
        if (decision.isNotEmpty()) {
            showStatus("Installation blocked: ${decision.joinToString()}")
            return
        }
        installButton.isEnabled = false
        selectButton.isEnabled = false
        val thisCancel = cancelled
        showStatus("Sending verified APK bytes to Android PackageInstaller")
        worker.execute {
            runCatching {
                ArtifactInstallSession.install(this, receipt, unknown, downgrade) { thisCancel.get() }
            }.onSuccess { session ->
                runOnUiThread {
                    active = null
                    if (!isDestroyed) {
                        selectButton.isEnabled = true
                        showStatus("Android session $session created; system approval may be required")
                    }
                }
            }.onFailure { error ->
                receipt.discard()
                runOnUiThread {
                    active = null
                    if (!isDestroyed) {
                        selectButton.isEnabled = true
                        showStatus("Install refused: ${error.message ?: "system error"}")
                    }
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        if (::status.isInitialized) {
            val last = ArtifactInstallSession.lastResult(this)
            if (last.contains("INSTALLED_BY_ANDROID") || last.contains("ANDROID_REJECTED")) {
                showStatus(last)
            }
        }
    }

    override fun onDestroy() {
        cancelled.set(true)
        active?.discard()
        active = null
        worker.shutdownNow()
        super.onDestroy()
    }
}
