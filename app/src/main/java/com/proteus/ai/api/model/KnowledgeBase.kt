package com.proteus.ai.api.model

import com.google.gson.annotations.SerializedName

data class KnowledgeBaseItem(
    @SerializedName("id") val id: String = "",
    @SerializedName("title") val title: String = "",
    @SerializedName("author") val author: String = "",
    @SerializedName("timestamp") val timestamp: String = "",
    @SerializedName("updated_at") val updatedAt: String = "",
    @SerializedName("likes") val likes: Int = 0,
    @SerializedName("dislikes") val dislikes: Int = 0,
    @SerializedName("content") val content: String? = null
)

data class KnowledgeBaseListResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("knowledge_base_items") val items: List<KnowledgeBaseItem> = emptyList()
)

data class KnowledgeBaseItemResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("knowledge_base_item") val item: KnowledgeBaseItem? = null
)

data class KnowledgeBaseSaveRequest(
    @SerializedName("content") val content: String
)

data class KnowledgeBaseUpdateRequest(
    @SerializedName("content") val content: String,
    @SerializedName("title") val title: String? = null
)

data class KnowledgeBaseSaveResponse(
    @SerializedName("success") val success: Boolean,
    @SerializedName("message") val message: String = "",
    @SerializedName("item_id") val itemId: String = ""
)
