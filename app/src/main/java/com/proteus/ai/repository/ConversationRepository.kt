package com.proteus.ai.repository

import com.proteus.ai.api.ApiClient
import com.proteus.ai.api.model.Conversation
import com.proteus.ai.api.model.ConversationDetail
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import timber.log.Timber
import java.io.IOException

class ConversationRepository {

    companion object {
        private const val MAX_RETRIES = 3
        private const val RETRY_DELAY_MS = 1000L
    }

    suspend fun getConversations(token: String): List<Conversation> =
        withRetry(MAX_RETRIES) {
            withContext(Dispatchers.IO) {
                val response = ApiClient.apiService.getConversations("Bearer $token")
                if (response.success) response.conversations else emptyList()
            }
        }

    suspend fun deleteConversation(token: String, conversationId: String): Boolean =
        withContext(Dispatchers.IO) {
            try {
                val response = ApiClient.apiService.deleteConversation("Bearer $token", conversationId)
                response.success
            } catch (e: Exception) {
                Timber.e(e, "Failed to delete conversation: $conversationId")
                false
            }
        }

    suspend fun getConversationDetail(
        token: String,
        conversationId: String
    ): ConversationDetail? = withContext(Dispatchers.IO) {
        try {
            withRetry(MAX_RETRIES) {
                val response = ApiClient.apiService.getConversationDetail(
                    "Bearer $token",
                    conversationId
                )
                if (response.success) response.conversation else null
            }
        } catch (e: Exception) {
            Timber.e(e, "Failed to get conversation detail: $conversationId")
            null
        }
    }

    private suspend fun <T> withRetry(
        maxRetries: Int,
        block: suspend () -> T
    ): T {
        var lastException: Exception? = null
        repeat(maxRetries) { attempt ->
            try {
                return block()
            } catch (e: IOException) {
                lastException = e
                Timber.w(e, "Network request failed (attempt ${attempt + 1}/$maxRetries)")
                if (attempt < maxRetries - 1) {
                    delay(RETRY_DELAY_MS * (attempt + 1)) // 指数退避
                }
            } catch (e: Exception) {
                Timber.e(e, "Unexpected error during request")
                throw e
            }
        }
        throw lastException ?: IOException("Request failed after $maxRetries attempts")
    }
}
