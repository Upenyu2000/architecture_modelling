package com.upenyu.roomifyandroid.analysis

import android.graphics.Bitmap
import android.graphics.Color
import com.upenyu.roomifyandroid.model.Opening
import com.upenyu.roomifyandroid.model.ProjectMetadata
import com.upenyu.roomifyandroid.model.RoomShape
import com.upenyu.roomifyandroid.model.SceneGeometry
import com.upenyu.roomifyandroid.model.SceneManifest
import com.upenyu.roomifyandroid.model.WallSegment
import kotlin.math.abs
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext

/**
 * Deterministic, offline floor-plan parser for rectilinear plans.
 *
 * The parser intentionally extracts long structural runs and ignores short text/furniture marks. The resulting
 * SceneManifest is the authoritative source for every later render. Irregular and diagonal geometry remains fully
 * supported through JSON import and manual correction in the editor.
 */
class OrthogonalFloorPlanAnalyzer : FloorPlanAnalyzer {
    override suspend fun analyze(bitmap: Bitmap, options: AnalysisOptions): AnalysisResult = withContext(Dispatchers.Default) {
        require(options.planWidthM in 1.0..500.0) { "Plan width must be between 1 m and 500 m." }
        val normalized = normalizeBitmap(bitmap, options.maximumAnalysisDimensionPx)
        ensureActive()
        val grayscale = grayscale(normalized)
        val threshold = otsuThreshold(grayscale)
        val ink = BooleanArray(grayscale.size) { grayscale[it] <= threshold }
        val width = normalized.width
        val height = normalized.height
        val minimumRunPx = max(18, (width * options.minimumWallLengthM / options.planWidthM).toInt())
        val bridgeGapPx = max(1, min(width, height) / 500)
        val bandDistancePx = max(3, min(width, height) / 95)

        val horizontal = collapseParallel(
            mergeThickness(
                detectRuns(ink, width, height, horizontal = true, minimumRunPx = minimumRunPx, bridgeGapPx = bridgeGapPx),
                horizontal = true,
                adjacencyPx = max(2, min(width, height) / 420),
            ),
            horizontal = true,
            bandDistancePx = bandDistancePx,
        )
        val vertical = collapseParallel(
            mergeThickness(
                detectRuns(ink, width, height, horizontal = false, minimumRunPx = minimumRunPx, bridgeGapPx = bridgeGapPx),
                horizontal = false,
                adjacencyPx = max(2, min(width, height) / 420),
            ),
            horizontal = false,
            bandDistancePx = bandDistancePx,
        )
        ensureActive()

        val allLines = (horizontal + vertical).filter { it.length >= minimumRunPx }
        require(allLines.size >= 4) {
            "The image does not contain enough long structural lines. Use a clearer top-down plan or import its JSON geometry."
        }
        val bounds = structuralBounds(allLines, width, height)
        val pixelWidth = max(1.0, bounds.right - bounds.left)
        val pixelDepth = max(1.0, bounds.bottom - bounds.top)
        val metresPerPixel = options.planWidthM / pixelWidth
        val depthM = pixelDepth * metresPerPixel

        val walls = allLines.mapIndexed { index, line ->
            val start = pointToMetres(line.x1, line.y1, bounds, metresPerPixel)
            val end = pointToMetres(line.x2, line.y2, bounds, metresPerPixel)
            val nearBoundary = line.distanceTo(bounds) <= bandDistancePx * 1.5
            WallSegment(
                id = "wall-${index + 1}",
                start = start,
                end = end,
                height = options.wallHeightM,
                thickness = options.wallThicknessM,
                wallType = if (nearBoundary) "exterior" else "interior",
                confidence = line.confidence,
            )
        }

        val rooms = inferRooms(horizontal, vertical, bounds, metresPerPixel, options.minimumWallLengthM)
        val openings = inferOpenings(walls, options.wallThicknessM)
        val warnings = buildList {
            if (rooms.isEmpty()) add("Walls were recovered, but no closed rectangular rooms were confirmed. Move/add rooms or import corrected JSON.")
            if (rooms.size > 40) add("Many small rooms were detected. Increase the minimum wall length or correct the JSON geometry.")
            add("Automatic image analysis prioritises orthogonal structural walls. Diagonal and curved geometry should be corrected in JSON or the editor.")
        }
        val confidence = when {
            rooms.isEmpty() -> 0.42
            walls.size >= 8 && rooms.isNotEmpty() -> 0.82
            else -> 0.68
        }
        val firstRoom = rooms.maxByOrNull { it.areaM2 }
        val scene = SceneManifest(
            projectId = options.projectId,
            widthM = options.planWidthM,
            depthM = depthM,
            wallHeightM = options.wallHeightM,
            walls = walls,
            rooms = rooms,
            openings = openings,
            firstPersonStart = firstRoom?.centroid?.let { listOf(it[0], 1.62, it[1]) },
            collisionSegments = walls.map { listOf(it.start, it.end) },
            ceilingHeightM = options.wallHeightM,
            projectMetadata = ProjectMetadata(
                detectedRooms = rooms.size,
                detectedOpenings = openings.size,
                detectedObjects = 0,
                parserVersion = "android-vector-1.0",
                sourcePlanType = "image",
                structuralConfidence = confidence,
                extractedLabels = emptyList(),
            ),
            referenceImagePath = "internal://projects/current/source-plan.img",
            warnings = warnings,
        )
        AnalysisResult(SceneGeometry.validate(scene), cropToBounds(normalized, bounds), warnings)
    }

