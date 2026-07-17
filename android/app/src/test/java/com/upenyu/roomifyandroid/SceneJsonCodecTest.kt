package com.upenyu.roomifyandroid

import com.upenyu.roomifyandroid.data.SceneJsonCodec
import com.upenyu.roomifyandroid.model.ProjectMetadata
import com.upenyu.roomifyandroid.model.RoomShape
import com.upenyu.roomifyandroid.model.SceneManifest
import com.upenyu.roomifyandroid.model.WallSegment
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

class SceneJsonCodecTest {
    private fun scene(): SceneManifest = SceneManifest(
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

    @Test
    fun roundTripPreservesAuthoritativeGeometry() {
        val source = scene()
        val encoded = SceneJsonCodec.encode(source)
        val decoded = SceneJsonCodec.decode(encoded)

        assertEquals(source.widthM, decoded.widthM, 0.0001)
        assertEquals(source.rooms.first().polygon, decoded.rooms.first().polygon)
        assertEquals(source.walls.map { it.start to it.end }, decoded.walls.map { it.start to it.end })
        assertTrue(encoded.contains("\"schema_version\""))
        assertTrue(encoded.contains("\"project_id\""))
        assertTrue(encoded.contains("\"fixtures_and_furniture\""))
    }

    @Test
    fun legacyDesktopJsonWithoutSchemaVersionRemainsCompatible() {
        val legacy = SceneJsonCodec.encode(scene()).replace(
            Regex("\\s*\\\"schema_version\\\"\\s*:\\s*\\\"roomify\\.scene\\.v1\\\"\\s*,"),
            "",
        )

        val decoded = SceneJsonCodec.decode(legacy)

        assertEquals(SceneJsonCodec.SUPPORTED_SCHEMA, decoded.schemaVersion)
        assertEquals("test", decoded.projectId)
    }

    @Test
    fun unsupportedDeclaredSchemaIsRejected() {
        val unsupported = SceneJsonCodec.encode(scene()).replace(
            SceneJsonCodec.SUPPORTED_SCHEMA,
            "roomify.scene.v99",
        )

        try {
            SceneJsonCodec.decode(unsupported)
            fail("An unsupported schema version must not be decoded as the current scene format.")
        } catch (error: IllegalArgumentException) {
            assertTrue(error.message.orEmpty().contains("Unsupported scene schema"))
        }
    }
}
