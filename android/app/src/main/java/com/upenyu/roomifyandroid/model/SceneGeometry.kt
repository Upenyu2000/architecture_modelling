package com.upenyu.roomifyandroid.model

import java.security.MessageDigest
import kotlin.math.abs
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

object SceneGeometry {
    private const val EPSILON = 1e-6

    fun validate(scene: SceneManifest): SceneManifest {
        require(scene.widthM in 1.0..500.0) { "Plan width must be between 1 m and 500 m." }
        require(scene.depthM in 1.0..500.0) { "Plan depth must be between 1 m and 500 m." }
        require(scene.wallHeightM in 1.8..12.0) { "Wall height is outside a practical range." }
        scene.walls.forEach { wall ->
            require(wall.start.size == 2 && wall.end.size == 2) { "Wall ${wall.id} must contain two-dimensional endpoints." }
            require(wall.start.all { it.isFinite() } && wall.end.all { it.isFinite() }) { "Wall ${wall.id} contains invalid coordinates." }
            require(distance(wall.start, wall.end) > 0.01) { "Wall ${wall.id} has no usable length." }
        }
        scene.rooms.forEach { room ->
            require(room.polygon.size >= 3) { "Room ${room.name} must have at least three points." }
            require(room.polygon.all { it.size == 2 && it.all { coordinate -> coordinate.isFinite() } }) {
                "Room ${room.name} contains invalid coordinates."
            }
            require(room.polygon.all { it[0] in -EPSILON..(scene.widthM + EPSILON) && it[1] in -EPSILON..(scene.depthM + EPSILON) }) {
                "Room ${room.name} extends outside the plan boundary."
            }
            require(abs(polygonArea(room.polygon)) > 0.02) { "Room ${room.name} has no usable area." }
            require(!selfIntersects(room.polygon)) { "Room ${room.name} crosses itself." }
        }
        return scene
    }

    fun polygonArea(points: List<List<Double>>): Double {
        if (points.size < 3) return 0.0
        var sum = 0.0
        for (index in points.indices) {
            val current = points[index]
            val next = points[(index + 1) % points.size]
            sum += current[0] * next[1] - next[0] * current[1]
        }
        return sum / 2.0
    }

    fun centroid(points: List<List<Double>>): List<Double> {
        val signedArea = polygonArea(points)
        if (abs(signedArea) < EPSILON) {
            return listOf(points.map { it[0] }.average(), points.map { it[1] }.average())
        }
        var x = 0.0
        var z = 0.0
        for (index in points.indices) {
            val current = points[index]
            val next = points[(index + 1) % points.size]
            val cross = current[0] * next[1] - next[0] * current[1]
            x += (current[0] + next[0]) * cross
            z += (current[1] + next[1]) * cross
        }
        val factor = 1.0 / (6.0 * signedArea)
        return listOf(x * factor, z * factor)
    }

    fun contains(points: List<List<Double>>, x: Double, z: Double): Boolean {
        if (points.indices.any { index -> pointOnSegment(listOf(x, z), points[index], points[(index + 1) % points.size]) }) return true
        var inside = false
        var previous = points.lastIndex
        for (current in points.indices) {
            val xi = points[current][0]
            val zi = points[current][1]
            val xj = points[previous][0]
            val zj = points[previous][1]
            val denominator = (zj - zi).takeUnless { abs(it) < 1e-12 } ?: 1e-12
            val intersects = (zi > z) != (zj > z) && x < (xj - xi) * (z - zi) / denominator + xi
            if (intersects) inside = !inside
            previous = current
        }
        return inside
    }

