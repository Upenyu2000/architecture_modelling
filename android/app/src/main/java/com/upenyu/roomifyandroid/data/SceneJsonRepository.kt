package com.upenyu.roomifyandroid.data

import android.content.Context
import android.net.Uri
import com.upenyu.roomifyandroid.model.SceneGeometry
import com.upenyu.roomifyandroid.model.SceneManifest
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileOutputStream
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

object SceneJsonCodec {
    val json: Json = Json {
        prettyPrint = true
        encodeDefaults = true
        ignoreUnknownKeys = true
        coerceInputValues = true
    }

    fun encode(scene: SceneManifest): String = json.encodeToString(SceneGeometry.validate(scene))

    fun decode(value: String): SceneManifest = SceneGeometry.validate(json.decodeFromString<SceneManifest>(value))
}

class SceneJsonRepository(private val context: Context) {
    private val projectDir = File(context.filesDir, "projects/current")
    private val sceneFile = File(projectDir, "scene.json")

    suspend fun loadCurrent(): SceneManifest? = withContext(Dispatchers.IO) {
        if (!sceneFile.exists()) return@withContext null
        runCatching { SceneJsonCodec.decode(sceneFile.readText(Charsets.UTF_8)) }.getOrNull()
    }

    suspend fun saveCurrent(scene: SceneManifest) = withContext(Dispatchers.IO) {
        projectDir.mkdirs()
        atomicWrite(sceneFile, SceneJsonCodec.encode(scene).toByteArray(Charsets.UTF_8))
    }

    suspend fun importFrom(uri: Uri): SceneManifest = withContext(Dispatchers.IO) {
        val bytes = context.contentResolver.openInputStream(uri)?.use { stream ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            val output = ByteArrayOutputStream()
            var total = 0
            while (true) {
                val read = stream.read(buffer)
                if (read < 0) break
                total += read
                require(total <= MAX_JSON_BYTES) { "The JSON file is larger than 10 MB." }
                output.write(buffer, 0, read)
            }
            output.toByteArray()
        } ?: error("Unable to open the selected JSON file.")
        require(bytes.isNotEmpty()) { "The selected JSON file is empty." }
        val scene = SceneJsonCodec.decode(bytes.toString(Charsets.UTF_8))
        projectDir.mkdirs()
        atomicWrite(sceneFile, SceneJsonCodec.encode(scene).toByteArray(Charsets.UTF_8))
        scene
    }

    suspend fun exportTo(uri: Uri, scene: SceneManifest) = withContext(Dispatchers.IO) {
        val data = SceneJsonCodec.encode(scene).toByteArray(Charsets.UTF_8)
        context.contentResolver.openOutputStream(uri, "wt")?.use { output ->
            output.write(data)
            output.flush()
        } ?: error("Unable to create the JSON file.")
    }

    suspend fun clear() = withContext(Dispatchers.IO) {
        projectDir.deleteRecursively()
    }

    private fun atomicWrite(destination: File, data: ByteArray) {
        destination.parentFile?.mkdirs()
        val temporary = File(destination.parentFile, ".${destination.name}.${UUID.randomUUID()}.tmp")
        try {
            FileOutputStream(temporary).use { output ->
                output.write(data)
                output.flush()
                output.fd.sync()
            }
            runCatching {
                Files.move(
                    temporary.toPath(),
                    destination.toPath(),
                    StandardCopyOption.REPLACE_EXISTING,
                    StandardCopyOption.ATOMIC_MOVE,
                )
            }.getOrElse {
                Files.move(temporary.toPath(), destination.toPath(), StandardCopyOption.REPLACE_EXISTING)
            }
        } finally {
            temporary.delete()
        }
    }

    companion object {
        private const val MAX_JSON_BYTES = 10 * 1024 * 1024
    }
}
