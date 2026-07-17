package com.upenyu.roomifyandroid.ui

import android.app.Application
import android.graphics.Bitmap
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.upenyu.roomifyandroid.analysis.AnalysisOptions
import com.upenyu.roomifyandroid.analysis.FloorPlanAnalyzer
import com.upenyu.roomifyandroid.analysis.OrthogonalFloorPlanAnalyzer
import com.upenyu.roomifyandroid.data.ProjectStore
import com.upenyu.roomifyandroid.data.SceneJsonCodec
import com.upenyu.roomifyandroid.data.SceneJsonRepository
import com.upenyu.roomifyandroid.model.SceneGeometry
import com.upenyu.roomifyandroid.model.SceneManifest
import java.util.UUID
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch


enum class RenderMode { PLAN, DESIGN }

data class RoomifyUiState(
    val scene: SceneManifest? = null,
    val sourceBitmap: Bitmap? = null,
    val selectedRoomId: String? = null,
    val planWidthM: Double = 14.0,
    val styleId: String = "modern",
    val renderMode: RenderMode = RenderMode.PLAN,
    val showSourceImage: Boolean = true,
    val isBusy: Boolean = true,
    val status: String = "Loading local project…",
    val error: String? = null,
    val warnings: List<String> = emptyList(),
    val hasUnsavedChanges: Boolean = false,
)

class RoomifyViewModel(application: Application) : AndroidViewModel(application) {
    private val sceneRepository = SceneJsonRepository(application)
    private val projectStore = ProjectStore(application)
    private val analyzer: FloorPlanAnalyzer = OrthogonalFloorPlanAnalyzer()
    private val _state = MutableStateFlow(RoomifyUiState())
    val state: StateFlow<RoomifyUiState> = _state.asStateFlow()
    private var persistenceJob: Job? = null

    init {
        viewModelScope.launch {
            val scene = sceneRepository.loadCurrent()
            val source = projectStore.loadSource()
            val style = scene?.materials?.paletteName?.let { label ->
                StyleCatalog.styles.firstOrNull { it.label.equals(label, ignoreCase = true) }?.id
            } ?: "modern"
            _state.value = _state.value.copy(
                scene = scene,
                sourceBitmap = source,
                selectedRoomId = scene?.rooms?.firstOrNull()?.id,
                planWidthM = scene?.widthM ?: 14.0,
                styleId = style,
                isBusy = false,
                status = if (scene == null) "Choose a floor-plan image or import authoritative JSON." else "Recovered the local JSON scene.",
                warnings = scene?.warnings.orEmpty(),
            )
        }
    }

    fun setPlanWidth(value: Double) {
        if (value !in 1.0..500.0) return
        _state.value = _state.value.copy(planWidthM = value, error = null)
    }

    fun analyzeImage(uri: Uri) {
        if (_state.value.isBusy) return
        viewModelScope.launch {
            mutateBusy("Reading image and extracting structural geometry…")
            runCatching {
                val source = projectStore.copyAndDecodeSource(uri)
                val result = analyzer.analyze(
                    source,
                    AnalysisOptions(
                        projectId = _state.value.scene?.projectId ?: "android-${UUID.randomUUID()}",
                        planWidthM = _state.value.planWidthM,
                    ),
                )
                projectStore.saveNormalizedSource(result.normalizedBitmap)
                sceneRepository.saveCurrent(result.scene)
                _state.value = _state.value.copy(
                    scene = result.scene,
                    sourceBitmap = result.normalizedBitmap,
                    selectedRoomId = result.scene.rooms.firstOrNull()?.id,
                    styleId = "modern",
                    isBusy = false,
                    status = "Image converted to JSON: ${result.scene.rooms.size} rooms and ${result.scene.walls.size} walls.",
                    error = null,
                    warnings = result.warnings,
                    hasUnsavedChanges = false,
                )
            }.onFailure(::showFailure)
        }
    }

    fun importJson(uri: Uri) {
        if (_state.value.isBusy) return
        viewModelScope.launch {
            mutateBusy("Validating floor-plan JSON…")
            runCatching { sceneRepository.importFrom(uri) }
                .onSuccess { scene ->
                    val style = StyleCatalog.styles.firstOrNull {
                        it.label.equals(scene.materials.paletteName, ignoreCase = true)
                    }?.id ?: "modern"
                    _state.value = _state.value.copy(
                        scene = scene,
                        selectedRoomId = scene.rooms.firstOrNull()?.id,
                        planWidthM = scene.widthM,
                        styleId = style,
                        isBusy = false,
                        status = "Imported authoritative JSON with ${scene.rooms.size} rooms.",
                        error = null,
                        warnings = scene.warnings,
                        hasUnsavedChanges = false,
                    )
                }
                .onFailure(::showFailure)
        }
    }

