package com.proteus.ai.api.model

import com.google.gson.annotations.SerializedName

data class AgentInfo(
    @SerializedName("agent_id") val agentId: String = "",
    @SerializedName("chat_id") val chatId: String = "",
    @SerializedName("conversation_id") val conversationId: String = "",
    @SerializedName("status") val status: String = "",
    @SerializedName("user_name") val userName: String = "",
    @SerializedName("model_name") val modelName: String = "",
    @SerializedName("modul") val modul: String = "",
    @SerializedName("task_text") val taskText: String = "",
    @SerializedName("elapsed_time") val elapsedTime: Double = 0.0,
    @SerializedName("current_iteration") val currentIteration: Int = 0,
    @SerializedName("max_iterations") val maxIterations: Int = 0,
    @SerializedName("total_input_tokens") val totalInputTokens: Long = 0,
    @SerializedName("total_output_tokens") val totalOutputTokens: Long = 0,
    @SerializedName("total_tokens") val totalTokens: Long = 0,
    @SerializedName("created_at") val createdAt: String = "",
    @SerializedName("updated_at") val updatedAt: String = ""
)

data class AgentStatusListResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("data") val data: List<AgentInfo> = emptyList(),
    @SerializedName("message") val message: String = ""
)

data class AgentActionResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("message") val message: String = ""
)

data class AgentConversationGroup(
    @SerializedName("conversation_id") val conversationId: String = "",
    @SerializedName("title") val title: String = "",
    @SerializedName("agents") val agents: List<AgentInfo> = emptyList(),
    @SerializedName("has_running") val hasRunning: Boolean = false
)

data class AgentConversationGroupsResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("data") val data: List<AgentConversationGroup> = emptyList(),
    @SerializedName("message") val message: String = ""
)
