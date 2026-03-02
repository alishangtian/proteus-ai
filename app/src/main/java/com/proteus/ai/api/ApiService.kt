package com.proteus.ai.api

import com.proteus.ai.api.model.*
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.*

interface ApiService {

    @GET("conversations")
    suspend fun getConversations(
        @Header("Authorization") authorization: String,
        @Query("limit") limit: Int = 50
    ): ConversationsResponse

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

    /** SSE 流式回放 */
    @Streaming
    @GET("replay/stream/{chat_id}")
    suspend fun replayStream(
        @Header("Authorization") authorization: String,
        @Path("chat_id") chatId: String
    ): Response<ResponseBody>

    /** 阻塞式 SSE 流，实时推送 AI 回复 */
    @Streaming
    @GET("stream/blocking/{chat_id}")
    suspend fun streamBlocking(
        @Header("Authorization") authorization: String,
        @Path("chat_id") chatId: String
    ): Response<ResponseBody>

    /** 停止任务 */
    @POST("stop")
    suspend fun stopTask(
        @Header("Authorization") authorization: String,
        @Body request: StopTaskRequest
    ): StopTaskResponse
}