    private data class RawLine(
        val x1: Double,
        val y1: Double,
        val x2: Double,
        val y2: Double,
        val confidence: Double = 0.72,
    ) {
        val horizontal: Boolean get() = abs(y2 - y1) <= abs(x2 - x1)
        val length: Double get() = hypot(x2 - x1, y2 - y1)
        val coordinate: Double get() = if (horizontal) (y1 + y2) / 2.0 else (x1 + x2) / 2.0
        val rangeStart: Double get() = if (horizontal) min(x1, x2) else min(y1, y2)
        val rangeEnd: Double get() = if (horizontal) max(x1, x2) else max(y1, y2)

        fun distanceTo(bounds: Bounds): Double = minOf(
            abs(coordinate - if (horizontal) bounds.top else bounds.left),
            abs(coordinate - if (horizontal) bounds.bottom else bounds.right),
        )
    }

    private data class Bounds(val left: Double, val top: Double, val right: Double, val bottom: Double)

    private fun cropToBounds(bitmap: Bitmap, bounds: Bounds): Bitmap {
        val left = bounds.left.toInt().coerceIn(0, bitmap.width - 1)
        val top = bounds.top.toInt().coerceIn(0, bitmap.height - 1)
        val right = kotlin.math.ceil(bounds.right).toInt().coerceIn(left + 1, bitmap.width)
        val bottom = kotlin.math.ceil(bounds.bottom).toInt().coerceIn(top + 1, bitmap.height)
        return Bitmap.createBitmap(bitmap, left, top, right - left, bottom - top)
    }

    private fun normalizeBitmap(source: Bitmap, maximum: Int): Bitmap {
        val scale = min(1f, maximum.toFloat() / max(source.width, source.height).toFloat())
        val scaled = if (scale < 1f) {
            Bitmap.createScaledBitmap(source, max(1, (source.width * scale).toInt()), max(1, (source.height * scale).toInt()), true)
        } else {
            source.copy(Bitmap.Config.ARGB_8888, false) ?: source
        }
        val pixels = IntArray(scaled.width * scaled.height)
        scaled.getPixels(pixels, 0, scaled.width, 0, 0, scaled.width, scaled.height)
        var minX = scaled.width
        var minY = scaled.height
        var maxX = 0
        var maxY = 0
        for (y in 0 until scaled.height) {
            for (x in 0 until scaled.width) {
                val color = pixels[y * scaled.width + x]
                val gray = (Color.red(color) * 299 + Color.green(color) * 587 + Color.blue(color) * 114) / 1000
                if (gray < 245) {
                    minX = min(minX, x)
                    minY = min(minY, y)
                    maxX = max(maxX, x)
                    maxY = max(maxY, y)
                }
            }
        }
        if (minX >= maxX || minY >= maxY) return scaled
        val margin = max(4, min(scaled.width, scaled.height) / 80)
        val left = max(0, minX - margin)
        val top = max(0, minY - margin)
        val right = min(scaled.width, maxX + margin + 1)
        val bottom = min(scaled.height, maxY + margin + 1)
        return Bitmap.createBitmap(scaled, left, top, right - left, bottom - top)
    }

    private fun grayscale(bitmap: Bitmap): IntArray {
        val pixels = IntArray(bitmap.width * bitmap.height)
        bitmap.getPixels(pixels, 0, bitmap.width, 0, 0, bitmap.width, bitmap.height)
        return IntArray(pixels.size) { index ->
            val color = pixels[index]
            (Color.red(color) * 299 + Color.green(color) * 587 + Color.blue(color) * 114) / 1000
        }
    }

