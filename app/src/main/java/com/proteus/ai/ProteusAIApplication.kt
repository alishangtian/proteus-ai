package com.proteus.ai

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import com.proteus.ai.api.ApiClient
import com.proteus.ai.storage.TokenManager
import timber.log.Timber

class ProteusAIApplication : Application() {
    lateinit var tokenManager: TokenManager
        private set

    companion object {
        const val CHANNEL_ID = "chat_notifications"
    }

    override fun onCreate() {
        super.onCreate()
        
        // 初始化 Timber 日志
        if (BuildConfig.DEBUG) {
            Timber.plant(Timber.DebugTree())
        }

        tokenManager = TokenManager(this)
        
        // 初始化 ApiClient 以便加载 SSL 证书（针对非 Debug 环境）
        ApiClient.init(this)

        createNotificationChannel()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val name = getString(R.string.channel_name)
            val descriptionText = getString(R.string.channel_description)
            val importance = NotificationManager.IMPORTANCE_DEFAULT
            val channel = NotificationChannel(CHANNEL_ID, name, importance).apply {
                description = descriptionText
            }
            // 注册渠道
            val notificationManager: NotificationManager =
                getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            notificationManager.createNotificationChannel(channel)
        }
    }
}
