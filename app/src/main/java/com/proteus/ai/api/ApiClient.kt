package com.proteus.ai.api

import android.content.Context
import com.proteus.ai.storage.TokenManager
import com.google.gson.GsonBuilder
import okhttp3.ConnectionPool
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import timber.log.Timber
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

object ApiClient {
    private val _baseUrl = MutableStateFlow(TokenManager.DEFAULT_SERVER_URL)
    val baseUrlFlow: StateFlow<String> = _baseUrl.asStateFlow()

    // 对于正规证书，不再需要 appContext 来加载本地文件
    fun init(context: Context) {
        // 仅保留结构，逻辑恢复默认
        okHttpClient = createOkHttpClient()
        retrofit = createRetrofit()
    }

    fun setBaseUrl(url: String) {
        val normalizedUrl = if (!url.endsWith("/")) "$url/" else url
        if (_baseUrl.value != normalizedUrl) {
            _baseUrl.value = normalizedUrl
            okHttpClient = createOkHttpClient()
            retrofit = createRetrofit()
            Timber.d("BASE_URL updated to: $normalizedUrl")
        }
    }

    val BASE_URL: String get() = _baseUrl.value

    private val gson = GsonBuilder().setLenient().create()

    private val loggingInterceptor = HttpLoggingInterceptor { message ->
        if (message.startsWith("event:") || message.startsWith("data:")) {
            Timber.tag("SSE-Raw").v(message)
        } else {
            Timber.tag("OkHttp").d(message)
        }
    }.apply { level = HttpLoggingInterceptor.Level.HEADERS }

    private var okHttpClient: OkHttpClient = createOkHttpClient()
    private var retrofit: Retrofit = createRetrofit()

    private fun createOkHttpClient(): OkHttpClient {
        return OkHttpClient.Builder()
            .addInterceptor(loggingInterceptor)
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(10, TimeUnit.MINUTES) // 保持长连接用于 SSE
            .writeTimeout(30, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .connectionPool(ConnectionPool(5, 60, TimeUnit.SECONDS)) // 60s < 服务端 keep-alive 75s，避免使用过期连接
            // 移除自定义 TrustManager 和 HostnameVerifier，回归系统安全标准
            .build()
    }

    private fun createRetrofit(): Retrofit = Retrofit.Builder()
        .baseUrl(_baseUrl.value)
        .client(okHttpClient)
        .addConverterFactory(GsonConverterFactory.create(gson))
        .build()

    val apiService: ApiService get() = retrofit.create(ApiService::class.java)
}