    private fun otsuThreshold(grayscale: IntArray): Int {
        val histogram = IntArray(256)
        grayscale.forEach { histogram[it.coerceIn(0, 255)]++ }
        val total = grayscale.size
        var totalWeighted = 0.0
        histogram.forEachIndexed { value, count -> totalWeighted += value * count.toDouble() }
        var backgroundWeight = 0
        var backgroundSum = 0.0
        var maximumVariance = -1.0
        var threshold = 160
        for (value in histogram.indices) {
            backgroundWeight += histogram[value]
            if (backgroundWeight == 0) continue
            val foregroundWeight = total - backgroundWeight
            if (foregroundWeight == 0) break
            backgroundSum += value * histogram[value].toDouble()
            val backgroundMean = backgroundSum / backgroundWeight
            val foregroundMean = (totalWeighted - backgroundSum) / foregroundWeight
            val variance = backgroundWeight.toDouble() * foregroundWeight.toDouble() *
                (backgroundMean - foregroundMean) * (backgroundMean - foregroundMean)
            if (variance > maximumVariance) {
                maximumVariance = variance
                threshold = value
            }
        }
        return threshold.coerceIn(65, 218)
    }

    private fun detectRuns(
        ink: BooleanArray,
        width: Int,
        height: Int,
        horizontal: Boolean,
        minimumRunPx: Int,
        bridgeGapPx: Int,
    ): List<RawLine> {
        val outer = if (horizontal) height else width
        val inner = if (horizontal) width else height
        val results = mutableListOf<RawLine>()
        for (coordinate in 0 until outer) {
            var runStart = -1
            var lastInk = -1
            var position = 0
            while (position < inner) {
                val index = if (horizontal) coordinate * width + position else position * width + coordinate
                if (ink[index]) {
                    if (runStart < 0) runStart = position
                    lastInk = position
                } else if (runStart >= 0 && position - lastInk > bridgeGapPx) {
                    if (lastInk - runStart + 1 >= minimumRunPx) {
                        results += if (horizontal) {
                            RawLine(runStart.toDouble(), coordinate.toDouble(), lastInk.toDouble(), coordinate.toDouble())
                        } else {
                            RawLine(coordinate.toDouble(), runStart.toDouble(), coordinate.toDouble(), lastInk.toDouble())
                        }
                    }
                    runStart = -1
                    lastInk = -1
                }
                position++
            }
            if (runStart >= 0 && lastInk - runStart + 1 >= minimumRunPx) {
                results += if (horizontal) {
                    RawLine(runStart.toDouble(), coordinate.toDouble(), lastInk.toDouble(), coordinate.toDouble())
                } else {
                    RawLine(coordinate.toDouble(), runStart.toDouble(), coordinate.toDouble(), lastInk.toDouble())
                }
            }
        }
        return results
    }

    private fun mergeThickness(lines: List<RawLine>, horizontal: Boolean, adjacencyPx: Int): List<RawLine> {
        val pending = lines.sortedWith(compareBy<RawLine> { it.coordinate }.thenBy { it.rangeStart }).toMutableList()
        val merged = mutableListOf<RawLine>()
        while (pending.isNotEmpty()) {
            val seed = pending.removeAt(0)
            val group = mutableListOf(seed)
            val iterator = pending.iterator()
            while (iterator.hasNext()) {
                val candidate = iterator.next()
                if (abs(candidate.coordinate - seed.coordinate) > adjacencyPx) continue
                if (overlapRatio(seed, candidate) < 0.62) continue
                group += candidate
                iterator.remove()
            }
            val coordinate = group.map { it.coordinate }.average()
            val start = group.minOf { it.rangeStart }
            val end = group.maxOf { it.rangeEnd }
            val confidence = (0.68 + min(0.25, group.size / 20.0)).coerceAtMost(0.93)
            merged += if (horizontal) RawLine(start, coordinate, end, coordinate, confidence)
            else RawLine(coordinate, start, coordinate, end, confidence)
        }
        return merged
    }

