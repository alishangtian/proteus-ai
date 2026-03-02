package com.proteus.ai.api

import com.proteus.ai.BuildConfig
import com.google.gson.GsonBuilder
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import timber.log.Timber
import java.util.concurrent.TimeUnit

object ApiClient {
    val BASE_URL: String = BuildConfig.BASE_URL

    private val gson = GsonBuilder()
        .setLenient()
        .create()

    private val loggingInterceptor = HttpLoggingInterceptor { message ->
        // 自定义日志逻辑：如果消息太长（很可能是 SSE 数据），则不全量打印，防止内存抖动
        if (message.startsWith("event:") || message.startsWith("data:")) {
            Timber.tag("SSE-Raw").v(message)
        } else {
            Timber.tag("OkHttp").d(message)
        }
    }.apply {
        // 关键优化：针对生产环境或流式请求，Level.BODY 会导致 Interceptor 尝试缓冲整个流
        // 这里设为 Level.HEADERS 以避免流被拦截器阻塞
        level = HttpLoggingInterceptor.Level.HEADERS
    }

    private val okHttpClient = OkHttpClient.Builder()
        .addInterceptor(loggingInterceptor)
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.SECONDS) // SSE 必须保持无限读取
        .writeTimeout(30, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    private val retrofit = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .client(okHttpClient)
        .addConverterFactory(GsonConverterFactory.create(gson))
        .build()

    val apiService: ApiService by lazy {
        retrofit.create(ApiService::class.java)
    }
}
