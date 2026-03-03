package com.proteus.ai

import android.app.Application
import com.proteus.ai.api.ApiClient
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
        
        // 初始化 ApiClient 以便加载 SSL 证书（针对非 Debug 环境）
        ApiClient.init(this)
    }
}