    private fun collapseParallel(lines: List<RawLine>, horizontal: Boolean, bandDistancePx: Int): List<RawLine> {
        val pending = lines.sortedByDescending { it.length }.toMutableList()
        val collapsed = mutableListOf<RawLine>()
        while (pending.isNotEmpty()) {
            val seed = pending.removeAt(0)
            val group = mutableListOf(seed)
            val iterator = pending.iterator()
            while (iterator.hasNext()) {
                val candidate = iterator.next()
                if (abs(candidate.coordinate - seed.coordinate) > bandDistancePx) continue
                if (overlapRatio(seed, candidate) < 0.74) continue
                group += candidate
                iterator.remove()
            }
            val weightedCoordinate = group.sumOf { it.coordinate * it.length } / group.sumOf { it.length }
            val start = group.minOf { it.rangeStart }
            val end = group.maxOf { it.rangeEnd }
            val confidence = group.maxOf { it.confidence }.coerceAtMost(0.96)
            collapsed += if (horizontal) RawLine(start, weightedCoordinate, end, weightedCoordinate, confidence)
            else RawLine(weightedCoordinate, start, weightedCoordinate, end, confidence)
        }
        return collapsed.sortedWith(compareBy<RawLine> { it.coordinate }.thenBy { it.rangeStart })
    }

    private fun overlapRatio(first: RawLine, second: RawLine): Double {
        val overlap = max(0.0, min(first.rangeEnd, second.rangeEnd) - max(first.rangeStart, second.rangeStart))
        return overlap / max(1.0, min(first.length, second.length))
    }

    private fun structuralBounds(lines: List<RawLine>, width: Int, height: Int): Bounds {
        val left = lines.minOfOrNull { min(it.x1, it.x2) } ?: 0.0
        val right = lines.maxOfOrNull { max(it.x1, it.x2) } ?: width.toDouble()
        val top = lines.minOfOrNull { min(it.y1, it.y2) } ?: 0.0
        val bottom = lines.maxOfOrNull { max(it.y1, it.y2) } ?: height.toDouble()
        return Bounds(left, top, right, bottom)
    }

    private fun pointToMetres(x: Double, y: Double, bounds: Bounds, metresPerPixel: Double): List<Double> = listOf(
        ((x - bounds.left) * metresPerPixel).coerceAtLeast(0.0),
        ((y - bounds.top) * metresPerPixel).coerceAtLeast(0.0),
    )

    private fun inferRooms(
        horizontal: List<RawLine>,
        vertical: List<RawLine>,
        bounds: Bounds,
        metresPerPixel: Double,
        minimumWallLengthM: Double,
    ): List<RoomShape> {
        val tolerance = max(4.0, min(bounds.right - bounds.left, bounds.bottom - bounds.top) / 90.0)
        val xs = clusterCoordinates(vertical.map { it.coordinate } + listOf(bounds.left, bounds.right), tolerance)
        val ys = clusterCoordinates(horizontal.map { it.coordinate } + listOf(bounds.top, bounds.bottom), tolerance)
        val rooms = mutableListOf<RoomShape>()
        for (xIndex in 0 until xs.lastIndex) {
            for (yIndex in 0 until ys.lastIndex) {
                val left = xs[xIndex]
                val right = xs[xIndex + 1]
                val top = ys[yIndex]
                val bottom = ys[yIndex + 1]
                val widthM = (right - left) * metresPerPixel
                val depthM = (bottom - top) * metresPerPixel
                if (widthM < max(0.55, minimumWallLengthM * 0.75) || depthM < max(0.55, minimumWallLengthM * 0.75)) continue
                if (widthM * depthM < 1.2) continue
                val enclosed = hasCoverage(horizontal, top, left, right, tolerance) &&
                    hasCoverage(horizontal, bottom, left, right, tolerance) &&
                    hasCoverage(vertical, left, top, bottom, tolerance) &&
                    hasCoverage(vertical, right, top, bottom, tolerance)
                if (!enclosed) continue
                val polygon = listOf(
                    pointToMetres(left, top, bounds, metresPerPixel),
                    pointToMetres(right, top, bounds, metresPerPixel),
                    pointToMetres(right, bottom, bounds, metresPerPixel),
                    pointToMetres(left, bottom, bounds, metresPerPixel),
                )
                val area = abs(SceneGeometry.polygonArea(polygon))
                if (rooms.any { existing -> overlapArea(existing.polygon, polygon) / min(existing.areaM2, area) > 0.86 }) continue
                val index = rooms.size + 1
                rooms += RoomShape(
                    id = "room-$index",
                    name = "Room $index",
                    polygon = polygon,
                    areaM2 = area,
                    centroid = SceneGeometry.centroid(polygon),
                    roomType = "room",
                    widthM = widthM,
                    depthM = depthM,
                    labelConfidence = 0.0,
                )
            }
        }
        return rooms.sortedByDescending { it.areaM2 }.mapIndexed { index, room -> room.copy(id = "room-${index + 1}", name = "Room ${index + 1}") }
    }

