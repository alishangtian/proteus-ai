package com.proteus.ai.api.model

import com.google.gson.annotations.SerializedName

sealed class SseEvent {
    abstract val timestamp: Double?

    data class AgentStart(
        val query: String?,
        override val timestamp: Double? = null
    ) : SseEvent()

    data class AgentStreamThinking(
        val thinking: String?,
        override val timestamp: Double? = null,
        val isDone: Boolean = false
    ) : SseEvent()

    data class ActionStart(
        val action: String?,
        val actionId: String?,
        val input: Any?,
        override val timestamp: Double? = null
    ) : SseEvent()

    data class ActionComplete(
        val action: String?,
        val actionId: String?,
        val result: String?,
        override val timestamp: Double? = null
    ) : SseEvent()

    data class ToolProgress(
        val tool: String?,
        val actionId: String?,
        val status: String?,
        val result: String?,
        override val timestamp: Double? = null
    ) : SseEvent()

    data class Message(
        val content: String?,
        override val timestamp: Double? = null
    ) : SseEvent()

    data class Usage(
        val totalTokens: Int?,
        override val timestamp: Double? = null
    ) : SseEvent()

    data class CompressStart(
        val originalLength: Int?,
        override val timestamp: Double? = null
    ) : SseEvent()

    data class CompressComplete(
        val originalLength: Int?,
        val compressedLength: Int?,
        override val timestamp: Double? = null
    ) : SseEvent()

    data class Unknown(
        val event: String,
        val rawData: String,
        override val timestamp: Double? = null
    ) : SseEvent()
}

/**
 * 后端返回的原始 JSON 结构定义，用于 GSON 解析
 */
data class RawSseData(
    val query: String? = null,
    val thinking: String? = null,
    val action: String? = null,
    @SerializedName("action_id") val actionId: String? = null,
    val input: Any? = null,
    val result: String? = null,
    val tool: String? = null,
    val status: String? = null,
    val content: String? = null,
    val totalTokens: Int? = null,
    val timestamp: Double? = null,
    // 压缩事件相关字段
    val original_length: Int? = null,
    val compressed_length: Int? = null
)
