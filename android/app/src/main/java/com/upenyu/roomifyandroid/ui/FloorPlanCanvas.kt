package com.upenyu.roomifyandroid.ui

import android.graphics.Paint
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import com.upenyu.roomifyandroid.model.ArchitecturalObject
import com.upenyu.roomifyandroid.model.RoomShape
import com.upenyu.roomifyandroid.model.SceneGeometry
import com.upenyu.roomifyandroid.model.SceneManifest
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin

private data class PlanViewport(val scale: Float, val offset: Offset) {
    fun toScreen(point: List<Double>): Offset = Offset(
        offset.x + point[0].toFloat() * scale,
        offset.y + point[1].toFloat() * scale,
    )

    fun toWorld(point: Offset): Pair<Double, Double> =
        ((point.x - offset.x) / scale).toDouble() to ((point.y - offset.y) / scale).toDouble()
}

@Composable
fun FloorPlanCanvas(
    scene: SceneManifest,
    sourceBitmap: android.graphics.Bitmap?,
    showSourceImage: Boolean,
    renderMode: RenderMode,
    selectedRoomId: String?,
    onSelectRoom: (String?) -> Unit,
    onMoveSelectedRoom: (Double, Double) -> Unit,
    modifier: Modifier = Modifier,
) {
    var canvasSize by remember { mutableStateOf(IntSize.Zero) }
    val sourceImage = remember(sourceBitmap) { sourceBitmap?.asImageBitmap() }
    val latestScene by rememberUpdatedState(scene)
    val latestOnSelectRoom by rememberUpdatedState(onSelectRoom)
    val latestOnMoveSelectedRoom by rememberUpdatedState(onMoveSelectedRoom)
    val background = Color(0xFFF4F4F5)
    val floorColor = parseColor(scene.materials.floorGlobal.hexColor, Color(0xFFD7B38A))
    val wallColor = parseColor(scene.materials.wallsGlobal.hexColor, Color(0xFFF3F0EA))
    val exteriorColor = parseColor(scene.materials.exteriorWalls.hexColor, Color(0xFF6B7280))
    val accentColor = parseColor(scene.materials.accent.hexColor, Color(0xFFF97316))
    val viewport = remember(scene.widthM, scene.depthM, canvasSize) {
        calculatePlanViewport(scene, canvasSize)
    }

    Box(
        modifier = modifier
            .background(background)
            .onSizeChanged { canvasSize = it }
            .pointerInput(renderMode, viewport) {
                if (renderMode != RenderMode.PLAN || viewport == null) return@pointerInput
                var dragRoomId: String? = null
                detectDragGestures(
                    onDragStart = { start ->
                        val (x, z) = viewport.toWorld(start)
                        dragRoomId = latestScene.rooms.lastOrNull { SceneGeometry.contains(it.polygon, x, z) }?.id
                        latestOnSelectRoom(dragRoomId)
                    },
                    onDragEnd = { dragRoomId = null },
                    onDragCancel = { dragRoomId = null },
                    onDrag = { change, amount ->
                        change.consume()
                        if (dragRoomId != null) {
                            latestOnMoveSelectedRoom(
                                (amount.x / viewport.scale).toDouble(),
                                (amount.y / viewport.scale).toDouble(),
                            )
                        }
                    },
                )
            },
    ) {
        Canvas(Modifier.fillMaxSize()) {
            if (renderMode == RenderMode.PLAN) {
                val planViewport = viewport ?: return@Canvas
                if (showSourceImage && sourceImage != null) {
                    val topLeft = planViewport.toScreen(listOf(0.0, 0.0))
                    val bottomRight = planViewport.toScreen(listOf(scene.widthM, scene.depthM))
                    drawImage(
                        image = sourceImage,
                        dstOffset = IntOffset(topLeft.x.toInt(), topLeft.y.toInt()),
                        dstSize = IntSize(
                            max(1, (bottomRight.x - topLeft.x).toInt()),
                            max(1, (bottomRight.y - topLeft.y).toInt()),
                        ),
                        alpha = 0.22f,
                    )
                }
                drawPlan(scene, planViewport, floorColor, exteriorColor, accentColor, background, selectedRoomId)
            } else {
                drawIsometric(scene, floorColor, wallColor, exteriorColor, accentColor, selectedRoomId)
            }
        }
    }
}

