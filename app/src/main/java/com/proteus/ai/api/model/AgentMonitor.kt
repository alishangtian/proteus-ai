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
