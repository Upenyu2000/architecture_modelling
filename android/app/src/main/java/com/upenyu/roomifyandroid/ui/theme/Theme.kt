package com.upenyu.roomifyandroid.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightScheme = lightColorScheme(
    primary = Color(0xFFF97316),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFFFEDD5),
    onPrimaryContainer = Color(0xFF7C2D12),
    secondary = Color(0xFF3B82F6),
    background = Color(0xFFFDFBF7),
    surface = Color.White,
    surfaceVariant = Color(0xFFF4F4F5),
    outline = Color(0xFFD4D4D8),
    error = Color(0xFFB91C1C),
)

private val DarkScheme = darkColorScheme(
    primary = Color(0xFFFB923C),
    secondary = Color(0xFF60A5FA),
    background = Color(0xFF111113),
    surface = Color(0xFF18181B),
    surfaceVariant = Color(0xFF27272A),
    outline = Color(0xFF52525B),
)

@Composable
fun DreamHomeTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) DarkScheme else LightScheme,
        content = content,
    )
}