    fun moveRoom(scene: SceneManifest, roomId: String, dx: Double, dz: Double): SceneManifest {
        val room = scene.rooms.firstOrNull { it.id == roomId } ?: return scene
        val minX = room.polygon.minOf { it[0] }
        val maxX = room.polygon.maxOf { it[0] }
        val minZ = room.polygon.minOf { it[1] }
        val maxZ = room.polygon.maxOf { it[1] }
        val safeDx = dx.coerceIn(-minX, scene.widthM - maxX)
        val safeDz = dz.coerceIn(-minZ, scene.depthM - maxZ)
        if (abs(safeDx) < EPSILON && abs(safeDz) < EPSILON) return scene
        val movedPolygon = room.polygon.map { listOf(it[0] + safeDx, it[1] + safeDz) }
        if (scene.rooms.any { it.id != roomId && polygonsOverlapStrict(movedPolygon, it.polygon) }) return scene
        val moved = room.copy(
            polygon = movedPolygon,
            centroid = centroid(movedPolygon),
            areaM2 = abs(polygonArea(movedPolygon)),
        )
        val movedFurniture = scene.fixturesAndFurniture.map { item ->
            if (item.roomId == roomId && item.coordinates.size >= 3) {
                item.copy(coordinates = listOf(item.coordinates[0] + safeDx, item.coordinates[1], item.coordinates[2] + safeDz))
            } else item
        }
        val movedOpenings = scene.openings.map { opening ->
            if (opening.roomIds.size == 1 && opening.roomIds.first() == roomId && opening.position.size >= 2) {
                opening.copy(position = listOf(opening.position[0] + safeDx, opening.position[1] + safeDz))
            } else opening
        }
        return rebuildDerivedGeometry(
            scene.copy(
                rooms = scene.rooms.map { if (it.id == roomId) moved else it },
                fixturesAndFurniture = movedFurniture,
                openings = movedOpenings,
                layoutMode = "manual",
            ),
        )
    }

    fun renameRoom(scene: SceneManifest, roomId: String, name: String): SceneManifest {
        val clean = name.trim().take(80)
        if (clean.isBlank()) return scene
        return scene.copy(rooms = scene.rooms.map { if (it.id == roomId) it.copy(name = clean) else it })
    }

    fun addRoom(scene: SceneManifest): SceneManifest {
        val index = scene.rooms.size + 1
        val width = min(3.2, max(1.4, scene.widthM * 0.22))
        val depth = min(3.2, max(1.4, scene.depthM * 0.22))
        val step = 0.35
        var selected: List<List<Double>>? = null
        var z = 0.2
        while (z + depth <= scene.depthM - 0.2 && selected == null) {
            var x = 0.2
            while (x + width <= scene.widthM - 0.2) {
                val candidate = rectangle(x, z, width, depth)
                if (scene.rooms.none { polygonsOverlapStrict(candidate, it.polygon) }) {
                    selected = candidate
                    break
                }
                x += step
            }
            z += step
        }
        val polygon = selected ?: rectangle(
            x = max(0.0, (scene.widthM - width) / 2.0),
            z = max(0.0, (scene.depthM - depth) / 2.0),
            width = width,
            depth = depth,
        )
        val room = RoomShape(
            id = "room-manual-$index",
            name = "Room $index",
            polygon = polygon,
            areaM2 = abs(polygonArea(polygon)),
            centroid = centroid(polygon),
            roomType = "room",
            widthM = width,
            depthM = depth,
            labelConfidence = 1.0,
        )
        return rebuildDerivedGeometry(
            scene.copy(
                rooms = scene.rooms + room,
                layoutMode = "manual",
                projectMetadata = scene.projectMetadata.copy(detectedRooms = scene.rooms.size + 1),
            ),
        )
    }

    fun deleteRoom(scene: SceneManifest, roomId: String): SceneManifest = rebuildDerivedGeometry(
        scene.copy(
            rooms = scene.rooms.filterNot { it.id == roomId },
            openings = scene.openings.map { opening -> opening.copy(roomIds = opening.roomIds.filterNot { it == roomId }) },
            fixturesAndFurniture = scene.fixturesAndFurniture.filterNot { it.roomId == roomId },
            layoutMode = "manual",
            projectMetadata = scene.projectMetadata.copy(detectedRooms = max(0, scene.rooms.size - 1)),
        ),
    )

