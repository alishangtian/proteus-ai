package com.proteus.ai.api.model

import com.google.gson.annotations.SerializedName

data class SubmitTaskRequest(
    @SerializedName("query") val query: String,
    @SerializedName("modul") val modul: String,
    @SerializedName("chat_id") val chatId: String? = null,
    @SerializedName("model_name") val modelName: String? = "deepseek-reasoner",
    @SerializedName("itecount") val itecount: Int = 5,
    @SerializedName("agentid") val agentId: String? = null,
    @SerializedName("team_name") val teamName: String? = null,
    @SerializedName("conversation_id") val conversationId: String? = null,
    @SerializedName("conversation_round") val conversationRound: Int = 5,
    @SerializedName("file_ids") val fileIds: List<String>? = null,
    @SerializedName("tool_memory_enabled") val toolMemoryEnabled: Boolean = false,
    @SerializedName("sop_memory_enabled") val sopMemoryEnabled: Boolean = false,
    @SerializedName("enable_tools") val enableTools: Boolean = false,
    @SerializedName("tool_choices") val toolChoices: List<String>? = null,
    @SerializedName("selected_skills") val selectedSkills: List<String>? = null,
    // 模式参数
    @SerializedName("deep_research") val deepResearch: Boolean = false,
    @SerializedName("web_search") val webSearch: Boolean = false,
    @SerializedName("skill_call") val skillCall: Boolean = false
)

data class SubmitTaskResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("message") val message: String,
    @SerializedName("task_id") val taskId: String
)
