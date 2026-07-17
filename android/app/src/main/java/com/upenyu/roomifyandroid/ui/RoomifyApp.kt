@file:OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)

package com.upenyu.roomifyandroid.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.weight
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RoomifyApp(viewModel: RoomifyViewModel) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var showResetDialog by remember { mutableStateOf(false) }
    var planWidthText by remember { mutableStateOf(state.planWidthM.toString()) }

    LaunchedEffect(state.planWidthM) {
        if (planWidthText.toDoubleOrNull() != state.planWidthM) planWidthText = state.planWidthM.toString()
    }

    val imagePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let(viewModel::analyzeImage) }
    val jsonPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let(viewModel::importJson) }
    val jsonExporter = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/json")) { uri -> uri?.let(viewModel::exportJson) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Dream Home Visualizer", fontWeight = FontWeight.Bold)
                        Text("Kotlin · offline JSON floor plans", style = MaterialTheme.typography.labelSmall)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.96f),
                    titleContentColor = MaterialTheme.colorScheme.onSurface,
                ),
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            InputCard(
                state = state,
                planWidthText = planWidthText,
                onPlanWidthChanged = { value ->
                    planWidthText = value
                    value.toDoubleOrNull()?.let(viewModel::setPlanWidth)
                },
                onChooseImage = { imagePicker.launch(arrayOf("image/png", "image/jpeg", "image/webp")) },
                onImportJson = { jsonPicker.launch(arrayOf("application/json", "text/json", "text/plain")) },
                onExportJson = { jsonExporter.launch("dream-home-scene.json") },
                onLoadSample = viewModel::loadSample,
                onReset = { showResetDialog = true },
            )
            StatusCard(state, viewModel::clearError)

            if (state.scene == null) {
                EmptyProjectCard()
            } else {
                SceneControls(state, viewModel::setRenderMode, viewModel::setShowSourceImage, viewModel::applyStyle)
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(20.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 4.dp),
                ) {
                    FloorPlanCanvas(
                        scene = state.scene!!,
                        sourceBitmap = state.sourceBitmap,
                        showSourceImage = state.showSourceImage,
                        renderMode = state.renderMode,
                        selectedRoomId = state.selectedRoomId,
                        onSelectRoom = viewModel::selectRoom,
                        onMoveSelectedRoom = viewModel::moveSelectedRoom,
                        modifier = Modifier.fillMaxWidth().height(520.dp),
                    )
                }
                SceneSummary(state)
                RoomEditor(state, viewModel::selectRoom, viewModel::renameSelectedRoom, viewModel::addRoom, viewModel::deleteSelectedRoom)
            }

            Text(
                "The JSON geometry is authoritative. The image is only an input and optional reference overlay; every plan and design view is rebuilt from walls, rooms, openings, materials and furniture stored in JSON.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(18.dp))
        }
    }

    if (showResetDialog) {
        AlertDialog(
            onDismissRequest = { showResetDialog = false },
            title = { Text("Clear local project?") },
            text = { Text("This removes the current source image and JSON scene from this device.") },
            confirmButton = {
                TextButton(onClick = {
                    showResetDialog = false
                    viewModel.resetProject()
                }) { Text("Clear") }
            },
            dismissButton = { TextButton(onClick = { showResetDialog = false }) { Text("Cancel") } },
        )
    }
}

@Composable
private fun InputCard(
    state: RoomifyUiState,
    planWidthText: String,
    onPlanWidthChanged: (String) -> Unit,
    onChooseImage: () -> Unit,
    onImportJson: () -> Unit,
    onExportJson: () -> Unit,
    onLoadSample: () -> Unit,
    onReset: () -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(20.dp)) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("1. Capture or restore a plan", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text(
                "Choose a clear top-down floor-plan image. Structural walls are extracted locally and converted into portable JSON. Import JSON when exact verified geometry already exists.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            OutlinedTextField(
                value = planWidthText,
                onValueChange = onPlanWidthChanged,
                enabled = !state.isBusy,
                modifier = Modifier.fillMaxWidth(),
                label = { Text("Known plan width in metres") },
                supportingText = { Text("This calibrates image pixels to real-world dimensions.") },
                singleLine = true,
            )
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(enabled = !state.isBusy, onClick = onChooseImage) { Text("Read image into JSON") }
                OutlinedButton(enabled = !state.isBusy, onClick = onImportJson) { Text("Import JSON") }
                OutlinedButton(enabled = !state.isBusy && state.scene != null, onClick = onExportJson) { Text("Export JSON") }
                OutlinedButton(enabled = !state.isBusy, onClick = onLoadSample) { Text("Load sample") }
                TextButton(enabled = !state.isBusy && (state.scene != null || state.sourceBitmap != null), onClick = onReset) { Text("Reset") }
            }
        }
    }
}