private fun calculatePlanViewport(scene: SceneManifest, size: IntSize): PlanViewport? {
    if (size.width <= 0 || size.height <= 0) return null
    val padding = 30f
    val usableWidth = max(1f, size.width - padding * 2f)
    val usableHeight = max(1f, size.height - padding * 2f)
    val scale = min(usableWidth / scene.widthM.toFloat(), usableHeight / scene.depthM.toFloat())
    val drawnWidth = scene.widthM.toFloat() * scale
    val drawnHeight = scene.depthM.toFloat() * scale
    return PlanViewport(
        scale = scale,
        offset = Offset((size.width - drawnWidth) / 2f, (size.height - drawnHeight) / 2f),
    )
}

private fun DrawScope.drawPlan(
    scene: SceneManifest,
    viewport: PlanViewport,
    floorColor: Color,
    wallColor: Color,
    accentColor: Color,
    background: Color,
    selectedRoomId: String?,
) {
    scene.rooms.forEachIndexed { index, room ->
        val path = roomPath(room, viewport)
        val selected = room.id == selectedRoomId
        val roomTint = floorColor.blend(Color.White, (index % 5) * 0.045f)
        drawPath(path, color = if (selected) accentColor.copy(alpha = 0.28f) else roomTint.copy(alpha = 0.62f))
        drawPath(path, color = if (selected) accentColor else Color(0xFF9CA3AF), style = Stroke(if (selected) 3.5f else 1.2f))
        drawRoomLabel(room, viewport, selected)
    }

    scene.walls.forEach { wall ->
        val start = viewport.toScreen(wall.start)
        val end = viewport.toScreen(wall.end)
        val width = max(2.5f, wall.thickness.toFloat() * viewport.scale)
        val color = if (wall.wallType == "exterior") wallColor else Color(0xFF3F3F46)
        drawLine(color = color, start = start, end = end, strokeWidth = width)
    }

    scene.openings.forEach { opening ->
        val center = viewport.toScreen(opening.position)
        val half = opening.width.toFloat() * viewport.scale / 2f
        val angle = Math.toRadians(opening.rotationDeg).toFloat()
        val delta = Offset(cos(angle) * half, sin(angle) * half)
        drawLine(background, center - delta, center + delta, strokeWidth = max(6f, scene.wallHeightM.toFloat()))
        drawLine(accentColor, center - delta, center + delta, strokeWidth = 1.6f)
    }

    scene.fixturesAndFurniture.forEach { item -> drawFurniture(item, viewport, accentColor) }
}

private fun DrawScope.drawRoomLabel(room: RoomShape, viewport: PlanViewport, selected: Boolean) {
    if (room.centroid.size < 2) return
    val center = viewport.toScreen(room.centroid)
    drawContext.canvas.nativeCanvas.drawText(
        room.name,
        center.x,
        center.y,
        Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = if (selected) android.graphics.Color.rgb(194, 65, 12) else android.graphics.Color.rgb(39, 39, 42)
            textSize = max(20f, viewport.scale * 0.18f)
            textAlign = Paint.Align.CENTER
            isFakeBoldText = selected
        },
    )
}

