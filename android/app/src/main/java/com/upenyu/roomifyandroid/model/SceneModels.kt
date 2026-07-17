package com.upenyu.roomifyandroid.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class WallSegment(
    val id: String,
    val start: List<Double>,
    val end: List<Double>,
    val height: Double,
    val thickness: Double = 0.16,
    @SerialName("wall_type") val wallType: String = "interior",
    val confidence: Double = 0.75,
    @SerialName("owner_room_id") val ownerRoomId: String? = null,
    @SerialName("linked_wall_ids") val linkedWallIds: List<String> = emptyList(),
    @SerialName("shared_group_id") val sharedGroupId: String? = null,
    @SerialName("render_offset") val renderOffset: List<Double> = listOf(0.0, 0.0),
    @SerialName("render_thickness") val renderThickness: Double? = null,
)

@Serializable
data class RoomShape(
    val id: String,
    val name: String,
    val polygon: List<List<Double>>,
    @SerialName("area_m2") val areaM2: Double,
    val centroid: List<Double>,
    @SerialName("room_type") val roomType: String = "room",
    @SerialName("width_m") val widthM: Double? = null,
    @SerialName("depth_m") val depthM: Double? = null,
    @SerialName("extracted_dimension") val extractedDimension: String? = null,
    @SerialName("label_confidence") val labelConfidence: Double = 0.0,
)

@Serializable
data class Opening(
    val id: String,
    @SerialName("opening_type") val openingType: String,
    val position: List<Double>,
    val width: Double,
    val height: Double = 2.1,
    @SerialName("rotation_deg") val rotationDeg: Double = 0.0,
    @SerialName("wall_id") val wallId: String? = null,
    @SerialName("wall_ids") val wallIds: List<String> = emptyList(),
    @SerialName("room_ids") val roomIds: List<String> = emptyList(),
    @SerialName("portal_id") val portalId: String? = null,
    @SerialName("placement_ratio") val placementRatio: Double? = null,
    @SerialName("swing_direction") val swingDirection: String = "none",
    @SerialName("hinge_side") val hingeSide: String = "none",
    @SerialName("swing_angle_deg") val swingAngleDeg: Double = 90.0,
    @SerialName("sill_height") val sillHeight: Double = 0.9,
    val interactive: Boolean = true,
    @SerialName("default_open") val defaultOpen: Boolean = false,
    val source: String = "heuristic",
    val confidence: Double = 0.6,
)

@Serializable
data class SceneAsset(
    val id: String,
    val category: String,
    val slot: String,
    val label: String,
    @SerialName("room_id") val roomId: String? = null,
    val position: List<Double>,
    @SerialName("rotation_y") val rotationY: Double = 0.0,
    val size: List<Double>,
    @SerialName("source_url") val sourceUrl: String? = null,
    @SerialName("source_path") val sourcePath: String? = null,
    @SerialName("mesh_url") val meshUrl: String? = null,
    @SerialName("mesh_path") val meshPath: String? = null,
    val source: String = "user_upload",
    val confidence: Double = 1.0,
)

@Serializable
data class ArchitecturalObject(
    val id: String,
    @SerialName("object_type") val objectType: String,
    @SerialName("asset_id") val assetId: String,
    val category: String,
    @SerialName("room_id") val roomId: String? = null,
    val coordinates: List<Double>,
    @SerialName("rotation_deg") val rotationDeg: Double = 0.0,
    val scale: List<Double> = listOf(1.0, 1.0, 1.0),
    val size: List<Double> = listOf(1.0, 1.0, 1.0),
    val source: String = "room_inference",
    val confidence: Double = 0.45,
)

@Serializable
data class MaterialSpec(
    val name: String,
    @SerialName("material_type") val materialType: String,
    @SerialName("hex_color") val hexColor: String,
    val roughness: Double = 0.6,
    val metallic: Double = 0.0,
    val specular: Double = 0.5,
    @SerialName("texture_url") val textureUrl: String? = null,
    @SerialName("normal_url") val normalUrl: String? = null,
    @SerialName("displacement_url") val displacementUrl: String? = null,
    @SerialName("texture_scale") val textureScale: Double = 1.0,
)

