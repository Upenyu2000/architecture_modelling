package com.upenyu.roomifyandroid

import com.upenyu.roomifyandroid.data.SceneJsonCodec
import com.upenyu.roomifyandroid.model.ProjectMetadata
import com.upenyu.roomifyandroid.model.RoomShape
import com.upenyu.roomifyandroid.model.SceneManifest
import com.upenyu.roomifyandroid.model.WallSegment
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SceneJsonCodecTest {
    @Test
    fun roundTripPreservesAuthoritativeGeometry() {
        val scene = SceneManifest(
            projectId = "test",
            widthM = 6.0,
            depthM = 4.0,
            wallHeightM = 2.8,
            walls = listOf(
                WallSegment("w1", listOf(0.0, 0.0), listOf(6.0, 0.0), 2.8, wallType = "exterior"),
                WallSegment("w2", listOf(6.0, 0.0), listOf(6.0, 4.0), 2.8, wallType = "exterior"),
                WallSegment("w3", listOf(6.0, 4.0), listOf(0.0, 4.0), 2.8, wallType = "exterior"),
                WallSegment("w4", listOf(0.0, 4.0), listOf(0.0, 0.0), 2.8, wallType = "exterior"),
            ),
            rooms = listOf(
                RoomShape(
                    id = "room-1",
                    name = "Room 1",
                    polygon = listOf(listOf(0.0, 0.0), listOf(6.0, 0.0), listOf(6.0, 4.0), listOf(0.0, 4.0)),
                    areaM2 = 24.0,
                    centroid = listOf(3.0, 2.0),
                ),
            ),
            projectMetadata = ProjectMetadata(detectedRooms = 1, structuralConfidence = 1.0),
        )

        val encoded = SceneJsonCodec.encode(scene)
        val decoded = SceneJsonCodec.decode(encoded)

        assertEquals(scene.widthM, decoded.widthM, 0.0001)
        assertEquals(scene.rooms.first().polygon, decoded.rooms.first().polygon)
        assertEquals(scene.walls.map { it.start to it.end }, decoded.walls.map { it.start to it.end })
        assertTrue(encoded.contains("\"project_id\""))
        assertTrue(encoded.contains("\"fixtures_and_furniture\""))
    }
}