    private fun clusterCoordinates(values: List<Double>, tolerance: Double): List<Double> {
        val sorted = values.sorted()
        if (sorted.isEmpty()) return emptyList()
        val clusters = mutableListOf<MutableList<Double>>()
        sorted.forEach { value ->
            val current = clusters.lastOrNull()
            if (current == null || abs(current.average() - value) > tolerance) clusters += mutableListOf(value)
            else current += value
        }
        return clusters.map { it.average() }.distinct().sorted()
    }

    private fun hasCoverage(lines: List<RawLine>, coordinate: Double, start: Double, end: Double, tolerance: Double): Boolean {
        val targetLength = max(1.0, end - start)
        val intervals = lines
            .filter { abs(it.coordinate - coordinate) <= tolerance }
            .mapNotNull { line ->
                val overlapStart = max(start, line.rangeStart)
                val overlapEnd = min(end, line.rangeEnd)
                if (overlapEnd > overlapStart) overlapStart to overlapEnd else null
            }
            .sortedBy { it.first }
        if (intervals.isEmpty()) return false
        var covered = 0.0
        var currentStart = intervals.first().first
        var currentEnd = intervals.first().second
        for ((intervalStart, intervalEnd) in intervals.drop(1)) {
            if (intervalStart <= currentEnd + tolerance) currentEnd = max(currentEnd, intervalEnd)
            else {
                covered += currentEnd - currentStart
                currentStart = intervalStart
                currentEnd = intervalEnd
            }
        }
        covered += currentEnd - currentStart
        return covered / targetLength >= 0.72
    }

    private fun inferOpenings(walls: List<WallSegment>, wallThicknessM: Double): List<Opening> {
        val candidates = mutableListOf<Opening>()
        val horizontal = walls.filter { abs(it.start[1] - it.end[1]) < 0.08 }
        val vertical = walls.filter { abs(it.start[0] - it.end[0]) < 0.08 }
        fun inspect(group: List<WallSegment>, horizontalWall: Boolean) {
            val tolerance = max(0.12, wallThicknessM * 1.8)
            group.groupBy { wall ->
                val coordinate = if (horizontalWall) wall.start[1] else wall.start[0]
                (coordinate / tolerance).toInt()
            }.values.forEach { aligned ->
                val sorted = aligned.sortedBy { if (horizontalWall) min(it.start[0], it.end[0]) else min(it.start[1], it.end[1]) }
                for (index in 0 until sorted.lastIndex) {
                    val first = sorted[index]
                    val second = sorted[index + 1]
                    val firstEnd = if (horizontalWall) max(first.start[0], first.end[0]) else max(first.start[1], first.end[1])
                    val secondStart = if (horizontalWall) min(second.start[0], second.end[0]) else min(second.start[1], second.end[1])
                    val gap = secondStart - firstEnd
                    if (gap !in 0.55..2.4) continue
                    val coordinate = if (horizontalWall) (first.start[1] + second.start[1]) / 2.0 else (first.start[0] + second.start[0]) / 2.0
                    val along = (firstEnd + secondStart) / 2.0
                    candidates += Opening(
                        id = "opening-${candidates.size + 1}",
                        openingType = if (gap > 1.55) "open_passage" else "door",
                        position = if (horizontalWall) listOf(along, coordinate) else listOf(coordinate, along),
                        width = gap,
                        rotationDeg = if (horizontalWall) 0.0 else 90.0,
                        wallId = first.id,
                        wallIds = listOf(first.id, second.id),
                        source = "heuristic",
                        confidence = 0.58,
                    )
                }
            }
        }
        inspect(horizontal, true)
        inspect(vertical, false)
        return candidates.distinctBy { opening ->
            "${(opening.position[0] * 10).toInt()}:${(opening.position[1] * 10).toInt()}:${opening.openingType}"
        }
    }

    private fun overlapArea(first: List<List<Double>>, second: List<List<Double>>): Double {
        val firstLeft = first.minOf { it[0] }
        val firstRight = first.maxOf { it[0] }
        val firstTop = first.minOf { it[1] }
        val firstBottom = first.maxOf { it[1] }
        val secondLeft = second.minOf { it[0] }
        val secondRight = second.maxOf { it[0] }
        val secondTop = second.minOf { it[1] }
        val secondBottom = second.maxOf { it[1] }
        return max(0.0, min(firstRight, secondRight) - max(firstLeft, secondLeft)) *
            max(0.0, min(firstBottom, secondBottom) - max(firstTop, secondTop))
    }
}
