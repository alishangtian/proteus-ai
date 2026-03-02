package com.proteus.ai.api.model

import com.google.gson.annotations.SerializedName

data class ConversationDetailResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("conversation") val conversation: ConversationDetail
)

data class ConversationDetail(
    @SerializedName("conversation_id") val id: String,
    @SerializedName("title") val title: String?,
    @SerializedName("initial_question") val initialQuestion: String?,
    @SerializedName("created_at") val createdAt: String?,
    @SerializedName("updated_at") val updatedAt: String?,
    @SerializedName("user_name") val userName: String?,
    @SerializedName("first_chat_id") val firstChatId: String?,
    @SerializedName("chat_ids") val chatIds: List<String>?
)
