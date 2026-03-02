package com.proteus.ai

import android.app.Application
import com.proteus.ai.storage.TokenManager
import timber.log.Timber

class ProteusAIApplication : Application() {
    lateinit var tokenManager: TokenManager
        private set

    override fun onCreate() {
        super.onCreate()
        
        // 初始化 Timber 日志
        if (BuildConfig.DEBUG) {
            Timber.plant(Timber.DebugTree())
        }

        tokenManager = TokenManager(this)
    }
}
