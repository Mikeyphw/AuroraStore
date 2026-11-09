/*
 * SPDX-FileCopyrightText: 2026 Aurora OSS
 * SPDX-FileCopyrightText: 2025 The Calyx Institute
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

package com.aurora.store.compose.ui.details

import android.os.Build
import androidx.activity.ComponentActivity
import androidx.activity.compose.LocalActivity
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.requiredSize
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ContainedLoadingIndicator
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.adaptive.WindowAdaptiveInfo
import androidx.compose.material3.adaptive.currentWindowAdaptiveInfoV2
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.res.dimensionResource
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.tooling.preview.PreviewParameter
import androidx.compose.ui.tooling.preview.PreviewWrapper
import androidx.compose.ui.unit.dp
import androidx.core.text.isDigitsOnly
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.aurora.extensions.adaptiveNavigationIcon
import com.aurora.extensions.isWindowCompact
import com.aurora.gplayapi.model.App
import com.aurora.store.R
import com.aurora.store.compose.composable.Info
import com.aurora.store.compose.composable.TopAppBar
import com.aurora.store.compose.preview.AppPreviewProvider
import com.aurora.store.compose.preview.ThemePreviewProvider
import com.aurora.store.compose.ui.sheets.VersionPickerSheet
import com.aurora.store.data.model.AppState
import com.aurora.store.data.model.HistoricalAvailabilityPolicy
import com.aurora.store.data.model.HistoricalAvailabilityPolicy.Decision
import com.aurora.store.data.model.HistoricalVersionPolicy
import com.aurora.store.data.model.Report
import com.aurora.store.util.PackageUtil
import com.aurora.store.viewmodel.details.AppDetailsViewModel
import kotlinx.coroutines.launch

@Composable
fun ManualDownloadScreen(
    packageName: String,
    onRequestInstall: (requestedApp: App) -> Unit,
    viewModel: AppDetailsViewModel = hiltViewModel(key = packageName),
    windowAdaptiveInfo: WindowAdaptiveInfo = currentWindowAdaptiveInfoV2()
) {
    val context = LocalContext.current
    val app by viewModel.app.collectAsStateWithLifecycle()
    val state by viewModel.state.collectAsStateWithLifecycle()
    val reports by viewModel.exodusReports.collectAsStateWithLifecycle()
    val lookupInProgress by viewModel.versionLookupInProgress.collectAsStateWithLifecycle()
    val topAppBarTitle = if (windowAdaptiveInfo.isWindowCompact) {
        app?.displayName ?: stringResource(R.string.title_manual_download)
    } else {
        stringResource(R.string.title_manual_download)
    }

    ScreenContent(
        state = state,
        topAppBarTitle = topAppBarTitle,
        currentVersionCode = app?.versionCode ?: 0L,
        metadataReady = app != null,
        installedVersionCode = PackageUtil.getInstalledVersionCode(context, packageName),
        installedVersionProvider = { PackageUtil.getInstalledVersionCode(context, packageName) },
        reports = reports,
        lookupInProgress = lookupInProgress,
        onLookup = viewModel::lookupVersions,
        onRequestInstall = { versionCode ->
            app?.let { listedApp ->
                // Historical files and static-library versions must not inherit metadata
                // belonging to the current Play listing.
                val requestedApp = if (versionCode == listedApp.versionCode) {
                    listedApp
                } else {
                    listedApp.copy(
                        versionCode = versionCode,
                        fileList = emptyList(),
                        dependencies = listedApp.dependencies.copy(dependentLibraries = emptyList())
                    )
                }
                onRequestInstall(requestedApp)
            }
        }
    )
}

@Composable
private fun ScreenContent(
    state: AppState = AppState.Unavailable,
    topAppBarTitle: String? = null,
    currentVersionCode: Long = 0L,
    metadataReady: Boolean = true,
    installedVersionCode: Long = 0L,
    installedVersionProvider: () -> Long = { installedVersionCode },
    reports: List<Report> = emptyList(),
    lookupInProgress: Boolean = false,
    onLookup: () -> Unit = {},
    onRequestInstall: (versionCode: Long) -> Unit = {},
    windowAdaptiveInfo: WindowAdaptiveInfo = currentWindowAdaptiveInfoV2()
) {
    val activity = LocalActivity.current as? ComponentActivity
    val coroutineScope = rememberCoroutineScope()
    val snackBarHostState = remember { SnackbarHostState() }
    val errorMessage = stringResource(R.string.manual_download_version_error)

    val focusManager = LocalFocusManager.current
    var versionCode by remember(currentVersionCode) {
        val initText = currentVersionCode.takeIf { it > 0L }?.toString().orEmpty()
        mutableStateOf(TextFieldValue(text = initText, selection = TextRange(initText.length)))
    }

    var showVersionPicker by remember { mutableStateOf(false) }
    var pendingDowngrade by remember { mutableStateOf<Pair<Long, Long>?>(null) }
    val selectedVersion = HistoricalVersionPolicy.parseVersionCode(versionCode.text)
    val selectionAssessment = selectedVersion?.let { requested ->
        // Neither Exodus reports nor latest-release metadata prove this historical APK exists.
        // Exact-version Play delivery and R3B verification occur only after a user request.
        val inHistory = reports.any { report ->
            HistoricalVersionPolicy.parseVersionCode(report.versionCode) == requested
        }
        HistoricalAvailabilityPolicy.assess(
            HistoricalAvailabilityPolicy.Evidence(
                requestedVersion = requested,
                currentListingVersion = currentVersionCode,
                installedVersion = installedVersionCode,
                historicalReportVersion = requested.takeIf { inHistory },
                deviceSdk = Build.VERSION.SDK_INT
            )
        )
    }
    val mayRequestSelection = when (selectionAssessment?.decision) {
        HistoricalAvailabilityPolicy.Decision.MAY_REQUEST_EXACT_DELIVERY,
        HistoricalAvailabilityPolicy.Decision.DOWNGRADE_CONSENT_REQUIRED -> true
        else -> false
    }

    pendingDowngrade?.let { (requested, installedAtConfirmation) ->
        AlertDialog(
            onDismissRequest = { pendingDowngrade = null },
            title = { Text(stringResource(R.string.r3_downgrade_title)) },
            text = {
                Text(
                    stringResource(
                        R.string.r3_downgrade_warning,
                        installedAtConfirmation,
                        requested
                    )
                )
            },
            confirmButton = {
                Button(
                    enabled = metadataReady && !state.inProgress(),
                    onClick = {
                        pendingDowngrade = null
                        val installedNow = installedVersionProvider()
                        val assessment = HistoricalAvailabilityPolicy.assess(
                            HistoricalAvailabilityPolicy.Evidence(
                                requestedVersion = requested,
                                currentListingVersion = currentVersionCode,
                                installedVersion = installedNow,
                                deviceSdk = Build.VERSION.SDK_INT,
                                downgradeConsent = true
                            )
                        )
                        if (HistoricalVersionPolicy.mayConfirmDowngrade(
                                requested,
                                installedAtConfirmation,
                                installedNow,
                                versionCode.text
                            ) && assessment.mayAttemptExactDelivery
                        ) {
                            onRequestInstall(requested)
                            focusManager.clearFocus()
                        }
                    }
                ) {
                    Text(stringResource(R.string.r3_downgrade_try))
                }
            },
            dismissButton = {
                FilledTonalButton(onClick = { pendingDowngrade = null }) {
                    Text(stringResource(R.string.action_close))
                }
            }
        )
    }

    if (showVersionPicker) {
        VersionPickerSheet(
            reports = reports,
            loading = lookupInProgress,
            installedVersionCode = installedVersionCode,
            currentListingVersionCode = currentVersionCode,
            onSelect = { report ->
                HistoricalVersionPolicy.canonicalVersionCode(report.versionCode)?.let { code ->
                    versionCode = TextFieldValue(text = code, selection = TextRange(code.length))
                    showVersionPicker = false
                }
            },
            onDismiss = { showVersionPicker = false }
        )
    }

    Scaffold(
        modifier = Modifier.imePadding(),
        topBar = {
            TopAppBar(
                title = topAppBarTitle,
                navigationIcon = windowAdaptiveInfo.adaptiveNavigationIcon
            )
        },
        snackbarHost = { SnackbarHost(hostState = snackBarHostState) }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .padding(paddingValues)
                .fillMaxSize()
                .padding(dimensionResource(R.dimen.spacing_medium)),
            verticalArrangement = Arrangement.SpaceBetween
        ) {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(
                    dimensionResource(R.dimen.spacing_medium)
                )
            ) {
                Info(
                    painter = painterResource(R.drawable.ic_download_manager),
                    title = AnnotatedString(text = stringResource(R.string.manual_download_hint))
                )
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    enabled = metadataReady && !state.inProgress(),
                    value = versionCode,
                    onValueChange = {
                        val code = it.text.filterNot(Char::isWhitespace)
                        if (code.isDigitsOnly()) {
                            versionCode = if (code == it.text) {
                                it
                            } else {
                                TextFieldValue(text = code, selection = TextRange(code.length))
                            }
                        } else {
                            coroutineScope.launch { snackBarHostState.showSnackbar(errorMessage) }
                        }
                    },
                    shape = RoundedCornerShape(10.dp),
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    keyboardActions = KeyboardActions(onDone = { focusManager.clearFocus() }),
                    trailingIcon = {
                        if (state.inProgress()) {
                            ContainedLoadingIndicator(
                                modifier = Modifier
                                    .requiredSize(dimensionResource(R.dimen.icon_size_default))
                            )
                        }
                    }
                )

                if (versionCode.text.isNotEmpty() && selectedVersion == null) {
                    Text(
                        text = stringResource(R.string.r3_invalid_version_code),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error
                    )
                }
                if (selectionAssessment?.isHistorical == true) {
                    Text(
                        text = stringResource(R.string.r3c_selected_version_unverified),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }

                Button(
                    modifier = Modifier.fillMaxWidth(),
                    enabled = metadataReady && !state.inProgress(),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.secondaryContainer,
                        contentColor = MaterialTheme.colorScheme.onSecondaryContainer
                    ),
                    onClick = {
                        // Dismiss the keyboard so the sheet opens over a settled layout, then
                        // load versions (a no-op fetch when they are already cached).
                        focusManager.clearFocus()
                        showVersionPicker = true
                        onLookup()
                    }
                ) {
                    Text(
                        text = stringResource(R.string.manual_download_lookup),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(
                    dimensionResource(R.dimen.spacing_medium)
                )
            ) {
                FilledTonalButton(
                    modifier = Modifier.weight(1F),
                    onClick = { activity?.onBackPressedDispatcher?.onBackPressed() }
                ) {
                    Text(
                        text = stringResource(R.string.action_close),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }

                Button(
                    modifier = Modifier.weight(1F),
                    enabled = metadataReady && !state.inProgress() && mayRequestSelection,
                    onClick = {
                        selectedVersion?.let { code ->
                            val installedNow = installedVersionProvider()
                            val live = HistoricalAvailabilityPolicy.assess(
                                HistoricalAvailabilityPolicy.Evidence(
                                    requestedVersion = code,
                                    currentListingVersion = currentVersionCode,
                                    installedVersion = installedNow,
                                    deviceSdk = Build.VERSION.SDK_INT
                                )
                            )
                            val isDowngradeNow = HistoricalVersionPolicy.isDowngrade(
                                code,
                                installedNow
                            )
                            val needsConsent = live.decision == Decision.DOWNGRADE_CONSENT_REQUIRED
                            if (isDowngradeNow && needsConsent) {
                                pendingDowngrade = code to installedNow
                            } else if (live.mayAttemptExactDelivery) {
                                onRequestInstall(code)
                                focusManager.clearFocus()
                            }
                        }
                    }
                ) {
                    Text(
                        text = stringResource(R.string.action_install),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }
        }
    }
}

@PreviewWrapper(ThemePreviewProvider::class)
@Preview
@Composable
private fun ManualDownloadScreenPreview(@PreviewParameter(AppPreviewProvider::class) app: App) {
    ScreenContent(
        topAppBarTitle = app.displayName,
        currentVersionCode = app.versionCode,
        reports = listOf(
            Report(version = "8.5.1", versionCode = "85100"),
            Report(version = "8.4.0", versionCode = "84000"),
            Report(version = "8.3.2", versionCode = "83200")
        )
    )
}
