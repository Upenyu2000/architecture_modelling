package com.upenyu.roomifyandroid

import com.upenyu.roomifyandroid.model.RoomShape
import com.upenyu.roomifyandroid.model.SceneGeometry
import com.upenyu.roomifyandroid.model.SceneManifest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SceneGeometryTest {
    private val room = RoomShape(
        id = "room-1",
        name = "Living Room",
        polygon = listOf(listOf(1.0, 1.0), listOf(4.0, 1.0), listOf(4.0, 3.0), listOf(1.0, 3.0)),
        areaM2 = 6.0,
        centroid = listOf(2.5, 2.0),
    )
    private val scene = SceneManifest(
        projectId = "test",
        widthM = 8.0,
        depthM = 6.0,
        wallHeightM = 2.8,
        walls = emptyList(),
        rooms = listOf(room),
    )

    @Test
    fun roomMovementStaysInsidePlanAndChangesFingerprint() {
        val original = SceneGeometry.fingerprint(scene)
        val moved = SceneGeometry.moveRoom(scene, room.id, 100.0, 100.0)
        val movedRoom = moved.rooms.first()

        assertTrue(movedRoom.polygon.maxOf { it[0] } <= moved.widthM)
        assertTrue(movedRoom.polygon.maxOf { it[1] } <= moved.depthM)
        assertEquals(6.0, movedRoom.areaM2, 0.0001)
        assertNotEquals(original, SceneGeometry.fingerprint(moved))
    }

    @Test
    fun importedPolygonAreaIsStable() {
        assertEquals(6.0, kotlin.math.abs(SceneGeometry.polygonArea(room.polygon)), 0.0001)
        assertEquals(listOf(2.5, 2.0), SceneGeometry.centroid(room.polygon))
    }
}
