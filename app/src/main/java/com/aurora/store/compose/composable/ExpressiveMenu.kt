/*
 * SPDX-FileCopyrightText: 2026 Aurora OSS
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

@file:OptIn(androidx.compose.material3.ExperimentalMaterial3ExpressiveApi::class)

package com.aurora.store.compose.composable

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.background
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.DropdownMenuGroup
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.DropdownMenuPopup
import androidx.compose.material3.ExperimentalMaterial3ExpressiveApi
import androidx.compose.material3.Icon
import androidx.compose.material3.MenuDefaults
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.toggleableState
import androidx.compose.ui.state.ToggleableState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.painter.Painter
import androidx.compose.ui.unit.dp

/** A popup container for Material 3 Expressive menu groups. */
@Composable
fun ExpressiveMenuPopup(
    expanded: Boolean,
    onDismissRequest: () -> Unit,
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit
) {
    DropdownMenuPopup(
        expanded = expanded,
        onDismissRequest = onDismissRequest,
        modifier = modifier
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(MenuDefaults.GroupSpacing)) {
            content()
        }
    }
}

/** A visually distinct group within an expressive menu popup. */
@Composable
fun ExpressiveMenuGroup(
    index: Int,
    count: Int,
    content: @Composable ColumnScope.() -> Unit
) {
    DropdownMenuGroup(
        shapes = MenuDefaults.groupShape(index, count),
        content = content
    )
}

/** A standard expressive menu action with the shape for its position in a group. */
@Composable
fun ExpressiveMenuItem(
    index: Int,
    count: Int,
    text: @Composable () -> Unit,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    leadingIcon: (@Composable () -> Unit)? = null,
    enabled: Boolean = true
) {
    DropdownMenuItem(
        onClick = onClick,
        text = text,
        shape = menuItemShape(index, count),
        modifier = modifier,
        leadingIcon = leadingIcon,
        enabled = enabled
    )
}

/** API23-compatible selection using the existing expressive group shape and selected icon. */
@Composable
fun ExpressiveSelectableMenuItem(
    index: Int,
    count: Int,
    selected: Boolean,
    text: @Composable () -> Unit,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    selectedLeadingIcon: (@Composable () -> Unit)? = null,
    enabled: Boolean = true
) {
    val itemShape = menuItemShape(index, count)
    DropdownMenuItem(
        onClick = onClick,
        text = text,
        shape = itemShape,
        modifier = modifier
            .background(
                color = if (selected) MaterialTheme.colorScheme.secondaryContainer else Color.Transparent,
                shape = itemShape
            )
            .semantics { this.selected = selected },
        leadingIcon = if (selected) selectedLeadingIcon else null,
        enabled = enabled
    )
}

/** API23-compatible toggle with explicit checked semantics and a checked visual state. */
@Composable
fun ExpressiveCheckableMenuItem(
    index: Int,
    count: Int,
    checked: Boolean,
    text: @Composable () -> Unit,
    onCheckedChange: (Boolean) -> Unit,
    modifier: Modifier = Modifier,
    leadingIcon: (@Composable () -> Unit)? = null,
    checkedLeadingIcon: (@Composable () -> Unit)? = null,
    enabled: Boolean = true
) {
    val itemShape = menuItemShape(index, count)
    DropdownMenuItem(
        onClick = { onCheckedChange(!checked) },
        text = text,
        shape = itemShape,
        modifier = modifier
            .background(
                color = if (checked) MaterialTheme.colorScheme.secondaryContainer else Color.Transparent,
                shape = itemShape
            )
            .semantics { toggleableState = ToggleableState(checked) },
        leadingIcon = if (checked) checkedLeadingIcon ?: leadingIcon else leadingIcon,
        trailingIcon = { Checkbox(checked = checked, onCheckedChange = null) },
        enabled = enabled
    )
}

@Composable
private fun menuItemShape(index: Int, count: Int): Shape = when {
    count <= 1 -> MenuDefaults.standaloneItemShape
    index == 0 -> MenuDefaults.leadingItemShape
    index == count - 1 -> MenuDefaults.trailingItemShape
    else -> MenuDefaults.middleItemShape
}

/** A menu leading icon with the standard Material menu icon size. */
@Composable
fun ExpressiveMenuIcon(
    painter: Painter,
    contentDescription: String? = null
) {
    Icon(
        painter = painter,
        contentDescription = contentDescription,
        modifier = Modifier.size(24.dp)
    )
}