    fun rebuildDerivedGeometry(scene: SceneManifest): SceneManifest {
        if (scene.rooms.isEmpty()) {
            return scene.copy(walls = emptyList(), collisionSegments = emptyList(), openings = emptyList())
        }
        data class Edge(val start: List<Double>, val end: List<Double>, val owners: MutableSet<String>)
        val edges = linkedMapOf<String, Edge>()
        scene.rooms.sortedBy { it.id }.forEach { room ->
            room.polygon.indices.forEach { index ->
                val start = room.polygon[index]
                val end = room.polygon[(index + 1) % room.polygon.size]
                if (distance(start, end) <= 0.01) return@forEach
                val key = canonicalEdgeKey(start, end)
                val existing = edges[key]
                if (existing == null) edges[key] = Edge(start, end, mutableSetOf(room.id))
                else existing.owners += room.id
            }
        }
        val thickness = scene.walls.firstOrNull()?.thickness ?: 0.16
        val walls = edges.entries.sortedBy { it.key }.mapIndexed { index, entry ->
            val edge = entry.value
            val owners = edge.owners.sorted()
            WallSegment(
                id = "wall-${index + 1}",
                start = edge.start,
                end = edge.end,
                height = scene.wallHeightM,
                thickness = thickness,
                wallType = if (owners.size == 1) "exterior" else "interior",
                confidence = 1.0,
                ownerRoomId = owners.singleOrNull(),
                sharedGroupId = if (owners.size > 1) "shared-${index + 1}" else null,
            )
        }
        val openings = scene.openings.mapNotNull { opening ->
            val ranked = walls.map { wall -> wall to pointSegmentDistance(opening.position, wall.start, wall.end) }
                .sortedBy { it.second }
            val closest = ranked.firstOrNull() ?: return@mapNotNull null
            val allowedDistance = max(0.45, opening.width / 2.0 + closest.first.thickness)
            if (closest.second > allowedDistance) return@mapNotNull null
            val linked = ranked.takeWhile { it.second <= closest.second + 0.08 }.map { it.first.id }.distinct()
            opening.copy(wallId = linked.firstOrNull(), wallIds = linked)
        }
        return scene.copy(
            walls = walls,
            openings = openings,
            collisionSegments = walls.map { listOf(it.start, it.end) },
            projectMetadata = scene.projectMetadata.copy(
                detectedRooms = scene.rooms.size,
                detectedOpenings = openings.size,
            ),
        )
    }

    fun fingerprint(scene: SceneManifest): String {
        val canonical = buildString {
            append(scene.widthM).append('|').append(scene.depthM).append('|').append(scene.wallHeightM).append('|')
            scene.walls.sortedBy { it.id }.forEach { wall ->
                append(wall.id).append(':').append(wall.start.joinToString(",")).append('>')
                    .append(wall.end.joinToString(",")).append(':').append(wall.thickness).append(';')
            }
            scene.rooms.sortedBy { it.id }.forEach { room ->
                append(room.id).append(':')
                room.polygon.forEach { point -> append(point.joinToString(",")).append('/') }
                append(';')
            }
            scene.openings.sortedBy { it.id }.forEach { opening ->
                append(opening.id).append(':').append(opening.position.joinToString(","))
                    .append(':').append(opening.width).append(';')
            }
        }
        return MessageDigest.getInstance("SHA-256")
            .digest(canonical.toByteArray())
            .joinToString("") { "%02x".format(it) }
    }

    private fun rectangle(x: Double, z: Double, width: Double, depth: Double): List<List<Double>> = listOf(
        listOf(x, z),
        listOf(x + width, z),
        listOf(x + width, z + depth),
        listOf(x, z + depth),
    )

