package com.proteus.ai.api.model

import com.google.gson.annotations.SerializedName

/**
 * 代表一个结构化的 SSE 事件
 */
sealed class SseEvent {
    abstract val timestamp: Double?

    data class AgentStart(
        val query: String?,
        override val timestamp: Double?
    ) : SseEvent()

    data class AgentStreamThinking(
        val thinking: String?,
        override val timestamp: Double?,
        val isDone: Boolean = false
    ) : SseEvent()

    data class ActionStart(
        val action: String?,
        val actionId: String?,
        val input: Any?, // 可以是 String 或 Map
        override val timestamp: Double?
    ) : SseEvent()

    data class ActionComplete(
        val action: String?,
        val actionId: String?,
        val result: String?,
        override val timestamp: Double?
    ) : SseEvent()

    data class ToolProgress(
        val tool: String?,
        val status: String?,
        val result: String?,
        override val timestamp: Double?
    ) : SseEvent()

    data class Message(
        val content: String?,
        override val timestamp: Double?
    ) : SseEvent()

    data class Usage(
        val totalTokens: Int?,
        override val timestamp: Double? = null
    ) : SseEvent()

    data class Unknown(
        val rawEvent: String,
        val rawData: String,
        override val timestamp: Double? = null
    ) : SseEvent()
}

/**
 * 原始 SSE 解析辅助模型
 */
data class RawSseData(
    @SerializedName("query") val query: String? = null,
    @SerializedName("thinking") val thinking: String? = null,
    @SerializedName("action") val action: String? = null,
    @SerializedName("action_id") val actionId: String? = null,
    @SerializedName("input") val input: Any? = null,
    @SerializedName("result") val result: String? = null,
    @SerializedName("tool") val tool: String? = null,
    @SerializedName("status") val status: String? = null,
    @SerializedName("content") val content: String? = null,
    @SerializedName("total_tokens") val totalTokens: Int? = null,
    @SerializedName("timestamp") val timestamp: Double? = null
)
