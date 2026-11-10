/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package com.aurora.store.data.artifact

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import android.text.Editable
import android.text.TextWatcher
import android.view.View
import android.widget.AdapterView
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
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import java.util.concurrent.Executors
import java.io.InputStream

/** Visible entry from Settings; import verification never mutates Play's Room/worker state. */
class ArtifactImportActivity : AppCompatActivity() {
    private val worker = Executors.newSingleThreadExecutor()
    // Each picked document owns one cancellation/stream lease. Stale jobs cannot
    // reuse a cancellation token or publish a replacement receipt.
    private val closeWorker = Executors.newSingleThreadExecutor()
    private fun newCancellation() = ArtifactCopyCancellation { stream ->
        // Closing a remote SAF provider stream might block. Never do it on the UI thread.
        runCatching { closeWorker.execute { runCatching { stream.close() } } }
            .onFailure { worker.execute { runCatching { stream.close() } } }
    }
    private var cancellation = newCancellation()
    // UI-thread request serial: a cancelled/older worker may never publish its result.
    private var requestSerial = 0L
    private var active: ArtifactApkVerifier.VerifiedImport? = null
    private lateinit var status: TextView
    private lateinit var review: TextView
    private lateinit var lastReceipt: TextView
    private lateinit var consentHint: TextView
    private lateinit var sources: Spinner
    private lateinit var sourceUrl: EditText
    private lateinit var apkPureEnabled: CheckBox
    private lateinit var alternativeConsent: CheckBox
    private lateinit var fossAcknowledgement: CheckBox
    private lateinit var providerStatus: TextView
    private var lastProviderIndex = -1
    private lateinit var installConsent: CheckBox
    private lateinit var unknownPublisherConsent: CheckBox
    private lateinit var downgradeConsent: CheckBox
    private lateinit var installButton: Button
    private lateinit var selectButton: Button
    // A source claim is valid only for the exact successful browser launch and selection.
    // Never persist raw URLs or use a browser navigation as publisher authentication.
    private var lastBrowserLaunch: ArtifactHandoffClaimPolicy.BrowserLaunch? = null
    private val providers = ArtifactProviderDiscovery.Provider.entries
    private val options = providers.map { it.title }
    private val picker = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) handlePickedFile(uri)
        else {
            lastBrowserLaunch = null
            clearReview("Document picker closed. No file selected or installed.")
        }
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
            onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
                override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                    // Never carry a verified selection or browser claim across sources.
                    if (lastProviderIndex != -1 && lastProviderIndex != position &&
                        ::status.isInitialized
                    ) {
                        invalidateCurrentImport("Provider changed. Select a new file for verification.")
                    }
                    lastProviderIndex = position
                    lastBrowserLaunch = null
                    if (::alternativeConsent.isInitialized) alternativeConsent.isChecked = false
                    if (::fossAcknowledgement.isInitialized) fossAcknowledgement.isChecked = false
                    refreshProviderPresentation()
                }

                override fun onNothingSelected(parent: AdapterView<*>?) {
                    lastBrowserLaunch = null
                }
            }
        }
        column.addView(sources)
        sourceUrl = EditText(this).apply {
            hint = "HTTPS page to open in browser (optional)"
            inputType = android.text.InputType.TYPE_CLASS_TEXT or
                android.text.InputType.TYPE_TEXT_VARIATION_URI
            setSingleLine(true)
            addTextChangedListener(object : TextWatcher {
                override fun afterTextChanged(s: Editable?) {
                    if (lastBrowserLaunch?.exactInput != s?.toString()) lastBrowserLaunch = null
                    // Editing a source after verification cannot silently relabel an import.
                    if (active != null) invalidateCurrentImport("Source changed. Verify the selected file again.")
                }

                override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
                override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
            })
        }
        column.addView(sourceUrl)
        apkPureEnabled = CheckBox(this).apply {
            text = "Enable APKPure browser handoff (off by default)"
            isChecked = getSharedPreferences("artifact_source_preferences", MODE_PRIVATE)
                .getBoolean("apkpure_opt_in", false)
            setOnCheckedChangeListener { _, checked ->
                if (!checked) lastBrowserLaunch = null
                getSharedPreferences("artifact_source_preferences", MODE_PRIVATE).edit()
                    .putBoolean("apkpure_opt_in", checked).apply()
            }
        }
        column.addView(apkPureEnabled)
        alternativeConsent = CheckBox(this).apply {
            text = "I explicitly choose this alternative provider for this browser visit (no automatic fallback)"
            isChecked = false
            setOnCheckedChangeListener { _, checked ->
                if (!checked) lastBrowserLaunch = null
            }
        }
        column.addView(alternativeConsent)
        fossAcknowledgement = CheckBox(this).apply {
            text = "This is a FOSS app; I understand F-Droid signatures may differ from installed copies"
            isChecked = false
            setOnCheckedChangeListener { _, checked ->
                if (!checked) lastBrowserLaunch = null
            }
        }
        column.addView(fossAcknowledgement)
        providerStatus = label("Provider not selected. Availability is UNKNOWN until checked at the provider.")
        column.addView(Button(this).apply {
            text = "Open chosen provider (manual browser handoff)"
            setOnClickListener { openSourceInBrowser() }
        })
        label(
            "Browser links are manual handoffs, not direct downloads or trusted publisher " +
                "proof. F-Droid may use a different signing key. APKPure is off by default. " +
                "No paid/protected downloads, scraping, or automatic Play fallback. " +
                "After downloading, use the system file picker below."
        )
        refreshProviderPresentation()
        selectButton = Button(this).apply {
            text = "Choose downloaded file"
            setOnClickListener {
                invalidateCurrentImport("Choose a file in Android's document picker.", preserveBrowserClaim = true)
                // The OS SAF picker owns document permission; do not use raw filesystem paths.
                runCatching { picker.launch(arrayOf("*/*")) }.onFailure {
                    lastBrowserLaunch = null
                    clearReview("Android document picker is unavailable. No file installed.")
                }
            }
        }
        column.addView(selectButton)
        column.addView(Button(this).apply {
            text = "Cancel current import"
            setOnClickListener {
                invalidateCurrentImport(
                    "Import cancelled. An already committed Android session may continue."
                )
            }
        })
        status = label("Select an APK or bundle to verify before installing.")
        label("Verification receipt")
        review = label("No verified files. Selecting a website does not verify a publisher.")
        label("Android installation outcome")
        lastReceipt = label(ArtifactInstallSession.lastResult(this))
        column.addView(Button(this).apply {
            text = "Refresh Android install outcome"
            setOnClickListener { lastReceipt.text = ArtifactInstallSession.lastResult(this@ArtifactImportActivity) }
        })
        label("Installation permissions for this verified file")
        installConsent = CheckBox(this).apply {
            text = "I approve installation of the verified package and version shown above"
            visibility = View.GONE
            setOnCheckedChangeListener { _, _ -> updateConsentState() }
        }
        unknownPublisherConsent = CheckBox(this).apply {
            text = "I accept installing a signed APK whose publisher identity is not independently verified"
            visibility = View.GONE
            setOnCheckedChangeListener { _, _ -> updateConsentState() }
        }
        downgradeConsent = CheckBox(this).apply {
            text = "I separately approve requesting the older version. Android may refuse; no uninstall or data wipe"
            visibility = View.GONE
            setOnCheckedChangeListener { _, _ -> updateConsentState() }
        }
        column.addView(installConsent)
        column.addView(unknownPublisherConsent)
        column.addView(downgradeConsent)
        consentHint = label("Consent options appear after verification.")
        installButton = Button(this).apply {
            text = "Request Android installation"
            isEnabled = false
            setOnClickListener { beginInstall() }
        }
        column.addView(installButton)
        // targetSdk 37 enforces edge-to-edge; keep review/consent outside system bars.
        val scroll = ScrollView(this).apply {
            isFillViewport = true
            addView(column, ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ))
        }
        ViewCompat.setOnApplyWindowInsetsListener(scroll) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            insets
        }
        setContentView(scroll)
        ViewCompat.requestApplyInsets(scroll)
    }

    private fun showStatus(message: String) {
        status.text = message
    }

    /** Invalidate selection, verification, consent and owned cache before another picker. */
    private fun invalidateCurrentImport(message: String, preserveBrowserClaim: Boolean = false) {
        requestSerial += 1
        cancellation.cancel()
        active?.discard()
        active = null
        if (!preserveBrowserClaim) lastBrowserLaunch = null
        if (::selectButton.isInitialized) selectButton.isEnabled = true
        clearReview(message)
    }

    private fun selectedProvider(): ArtifactProviderDiscovery.Provider =
        providers[sources.selectedItemPosition.coerceIn(0, providers.lastIndex)]

    private fun selectedSource(): ArtifactSource =
        selectedProvider().source ?: ArtifactSource.LOCAL_DOCUMENT

    private fun refreshProviderPresentation() {
        if (!::providerStatus.isInitialized || !::sourceUrl.isInitialized) return
        val choice = selectedProvider()
        providerStatus.text = choice.explanation + "\n" + ArtifactProviderDiscovery.status(choice)
        sourceUrl.hint = when (choice) {
            ArtifactProviderDiscovery.Provider.GOOGLE_PLAY -> "Exact Android package ID (e.g. org.example.app)"
            ArtifactProviderDiscovery.Provider.LOCAL_DOCUMENT -> "No provider URL needed for local documents"
            else -> "Allowed HTTPS provider page (not a direct APK URL)"
        }
        alternativeConsent.visibility = if (choice.isAlternative) View.VISIBLE else View.GONE
        fossAcknowledgement.visibility = if (choice == ArtifactProviderDiscovery.Provider.FDROID) {
            View.VISIBLE
        } else View.GONE
        apkPureEnabled.visibility = if (choice == ArtifactProviderDiscovery.Provider.APKPURE) {
            View.VISIBLE
        } else View.GONE
    }

    private fun verifiedFacts(verified: ArtifactApkVerifier.VerifiedImport):
        ArtifactReviewPresentation.VerifiedFacts {
        val receipt = ArtifactIndependentEvidence.fromVerifiedImport(verified)
        return ArtifactReviewPresentation.VerifiedFacts(
            receipt.provenance,
            receipt.attemptGeneration,
            receipt.apkSha256,
            receipt.packageName,
            receipt.versionCode,
            receipt.apkSha256.size,
            verified.totalApkBytes,
            receipt.selectedFileSha256,
            receipt.signingCertificateSha256,
            receipt.installedVersion,
            receipt.signerMatchesInstalled,
            verified.trustTier
        )
    }

    private fun clearReview(message: String) {
        installButton.isEnabled = false
        if (::installConsent.isInitialized) {
            installConsent.isChecked = false
            unknownPublisherConsent.isChecked = false
            downgradeConsent.isChecked = false
            installConsent.visibility = View.GONE
            unknownPublisherConsent.visibility = View.GONE
            downgradeConsent.visibility = View.GONE
        }
        if (::review.isInitialized) review.text = "No verified files."
        if (::consentHint.isInitialized) consentHint.text = "Consent options appear after verification."
        if (::status.isInitialized) showStatus(message)
    }

    private fun configureConsent(verified: ArtifactApkVerifier.VerifiedImport) {
        val facts = verifiedFacts(verified)
        installConsent.isChecked = false
        unknownPublisherConsent.isChecked = false
        downgradeConsent.isChecked = false
        installConsent.visibility = View.VISIBLE
        unknownPublisherConsent.visibility = if (
            ArtifactReviewPresentation.consentNeedsUnknownPublisher(facts)
        ) View.VISIBLE else View.GONE
        downgradeConsent.visibility = if (
            ArtifactReviewPresentation.consentNeedsDowngrade(facts)
        ) View.VISIBLE else View.GONE
        updateConsentState()
    }

    private fun decisionFor(verified: ArtifactApkVerifier.VerifiedImport) =
        ArtifactImportDecision.blockers(
            ArtifactImportDecision.Review(
                verified.attempt.packageName,
                verified.attempt.versionCode,
                signerVerified = true,
                installedSignerMatches = verified.signerMatchesInstalled,
                installedVersion = verified.installedVersion,
                trustedPublisherAnchor = false, // C04 never establishes this anchor.
                userApprovedInstall = installConsent.isChecked,
                userAcceptedUnknownPublisher = unknownPublisherConsent.isChecked,
                userApprovedDowngrade = downgradeConsent.isChecked
            )
        )

    private fun updateConsentState() {
        // Consent cannot be carried from another file/import attempt.
        if (!::installButton.isInitialized || !::consentHint.isInitialized) return
        val verified = active
        if (verified == null) {
            installButton.isEnabled = false
            consentHint.text = "Verify a file before accepting installation."
            return
        }
        val blockers = decisionFor(verified)
        installButton.isEnabled = blockers.isEmpty()
        consentHint.text = ArtifactReviewPresentation.blockerDescription(blockers)
    }

    private fun openSourceInBrowser() {
        // Only an explicit user click may open the system browser; NEVER auto-fallback.
        lastBrowserLaunch = null
        val provider = selectedProvider()
        val enteredUrl = sourceUrl.text.toString()
        val plan = ArtifactProviderDiscovery.decide(
            provider, enteredUrl,
            alternativeConsent.isChecked, apkPureEnabled.isChecked,
            fossAcknowledgement.isChecked
        )
        when (plan) {
            is ArtifactProviderDiscovery.Outcome.Refused -> showStatus(plan.explanation)
            is ArtifactProviderDiscovery.Outcome.Ready -> {
                if (plan.route == ArtifactProviderDiscovery.Route.NATIVE_FILE_PICKER) {
                    selectButton.performClick()
                    return
                }
                val page = plan.url ?: return showStatus("No verified provider URL; nothing opened.")
                runCatching {
                    startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(page.toASCIIString())).apply {
                        addCategory(Intent.CATEGORY_BROWSABLE)
                    })
                    if (plan.route == ArtifactProviderDiscovery.Route.EXTERNAL_PROVIDER_PAGE) {
                        // This is only a time-bounded navigation claim; no file's actual
                        // origin, developer identity or signing key has been established.
                        val handoff = ArtifactSourceHandoff.parse(
                            enteredUrl, selectedSource(), apkPureEnabled.isChecked
                        ) ?: error("Provider page no longer passes HTTPS validation")
                        lastBrowserLaunch = ArtifactHandoffClaimPolicy.afterSuccessfulLaunch(enteredUrl, handoff)
                    }
                    showStatus(if (plan.route == ArtifactProviderDiscovery.Route.PLAY_LISTING) {
                        "Google Play listing opened. Version availability and Play delivery are not established here."
                    } else {
                        "Provider page opened in browser. Download manually, then use Android's picker; publisher is unverified."
                    })
                }.onFailure {
                    lastBrowserLaunch = null
                    showStatus("Provider browser is unavailable. No file was downloaded or installed.")
                }
            }
        }
    }

    /** SAF metadata is untrusted and its provider may stall; never query on the UI thread. */
    private fun selectedFilename(uri: Uri): String {
        val cursor = contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
        val name = cursor?.use { result ->
            if (result.moveToFirst()) result.getString(0) else null
        }
        return ArtifactPickerPolicy.safeDocumentName(name) ?: "unknown"
    }

    private fun handlePickedFile(uri: Uri) {
        if (!ArtifactPickerPolicy.acceptsPickerScheme(uri.scheme)) {
            invalidateCurrentImport("Refused a non-SAF document URI; nothing installed.")
            return
        }
        // Capture browser claim on the UI thread at the exact picker result. URI
        // metadata lookup happens later on the worker, not via a UI-thread provider query.
        val source = selectedSource()
        val enteredUrl = sourceUrl.text.toString()
        val optIn = apkPureEnabled.isChecked
        val alternativeApproved = alternativeConsent.isChecked
        val pickedAtMonotonicMs = System.nanoTime() / 1_000_000L
        val launched = lastBrowserLaunch
        lastBrowserLaunch = null
        requestSerial += 1
        val serial = requestSerial
        cancellation.cancel()
        val ticket = newCancellation()
        cancellation = ticket
        active?.discard()
        active = null
        selectButton.isEnabled = false
        clearReview("Reading document metadata and copying privately. Nothing installed.")
        review.text = "Verification in progress — no APK approved yet."
        worker.execute {
            var staged: ArtifactPrivateStager.Staged? = null
            try {
                if (ticket.isCancelled()) throw IllegalStateException("Import cancelled")
                val name = selectedFilename(uri)
                if (ticket.isCancelled()) throw IllegalStateException("Import cancelled")
                val provenance = ArtifactHandoffClaimPolicy.selection(
                    selected = source, enteredUrl = enteredUrl, apkPureOptIn = optIn,
                    launched = launched,
                    untrustedFilename = ArtifactPickerPolicy.safeDisplayLabel(name),
                    alternativeConsent = alternativeApproved,
                    nowMonotonicMs = pickedAtMonotonicMs
                )
                staged = ArtifactPrivateStager.stage(this, uri, name, ticket) {
                    ticket.isCancelled()
                }
                val result = ArtifactApkVerifier.verify(this, staged, provenance) {
                    ticket.isCancelled()
                }
                if (ticket.isCancelled()) {
                    result.discard()
                    throw IllegalStateException("Import cancelled")
                }
                runOnUiThread {
                    if (serial != requestSerial || ticket.isCancelled() || isFinishing || isDestroyed) {
                        result.discard()
                    } else {
                        active?.discard()
                        active = result
                        selectButton.isEnabled = true
                        review.text = ArtifactReviewPresentation.verification(verifiedFacts(result))
                        configureConsent(result)
                        showStatus("APK signature checks passed. Review the receipt and required approvals; NOT installed.")
                    }
                }
            } catch (error: Exception) {
                staged?.discard()
                runOnUiThread {
                    if (serial == requestSerial && !isDestroyed && !ticket.isCancelled()) {
                        selectButton.isEnabled = true
                        clearReview("Import refused: ${error.message ?: "unreadable or unsupported file"}. No install consent remains.")
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
        val decision = decisionFor(receipt)
        if (decision.isNotEmpty()) {
            showStatus("Installation blocked: ${ArtifactReviewPresentation.blockerDescription(decision)}")
            return
        }
        installButton.isEnabled = false
        selectButton.isEnabled = false
        val ticket = cancellation
        val serial = requestSerial
        showStatus("Sending verified APK bytes to Android PackageInstaller")
        worker.execute {
            runCatching {
                ArtifactInstallSession.install(this, receipt, approved, unknown, downgrade) { ticket.isCancelled() }
            }.onSuccess { session ->
                runOnUiThread {
                    if (serial == requestSerial) {
                        active = null
                        if (!isDestroyed) {
                            selectButton.isEnabled = true
                            clearReview("Android install request submitted; final outcome NOT confirmed (session $session).")
                            lastReceipt.text = ArtifactInstallSession.lastResult(this@ArtifactImportActivity)
                        }
                    }
                }
            }.onFailure { error ->
                receipt.discard()
                runOnUiThread {
                    if (serial == requestSerial) {
                        active = null
                        if (!isDestroyed) {
                            selectButton.isEnabled = true
                            clearReview("Install refused before Android confirmation: ${error.message ?: "system error"}")
                        }
                    }
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        if (::lastReceipt.isInitialized) {
            lastReceipt.text = ArtifactInstallSession.lastResult(this)
        }
    }

    override fun onDestroy() {
        lastBrowserLaunch = null
        requestSerial += 1
        cancellation.cancel()
        active?.discard()
        active = null
        worker.shutdownNow()
        // Let already submitted provider-close work complete; do not strand its stream.
        closeWorker.shutdown()
        super.onDestroy()
    }
}
