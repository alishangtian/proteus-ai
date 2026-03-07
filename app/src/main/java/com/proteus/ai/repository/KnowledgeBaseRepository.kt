package com.proteus.ai.repository

import com.proteus.ai.api.ApiClient
import com.proteus.ai.api.model.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class KnowledgeBaseRepository {

    suspend fun getList(token: String): List<KnowledgeBaseItem> = withContext(Dispatchers.IO) {
        val response = ApiClient.apiService.getKnowledgeBaseList("Bearer $token")
        if (response.success) response.items else emptyList()
    }

    suspend fun getItem(token: String, itemId: String): KnowledgeBaseItem? = withContext(Dispatchers.IO) {
        val response = ApiClient.apiService.getKnowledgeBaseItem("Bearer $token", itemId)
        if (response.success) response.item else null
    }

    suspend fun saveItem(token: String, content: String): KnowledgeBaseSaveResponse = withContext(Dispatchers.IO) {
        ApiClient.apiService.saveKnowledgeBaseItem("Bearer $token", KnowledgeBaseSaveRequest(content))
    }

    suspend fun updateItem(token: String, itemId: String, content: String, title: String? = null): KnowledgeBaseSaveResponse = withContext(Dispatchers.IO) {
        ApiClient.apiService.updateKnowledgeBaseItem(
            "Bearer $token",
            itemId,
            KnowledgeBaseUpdateRequest(content, title)
        )
    }

    suspend fun deleteItem(token: String, itemId: String): Boolean = withContext(Dispatchers.IO) {
        val response = ApiClient.apiService.deleteKnowledgeBaseItem("Bearer $token", itemId)
        response.success
    }
}