@Composable
private fun StatusCard(state: RoomifyUiState, onDismissError: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = if (state.error == null) MaterialTheme.colorScheme.surfaceVariant else MaterialTheme.colorScheme.errorContainer,
        ),
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    state.error ?: state.status,
                    modifier = Modifier.weight(1f),
                    color = if (state.error == null) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onErrorContainer,
                    style = MaterialTheme.typography.bodyMedium,
                )
                if (state.error != null) TextButton(onClick = onDismissError) { Text("Dismiss") }
            }
            if (state.isBusy) LinearProgressIndicator(Modifier.fillMaxWidth())
            if (state.hasUnsavedChanges) Text("Saving local JSON…", style = MaterialTheme.typography.labelSmall)
        }
    }
}

@Composable
private fun EmptyProjectCard() {
    Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(20.dp)) {
        Column(
            modifier = Modifier.padding(28.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text("No floor plan yet", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Text(
                "Start with a PNG, JPG or WEBP plan, or import a SceneManifest JSON exported by the Windows or Android app.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun SceneControls(
    state: RoomifyUiState,
    onRenderMode: (RenderMode) -> Unit,
    onShowSource: (Boolean) -> Unit,
    onStyle: (String) -> Unit,
) {
    var styleMenu by remember { mutableStateOf(false) }
    val style = StyleCatalog.byId(state.styleId)
    Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(20.dp)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("2. Verify geometry and design", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (state.renderMode == RenderMode.PLAN) Button(onClick = { onRenderMode(RenderMode.PLAN) }) { Text("Plan") }
                else OutlinedButton(onClick = { onRenderMode(RenderMode.PLAN) }) { Text("Plan") }
                if (state.renderMode == RenderMode.DESIGN) Button(onClick = { onRenderMode(RenderMode.DESIGN) }) { Text("3D design") }
                else OutlinedButton(onClick = { onRenderMode(RenderMode.DESIGN) }) { Text("3D design") }
                Box {
                    OutlinedButton(onClick = { styleMenu = true }) { Text(style.label) }
                    DropdownMenu(expanded = styleMenu, onDismissRequest = { styleMenu = false }) {
                        StyleCatalog.styles.forEach { option ->
                            DropdownMenuItem(
                                text = {
                                    Column {
                                        Text(option.label, fontWeight = FontWeight.SemiBold)
                                        Text(option.description, style = MaterialTheme.typography.labelSmall)
                                    }
                                },
                                onClick = {
                                    styleMenu = false
                                    onStyle(option.id)
                                },
                            )
                        }
                    }
                }
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Switch(
                    checked = state.showSourceImage,
                    onCheckedChange = onShowSource,
                    enabled = state.sourceBitmap != null && state.renderMode == RenderMode.PLAN,
                )
                Spacer(Modifier.width(8.dp))
                Text("Show source-image alignment overlay")
            }
            Text(
                if (state.renderMode == RenderMode.PLAN) "Tap a room, then drag it to correct its JSON coordinates."
                else "The design view is generated from JSON geometry and the selected material palette.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun SceneSummary(state: RoomifyUiState) {
    val scene = state.scene ?: return
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("JSON scene summary", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                SummaryMetric("Rooms", scene.rooms.size.toString())
                SummaryMetric("Walls", scene.walls.size.toString())
                SummaryMetric("Openings", scene.openings.size.toString())
                SummaryMetric("Width", "%.2f m".format(scene.widthM))
                SummaryMetric("Depth", "%.2f m".format(scene.depthM))
                SummaryMetric("Confidence", "%.0f%%".format(scene.projectMetadata.structuralConfidence * 100.0))
            }
            if (state.warnings.isNotEmpty()) {
                HorizontalDivider()
                state.warnings.forEach { warning ->
                    Text("• $warning", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

@Composable
private fun SummaryMetric(label: String, value: String) {
    Column(
        modifier = Modifier.background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(12.dp)).padding(horizontal = 13.dp, vertical = 9.dp),
    ) {
        Text(value, fontWeight = FontWeight.Bold)
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun RoomEditor(
    state: RoomifyUiState,
    onSelectRoom: (String?) -> Unit,
    onRename: (String) -> Unit,
    onAdd: () -> Unit,
    onDelete: () -> Unit,
) {
    val scene = state.scene ?: return
    val selected = scene.rooms.firstOrNull { it.id == state.selectedRoomId }
    var name by remember(selected?.id, selected?.name) { mutableStateOf(selected?.name.orEmpty()) }
    Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(20.dp)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("3. Correct room JSON", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                scene.rooms.forEach { room ->
                    if (room.id == selected?.id) Button(onClick = { onSelectRoom(room.id) }) { Text(room.name) }
                    else OutlinedButton(onClick = { onSelectRoom(room.id) }) { Text(room.name) }
                }
            }
            if (selected != null) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("Room name") },
                    supportingText = { Text("${"%.2f".format(selected.areaM2)} m² · centroid ${"%.2f".format(selected.centroid[0])}, ${"%.2f".format(selected.centroid[1])}") },
                    singleLine = true,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(enabled = name.isNotBlank(), onClick = { onRename(name) }) { Text("Save name") }
                    OutlinedButton(onClick = onDelete) { Text("Delete room") }
                }
            }
            OutlinedButton(onClick = onAdd) { Text("Add rectangular room") }
        }
    }
}