@Serializable
data class SceneMaterials(
    @SerialName("palette_name") val paletteName: String = "Modern",
    @SerialName("floor_global") val floorGlobal: MaterialSpec = MaterialSpec(
        name = "Natural Oak",
        materialType = "wood",
        hexColor = "#B58A5A",
        roughness = 0.42,
    ),
    @SerialName("walls_global") val wallsGlobal: MaterialSpec = MaterialSpec(
        name = "Warm Architectural White",
        materialType = "plaster",
        hexColor = "#EEEAE2",
        roughness = 0.76,
    ),
    @SerialName("exterior_walls") val exteriorWalls: MaterialSpec = MaterialSpec(
        name = "Pale Concrete",
        materialType = "concrete",
        hexColor = "#A8AAA6",
        roughness = 0.82,
    ),
    val accent: MaterialSpec = MaterialSpec(
        name = "Charcoal Graphite",
        materialType = "paint",
        hexColor = "#32383A",
        roughness = 0.38,
    ),
    @SerialName("fixture_metal") val fixtureMetal: MaterialSpec = MaterialSpec(
        name = "Architectural Metal",
        materialType = "metal",
        hexColor = "#A5A7AA",
        roughness = 0.24,
        metallic = 0.82,
        specular = 0.75,
    ),
)

@Serializable
data class ProjectMetadata(
    @SerialName("scale_ratio") val scaleRatio: String = "user_calibrated",
    @SerialName("detected_rooms") val detectedRooms: Int = 0,
    @SerialName("detected_openings") val detectedOpenings: Int = 0,
    @SerialName("detected_objects") val detectedObjects: Int = 0,
    @SerialName("parser_version") val parserVersion: String = "android-vector-1.0",
    @SerialName("source_plan_type") val sourcePlanType: String = "image",
    @SerialName("structural_confidence") val structuralConfidence: Double = 0.0,
    @SerialName("ocr_status") val ocrStatus: String = "text_suppressed_by_geometry_filter",
    @SerialName("extracted_labels") val extractedLabels: List<String> = emptyList(),
)

@Serializable
data class SceneManifest(
    @SerialName("schema_version") val schemaVersion: String = "roomify.scene.v1",
    @SerialName("project_id") val projectId: String,
    @SerialName("width_m") val widthM: Double,
    @SerialName("depth_m") val depthM: Double,
    @SerialName("wall_height_m") val wallHeightM: Double,
    val walls: List<WallSegment>,
    val rooms: List<RoomShape>,
    val assets: List<SceneAsset> = emptyList(),
    @SerialName("camera_path") val cameraPath: List<List<Double>> = emptyList(),
    val openings: List<Opening> = emptyList(),
    @SerialName("fixtures_and_furniture") val fixturesAndFurniture: List<ArchitecturalObject> = emptyList(),
    val materials: SceneMaterials = SceneMaterials(),
    @SerialName("project_metadata") val projectMetadata: ProjectMetadata = ProjectMetadata(),
    @SerialName("first_person_start") val firstPersonStart: List<Double>? = null,
    @SerialName("collision_segments") val collisionSegments: List<List<List<Double>>> = emptyList(),
    @SerialName("ceiling_height_m") val ceilingHeightM: Double = 2.8,
    @SerialName("cutaway_height_m") val cutawayHeightM: Double = 1.65,
    @SerialName("floor_texture_url") val floorTextureUrl: String? = null,
    @SerialName("floor_texture_path") val floorTexturePath: String? = null,
    @SerialName("wall_texture_url") val wallTextureUrl: String? = null,
    @SerialName("wall_texture_path") val wallTexturePath: String? = null,
    @SerialName("reference_image_url") val referenceImageUrl: String? = null,
    @SerialName("reference_image_path") val referenceImagePath: String? = null,
    @SerialName("detection_preview_url") val detectionPreviewUrl: String? = null,
    @SerialName("architecture_json_url") val architectureJsonUrl: String? = null,
    @SerialName("wall_detection_mode") val wallDetectionMode: String = "balanced",
    @SerialName("plan_type") val planType: String = "auto",
    @SerialName("layout_mode") val layoutMode: String = "automatic",
    val warnings: List<String> = emptyList(),
)
