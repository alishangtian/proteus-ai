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
        @SerializedName("is_done") val isDone: Boolean = false,
        override val timestamp: Double? = null
    ) : SseEvent()

    data class ActionStart(
        val action: String?,
        @SerializedName("action_id") val actionId: String?,
        val input: Any?,
        override val timestamp: Double? = null
    ) : SseEvent()

    data class ToolProgress(
        val tool: String?,
        @SerializedName("action_id") val actionId: String?,
        val status: String?,
        override val timestamp: Double? = null
    ) : SseEvent()

    data class ActionComplete(
        val action: String?,
        @SerializedName("action_id") val actionId: String?,
        val result: String?,
        @SerializedName("is_done") val isDone: Boolean = false,
        override val timestamp: Double? = null
    ) : SseEvent()

    data class Message(
        val content: String?,
        override val timestamp: Double? = null
    ) : SseEvent()

    data class CompressStart(
        @SerializedName("original_length") val originalLength: Int?,
        override val timestamp: Double? = null
    ) : SseEvent()

    data class CompressComplete(
        @SerializedName("original_length") val originalLength: Int?,
        @SerializedName("compressed_length") val compressedLength: Int?,
        override val timestamp: Double? = null
    ) : SseEvent()

    data class Usage(
        @SerializedName("total_tokens") val totalTokens: Int?,
        override val timestamp: Double? = null
    ) : SseEvent()

    data class Unknown(
        val event: String,
        val rawData: String,
        override val timestamp: Double? = null
    ) : SseEvent()
}

data class RawSseData(
    val query: String? = null,
    val thinking: String? = null,
    val action: String? = null,
    @SerializedName("action_id") val actionId: String? = null,
    val tool: String? = null,
    val input: Any? = null,
    val status: String? = null,
    val result: String? = null,
    val content: String? = null,
    @SerializedName("is_done") val isDone: Boolean = false,
    @SerializedName("original_length") val originalLength: Int? = null,
    @SerializedName("compressed_length") val compressedLength: Int? = null,
    @SerializedName("total_tokens") val totalTokens: Int? = null,
    val timestamp: Double? = null
)
