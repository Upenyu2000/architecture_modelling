package com.upenyu.roomifyandroid

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.lifecycle.viewmodel.compose.viewModel
import com.upenyu.roomifyandroid.ui.RoomifyApp
import com.upenyu.roomifyandroid.ui.RoomifyViewModel
import com.upenyu.roomifyandroid.ui.theme.DreamHomeTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            DreamHomeTheme {
                val roomifyViewModel: RoomifyViewModel = viewModel()
                RoomifyApp(roomifyViewModel)
            }
        }
    }
}