    private fun selfIntersects(points: List<List<Double>>): Boolean {
        for (first in points.indices) {
            val firstNext = (first + 1) % points.size
            for (second in first + 1 until points.size) {
                val secondNext = (second + 1) % points.size
                if (first == second || firstNext == second || secondNext == first) continue
                if (first == 0 && secondNext == 0) continue
                if (segmentsIntersectStrict(points[first], points[firstNext], points[second], points[secondNext])) return true
            }
        }
        return false
    }

    private fun polygonsOverlapStrict(first: List<List<Double>>, second: List<List<Double>>): Boolean {
        val overlapX = min(first.maxOf { it[0] }, second.maxOf { it[0] }) - max(first.minOf { it[0] }, second.minOf { it[0] })
        val overlapZ = min(first.maxOf { it[1] }, second.maxOf { it[1] }) - max(first.minOf { it[1] }, second.minOf { it[1] })
        if (overlapX <= EPSILON || overlapZ <= EPSILON) return false
        first.indices.forEach { firstIndex ->
            second.indices.forEach { secondIndex ->
                if (segmentsIntersectStrict(
                        first[firstIndex], first[(firstIndex + 1) % first.size],
                        second[secondIndex], second[(secondIndex + 1) % second.size],
                    )
                ) return true
            }
        }
        val firstCentroid = centroid(first)
        val secondCentroid = centroid(second)
        return contains(second, firstCentroid[0], firstCentroid[1]) || contains(first, secondCentroid[0], secondCentroid[1])
    }

    private fun segmentsIntersectStrict(a: List<Double>, b: List<Double>, c: List<Double>, d: List<Double>): Boolean {
        fun orientation(p: List<Double>, q: List<Double>, r: List<Double>): Double =
            (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
        val o1 = orientation(a, b, c)
        val o2 = orientation(a, b, d)
        val o3 = orientation(c, d, a)
        val o4 = orientation(c, d, b)
        return o1 * o2 < -EPSILON && o3 * o4 < -EPSILON
    }

    private fun pointOnSegment(point: List<Double>, start: List<Double>, end: List<Double>): Boolean {
        val cross = (point[1] - start[1]) * (end[0] - start[0]) - (point[0] - start[0]) * (end[1] - start[1])
        if (abs(cross) > 1e-5) return false
        return point[0] in (min(start[0], end[0]) - EPSILON)..(max(start[0], end[0]) + EPSILON) &&
            point[1] in (min(start[1], end[1]) - EPSILON)..(max(start[1], end[1]) + EPSILON)
    }

    private fun canonicalEdgeKey(start: List<Double>, end: List<Double>): String {
        fun quantize(point: List<Double>): Pair<Int, Int> =
            (point[0] * 1000.0).roundToInt() to (point[1] * 1000.0).roundToInt()
        val first = quantize(start)
        val second = quantize(end)
        val ordered = if (first.first < second.first || (first.first == second.first && first.second <= second.second)) {
            first to second
        } else second to first
        return "${ordered.first.first},${ordered.first.second}:${ordered.second.first},${ordered.second.second}"
    }

    private fun pointSegmentDistance(point: List<Double>, start: List<Double>, end: List<Double>): Double {
        if (point.size < 2 || start.size < 2 || end.size < 2) return Double.POSITIVE_INFINITY
        val dx = end[0] - start[0]
        val dz = end[1] - start[1]
        val lengthSquared = dx * dx + dz * dz
        if (lengthSquared < EPSILON) return distance(point, start)
        val t = (((point[0] - start[0]) * dx + (point[1] - start[1]) * dz) / lengthSquared).coerceIn(0.0, 1.0)
        return hypot(point[0] - (start[0] + t * dx), point[1] - (start[1] + t * dz))
    }

    private fun distance(first: List<Double>, second: List<Double>): Double =
        hypot(first[0] - second[0], first[1] - second[1])
}
