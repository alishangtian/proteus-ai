package com.proteus.ai.api

import com.proteus.ai.api.model.*
import retrofit2.http.*

interface ApiService {

    @GET("conversations")
    suspend fun getConversations(
        @Header("Authorization") authorization: String,
        @Query("limit") limit: Int = 50
    ): ConversationsResponse

    @DELETE("conversations/{conversation_id}")
    suspend fun deleteConversation(
        @Header("Authorization") authorization: String,
        @Path("conversation_id") conversationId: String
    ): SimpleResponse

    @GET("models")
    suspend fun getModels(): ModelsResponse

    @POST("submit_task")
    suspend fun submitTask(
        @Header("Authorization") authorization: String,
        @Body request: SubmitTaskRequest
    ): SubmitTaskResponse

    @GET("conversations/{conversation_id}")
    suspend fun getConversationDetail(
        @Header("Authorization") authorization: String,
        @Path("conversation_id") conversationId: String
    ): ConversationDetailResponse

    /** 停止任务 */
    @POST("stop")
    suspend fun stopTask(
        @Header("Authorization") authorization: String,
        @Body request: StopTaskRequest
    ): StopTaskResponse
}