    fun exportJson(uri: Uri) {
        val scene = _state.value.scene ?: return
        viewModelScope.launch {
            mutateBusy("Writing portable scene JSON…")
            runCatching { sceneRepository.exportTo(uri, scene) }
                .onSuccess {
                    _state.value = _state.value.copy(
                        isBusy = false,
                        status = "JSON exported. The same file can reconstruct the plan on Android or desktop.",
                        error = null,
                        hasUnsavedChanges = false,
                    )
                }
                .onFailure(::showFailure)
        }
    }

    fun loadSample() {
        if (_state.value.isBusy) return
        viewModelScope.launch {
            mutateBusy("Loading sample JSON…")
            runCatching {
                getApplication<Application>().assets.open("sample_scene.json").bufferedReader().use { reader ->
                    SceneJsonCodec.decode(reader.readText())
                }
            }.onSuccess { scene ->
                sceneRepository.saveCurrent(scene)
                _state.value = _state.value.copy(
                    scene = scene,
                    selectedRoomId = scene.rooms.firstOrNull()?.id,
                    planWidthM = scene.widthM,
                    styleId = "modern",
                    isBusy = false,
                    status = "Sample JSON loaded.",
                    error = null,
                    warnings = scene.warnings,
                    hasUnsavedChanges = false,
                )
            }.onFailure(::showFailure)
        }
    }

    fun selectRoom(roomId: String?) {
        _state.value = _state.value.copy(selectedRoomId = roomId)
    }

    fun moveSelectedRoom(dx: Double, dz: Double) {
        val current = _state.value
        val scene = current.scene ?: return
        val roomId = current.selectedRoomId ?: return
        val updated = SceneGeometry.moveRoom(scene, roomId, dx, dz)
        updateScene(updated, "Room moved. JSON geometry updated.", persistImmediately = false)
    }

    fun renameSelectedRoom(name: String) {
        val current = _state.value
        val scene = current.scene ?: return
        val roomId = current.selectedRoomId ?: return
        updateScene(SceneGeometry.renameRoom(scene, roomId, name), "Room name updated.")
    }

    fun addRoom() {
        val scene = _state.value.scene ?: return
        val updated = SceneGeometry.addRoom(scene)
        updateScene(updated, "New editable room added.")
        _state.value = _state.value.copy(selectedRoomId = updated.rooms.lastOrNull()?.id)
    }

    fun deleteSelectedRoom() {
        val current = _state.value
        val scene = current.scene ?: return
        val roomId = current.selectedRoomId ?: return
        val updated = SceneGeometry.deleteRoom(scene, roomId)
        updateScene(updated, "Room removed from the JSON scene.")
        _state.value = _state.value.copy(selectedRoomId = updated.rooms.firstOrNull()?.id)
    }

    fun applyStyle(styleId: String) {
        val scene = _state.value.scene ?: return
        val updated = StyleCatalog.apply(scene, styleId)
        _state.value = _state.value.copy(styleId = styleId)
        updateScene(updated, "${StyleCatalog.byId(styleId).label} design applied to the JSON scene.")
    }

    fun setRenderMode(mode: RenderMode) {
        _state.value = _state.value.copy(renderMode = mode)
    }

    fun setShowSourceImage(show: Boolean) {
        _state.value = _state.value.copy(showSourceImage = show)
    }

    fun resetProject() {
        if (_state.value.isBusy) return
        viewModelScope.launch {
            mutateBusy("Clearing local project…")
            runCatching {
                sceneRepository.clear()
                projectStore.clearSource()
            }.onSuccess {
                _state.value = RoomifyUiState(
                    isBusy = false,
                    status = "Project cleared. Choose an image or import JSON.",
                )
            }.onFailure(::showFailure)
        }
    }

    fun clearError() {
        _state.value = _state.value.copy(error = null)
    }

    private fun updateScene(scene: SceneManifest, message: String, persistImmediately: Boolean = true) {
        val validated = SceneGeometry.validate(scene)
        _state.value = _state.value.copy(
            scene = validated,
            status = message,
            error = null,
            hasUnsavedChanges = true,
        )
        persistenceJob?.cancel()
        persistenceJob = viewModelScope.launch {
            if (!persistImmediately) delay(280)
            runCatching { sceneRepository.saveCurrent(validated) }
                .onSuccess { _state.value = _state.value.copy(hasUnsavedChanges = false) }
                .onFailure(::showFailure)
        }
    }

    private fun mutateBusy(status: String) {
        _state.value = _state.value.copy(isBusy = true, status = status, error = null)
    }

    private fun showFailure(throwable: Throwable) {
        _state.value = _state.value.copy(
            isBusy = false,
            error = throwable.message ?: "The operation failed.",
            status = "The last valid JSON scene was preserved.",
        )
    }
}
