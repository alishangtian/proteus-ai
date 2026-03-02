package com.proteus.ai.api.model

import com.google.gson.annotations.SerializedName

data class StopTaskRequest(
    @SerializedName("conversation_id") val conversationId: String,
    @SerializedName("chat_id") val chatId: String
)
