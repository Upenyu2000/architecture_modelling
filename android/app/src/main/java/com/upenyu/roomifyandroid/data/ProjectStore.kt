package com.upenyu.roomifyandroid.data

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageDecoder
import android.net.Uri
import android.os.Build
import java.io.File
import java.io.FileOutputStream
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class ProjectStore(private val context: Context) {
    private val projectDir = File(context.filesDir, "projects/current")
    private val originalFile = File(projectDir, "source-original.img")
    private val sourceFile = File(projectDir, "source-plan.png")

    suspend fun copyAndDecodeSource(uri: Uri, maxDimension: Int = 2400): Bitmap = withContext(Dispatchers.IO) {
        projectDir.mkdirs()
        val temporary = File(projectDir, ".source-${UUID.randomUUID()}.tmp")
        var total = 0L
        try {
            context.contentResolver.openInputStream(uri)?.use { input ->
                FileOutputStream(temporary).use { output ->
                    val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                    while (true) {
                        val read = input.read(buffer)
                        if (read < 0) break
                        total += read
                        require(total <= MAX_IMAGE_BYTES) { "The selected image is larger than 40 MB." }
                        output.write(buffer, 0, read)
                    }
                    output.flush()
                    output.fd.sync()
                }
            } ?: error("Unable to open the selected image.")
            require(total > 0) { "The selected image is empty." }
            val bitmap = decodeFile(temporary, maxDimension)
                ?: error("The selected file is not a readable image.")
            runCatching {
                Files.move(
                    temporary.toPath(),
                    originalFile.toPath(),
                    StandardCopyOption.REPLACE_EXISTING,
                    StandardCopyOption.ATOMIC_MOVE,
                )
            }.getOrElse {
                Files.move(temporary.toPath(), originalFile.toPath(), StandardCopyOption.REPLACE_EXISTING)
            }
            bitmap
        } finally {
            temporary.delete()
        }
    }


    suspend fun saveNormalizedSource(bitmap: Bitmap) = withContext(Dispatchers.IO) {
        projectDir.mkdirs()
        val temporary = File(projectDir, ".normalized-${UUID.randomUUID()}.tmp")
        try {
            FileOutputStream(temporary).use { output ->
                check(bitmap.compress(Bitmap.CompressFormat.PNG, 100, output)) { "Unable to encode the aligned plan image." }
                output.flush()
                output.fd.sync()
            }
            runCatching {
                Files.move(
                    temporary.toPath(),
                    sourceFile.toPath(),
                    StandardCopyOption.REPLACE_EXISTING,
                    StandardCopyOption.ATOMIC_MOVE,
                )
            }.getOrElse {
                Files.move(temporary.toPath(), sourceFile.toPath(), StandardCopyOption.REPLACE_EXISTING)
            }
        } finally {
            temporary.delete()
        }
    }

    suspend fun loadSource(maxDimension: Int = 2400): Bitmap? = withContext(Dispatchers.IO) {
        when {
            sourceFile.exists() -> decodeFile(sourceFile, maxDimension)
            originalFile.exists() -> decodeFile(originalFile, maxDimension)
            else -> null
        }
    }

    suspend fun clearSource() = withContext(Dispatchers.IO) {
        sourceFile.delete()
        originalFile.delete()
    }

    private fun decodeFile(file: File, maxDimension: Int): Bitmap? {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            val source = ImageDecoder.createSource(file)
            return ImageDecoder.decodeBitmap(source) { decoder, info, _ ->
                val largest = maxOf(info.size.width, info.size.height)
                if (largest > maxDimension) {
                    val ratio = maxDimension.toFloat() / largest.toFloat()
                    decoder.setTargetSize(
                        (info.size.width * ratio).toInt().coerceAtLeast(1),
                        (info.size.height * ratio).toInt().coerceAtLeast(1),
                    )
                }
                decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
            }
        }

        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(file.absolutePath, bounds)
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return null
        var sample = 1
        while (maxOf(bounds.outWidth / sample, bounds.outHeight / sample) > maxDimension) sample *= 2
        return BitmapFactory.decodeFile(file.absolutePath, BitmapFactory.Options().apply { inSampleSize = sample })
    }

    companion object {
        private const val MAX_IMAGE_BYTES = 40L * 1024L * 1024L
    }
}
