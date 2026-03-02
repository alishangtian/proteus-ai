package com.proteus.ai.api.model

import com.google.gson.annotations.SerializedName

data class Conversation(
    @SerializedName("conversation_id") val conversationId: String? = null,
    @SerializedName("title") val title: String? = null,
    @SerializedName("initial_question") val initialQuestion: String? = null,
    @SerializedName("created_at") val createdAt: String? = null,
    @SerializedName("updated_at") val updatedAt: String? = null,
    @SerializedName("user_name") val userName: String? = null,
    @SerializedName("modul") val module: String? = null,
    @SerializedName("first_chat_id") val firstChatId: String? = null,
    @SerializedName("chat_count") val chatCount: Int = 0
) {
    // 兼容之前的代码使用 id
    val id: String? get() = conversationId
}

data class ConversationsResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("conversations") val conversations: List<Conversation>
)