package com.upenyu.roomifyandroid.analysis

import android.graphics.Bitmap
import com.upenyu.roomifyandroid.model.SceneManifest

interface FloorPlanAnalyzer {
    suspend fun analyze(bitmap: Bitmap, options: AnalysisOptions): AnalysisResult
}

data class AnalysisOptions(
    val projectId: String = "android-project",
    val planWidthM: Double = 14.0,
    val wallHeightM: Double = 2.8,
    val wallThicknessM: Double = 0.16,
    val minimumWallLengthM: Double = 0.6,
    val maximumAnalysisDimensionPx: Int = 1400,
)

data class AnalysisResult(
    val scene: SceneManifest,
    val normalizedBitmap: Bitmap,
    val warnings: List<String>,
)
