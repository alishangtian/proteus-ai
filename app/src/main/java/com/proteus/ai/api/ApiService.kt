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

    // ==================== 知识库 ====================

    @GET("knowledge_base/list")
    suspend fun getKnowledgeBaseList(
        @Header("Authorization") authorization: String
    ): KnowledgeBaseListResponse

    @GET("knowledge_base/item/{item_id}")
    suspend fun getKnowledgeBaseItem(
        @Header("Authorization") authorization: String,
        @Path("item_id") itemId: String
    ): KnowledgeBaseItemResponse

    @POST("knowledge_base/save")
    suspend fun saveKnowledgeBaseItem(
        @Header("Authorization") authorization: String,
        @Body request: KnowledgeBaseSaveRequest
    ): KnowledgeBaseSaveResponse

    @PUT("knowledge_base/item/{item_id}")
    suspend fun updateKnowledgeBaseItem(
        @Header("Authorization") authorization: String,
        @Path("item_id") itemId: String,
        @Body request: KnowledgeBaseUpdateRequest
    ): KnowledgeBaseSaveResponse

    @DELETE("knowledge_base/item/{item_id}")
    suspend fun deleteKnowledgeBaseItem(
        @Header("Authorization") authorization: String,
        @Path("item_id") itemId: String
    ): SimpleResponse

    // ==================== Agent 监控 ====================

    @GET("agents/status")
    suspend fun getAgentsStatus(
        @Header("Authorization") authorization: String,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 20,
        @Query("status") status: String? = null
    ): AgentStatusListResponse

    @GET("agents/by_conversation")
    suspend fun getAgentsByConversation(
        @Header("Authorization") authorization: String,
        @Query("status") status: String? = null
    ): AgentConversationGroupsResponse

    @POST("agents/{agent_id}/stop")
    suspend fun stopAgent(
        @Header("Authorization") authorization: String,
        @Path("agent_id") agentId: String
    ): AgentActionResponse

    @DELETE("agents/{agent_id}")
    suspend fun deleteAgent(
        @Header("Authorization") authorization: String,
        @Path("agent_id") agentId: String
    ): AgentActionResponse
}