private fun DrawScope.drawFurniture(item: ArchitecturalObject, viewport: PlanViewport, accent: Color) {
    if (item.coordinates.size < 3 || item.size.size < 3) return
    val center = viewport.toScreen(listOf(item.coordinates[0], item.coordinates[2]))
    val width = max(3f, item.size[0].toFloat() * viewport.scale)
    val depth = max(3f, item.size[2].toFloat() * viewport.scale)
    val rect = Rect(center.x - width / 2f, center.y - depth / 2f, center.x + width / 2f, center.y + depth / 2f)
    val color = objectColor(item, accent)
    drawRect(color.copy(alpha = 0.28f), rect.topLeft, rect.size)
    drawRect(color.copy(alpha = 0.78f), rect.topLeft, rect.size, style = Stroke(1.2f))
}

private fun roomPath(room: RoomShape, viewport: PlanViewport): Path = Path().apply {
    room.polygon.firstOrNull()?.let { first ->
        val point = viewport.toScreen(first)
        moveTo(point.x, point.y)
        room.polygon.drop(1).forEach { next ->
            val screen = viewport.toScreen(next)
            lineTo(screen.x, screen.y)
        }
        close()
    }
}

private fun DrawScope.drawIsometric(
    scene: SceneManifest,
    floorColor: Color,
    wallColor: Color,
    exteriorColor: Color,
    accentColor: Color,
    selectedRoomId: String?,
) {
    val padding = 40f
    val projectedCorners = listOf(
        isoPoint(0.0, 0.0),
        isoPoint(scene.widthM, 0.0),
        isoPoint(scene.widthM, scene.depthM),
        isoPoint(0.0, scene.depthM),
    )
    val minX = projectedCorners.minOf { it.x }
    val maxX = projectedCorners.maxOf { it.x }
    val minY = projectedCorners.minOf { it.y }
    val maxY = projectedCorners.maxOf { it.y }
    val scale = min(
        (size.width - padding * 2f) / max(1f, maxX - minX),
        (size.height - padding * 2f) / max(1f, maxY - minY + scene.wallHeightM.toFloat()),
    )
    val offset = Offset(
        (size.width - (maxX - minX) * scale) / 2f - minX * scale,
        (size.height - (maxY - minY) * scale) / 2f - minY * scale + scene.wallHeightM.toFloat() * scale * 0.35f,
    )
    fun project(point: List<Double>, elevation: Double = 0.0): Offset {
        val iso = isoPoint(point[0], point[1])
        return Offset(offset.x + iso.x * scale, offset.y + iso.y * scale - elevation.toFloat() * scale * 0.72f)
    }

    scene.rooms.sortedBy { it.centroid.getOrElse(1) { 0.0 } }.forEachIndexed { index, room ->
        val path = Path()
        room.polygon.firstOrNull()?.let { first ->
            val start = project(first)
            path.moveTo(start.x, start.y)
            room.polygon.drop(1).forEach { point ->
                val screen = project(point)
                path.lineTo(screen.x, screen.y)
            }
            path.close()
        }
        val selected = room.id == selectedRoomId
        drawPath(
            path,
            color = if (selected) accentColor.copy(alpha = 0.72f) else floorColor.blend(Color.White, index * 0.03f).copy(alpha = 0.94f),
        )
        drawPath(path, color = if (selected) accentColor else Color(0xFF71717A), style = Stroke(1.1f))
    }

    scene.fixturesAndFurniture
        .filter { it.coordinates.size >= 3 && it.size.size >= 3 }
        .sortedBy { it.coordinates[0] + it.coordinates[2] }
        .forEach { item ->
            val width = max(0.08, item.size[0])
            val height = max(0.08, item.size[1])
            val depth = max(0.08, item.size[2])
            val cx = item.coordinates[0]
            val cz = item.coordinates[2]
            val base = listOf(
                listOf(cx - width / 2.0, cz - depth / 2.0),
                listOf(cx + width / 2.0, cz - depth / 2.0),
                listOf(cx + width / 2.0, cz + depth / 2.0),
                listOf(cx - width / 2.0, cz + depth / 2.0),
            )
            val bottom = base.map { project(it) }
            val top = base.map { project(it, height) }
            val color = objectColor(item, accentColor)
            val rightFace = Path().apply {
                moveTo(bottom[1].x, bottom[1].y)
                lineTo(bottom[2].x, bottom[2].y)
                lineTo(top[2].x, top[2].y)
                lineTo(top[1].x, top[1].y)
                close()
            }
            val leftFace = Path().apply {
                moveTo(bottom[2].x, bottom[2].y)
                lineTo(bottom[3].x, bottom[3].y)
                lineTo(top[3].x, top[3].y)
                lineTo(top[2].x, top[2].y)
                close()
            }
            val topFace = Path().apply {
                moveTo(top[0].x, top[0].y)
                top.drop(1).forEach { lineTo(it.x, it.y) }
                close()
            }
            drawPath(rightFace, color.blend(Color.Black, 0.24f))
            drawPath(leftFace, color.blend(Color.Black, 0.12f))
            drawPath(topFace, color.blend(Color.White, 0.12f))
            drawPath(topFace, Color(0xFF52525B), style = Stroke(0.8f))
        }

    scene.walls.sortedBy { max(it.start[1], it.end[1]) }.forEach { wall ->
        val bottomStart = project(wall.start)
        val bottomEnd = project(wall.end)
        val topStart = project(wall.start, wall.height)
        val topEnd = project(wall.end, wall.height)
        val face = Path().apply {
            moveTo(bottomStart.x, bottomStart.y)
            lineTo(bottomEnd.x, bottomEnd.y)
            lineTo(topEnd.x, topEnd.y)
            lineTo(topStart.x, topStart.y)
            close()
        }
        drawPath(face, if (wall.wallType == "exterior") exteriorColor else wallColor)
        drawPath(face, Color(0xFF52525B), style = Stroke(0.9f))
    }

    scene.openings.forEach { opening ->
        if (opening.position.size < 2) return@forEach
        val half = opening.width / 2.0
        val angle = Math.toRadians(opening.rotationDeg)
        val dx = cos(angle) * half
        val dz = sin(angle) * half
        val start = listOf(opening.position[0] - dx, opening.position[1] - dz)
        val end = listOf(opening.position[0] + dx, opening.position[1] + dz)
        val sill = if (opening.openingType == "window") opening.sillHeight else 0.0
        val openingHeight = min(opening.height, scene.wallHeightM - sill).coerceAtLeast(0.2)
        val bottomStart = project(start, sill)
        val bottomEnd = project(end, sill)
        val topStart = project(start, sill + openingHeight)
        val topEnd = project(end, sill + openingHeight)
        val face = Path().apply {
            moveTo(bottomStart.x, bottomStart.y)
            lineTo(bottomEnd.x, bottomEnd.y)
            lineTo(topEnd.x, topEnd.y)
            lineTo(topStart.x, topStart.y)
            close()
        }
        val color = if (opening.openingType == "window") Color(0xFF93C5FD) else Color(0xFF374151)
        drawPath(face, color.copy(alpha = 0.94f))
        drawPath(face, Color(0xFF111827), style = Stroke(0.8f))
    }
}

private fun isoPoint(x: Double, z: Double): Offset = Offset(
    ((x - z) * 0.82).toFloat(),
    ((x + z) * 0.41).toFloat(),
)

private fun objectColor(item: ArchitecturalObject, fallback: Color): Color {
    val value = Regex("#[0-9A-Fa-f]{6}").find(item.assetId)?.value ?: return fallback
    return parseColor(value, fallback)
}

private fun parseColor(value: String, fallback: Color): Color = runCatching {
    Color(android.graphics.Color.parseColor(value))
}.getOrDefault(fallback)

private fun Color.blend(other: Color, amount: Float): Color {
    val factor = amount.coerceIn(0f, 1f)
    return Color(
        red = red + (other.red - red) * factor,
        green = green + (other.green - green) * factor,
        blue = blue + (other.blue - blue) * factor,
        alpha = alpha + (other.alpha - alpha) * factor,
    )
}
