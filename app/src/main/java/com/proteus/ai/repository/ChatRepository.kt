package com.proteus.ai.repository

import com.google.gson.Gson
import com.proteus.ai.api.ApiClient
import com.proteus.ai.api.model.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import okio.BufferedSource
import timber.log.Timber

class ChatRepository {
    private val gson = Gson()

    suspend fun submitTask(
        token: String,
        query: String,
        chatId: String,
        conversationId: String? = null,
        deepResearch: Boolean = false,
        webSearch: Boolean = false,
        skillCall: Boolean = false
    ): SubmitTaskResponse = withContext(Dispatchers.IO) {
        val request = SubmitTaskRequest(
            query = query,
            modul = "chat",
            chatId = chatId,
            conversationId = conversationId,
            deepResearch = deepResearch,
            webSearch = webSearch,
            skillCall = skillCall
        )
        ApiClient.apiService.submitTask("Bearer $token", request)
    }

    suspend fun stopTask(
        token: String,
        conversationId: String,
        chatId: String
    ): StopTaskResponse = withContext(Dispatchers.IO) {
        val request = StopTaskRequest(conversationId, chatId)
        ApiClient.apiService.stopTask("Bearer $token", request)
    }

    fun streamChatBlocking(token: String, chatId: String): Flow<SseEvent> = flow {
        var retryCount = 0
        val maxRetries = 5
        var success = false

        while (retryCount < maxRetries && !success) {
            val response = try {
                Timber.d("Starting stream request for chatId: $chatId, attempt: ${retryCount + 1}")
                ApiClient.apiService.streamBlocking("Bearer $token", chatId)
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                Timber.e(e, "Stream request exception")
                throw e
            }

            if (response.isSuccessful) {
                success = true
                val body = response.body() ?: throw Exception("Empty response body")
                Timber.d("Stream response successful, starting to parse source")
                // 使用 use 确保 source 关闭，但内部循环逻辑要稳健
                body.source().use { source ->
                    parseSseSource(source, this)
                }
            } else if (response.code() == 404) {
                retryCount++
                Timber.w("Stream not found (404), retrying... ($retryCount/$maxRetries)")
                delay(1500L * retryCount)
            } else {
                val errorBody = response.errorBody()?.string()
                Timber.e("Stream failed: ${response.code()}, body: $errorBody")
                throw Exception("Stream request failed with code: ${response.code()}")
            }
        }

        if (!success) {
            throw Exception("Failed to connect to stream after $maxRetries retries")
        }
    }.flowOn(Dispatchers.IO)

    fun replayStream(token: String, chatId: String): Flow<SseEvent> = flow {
        val response = ApiClient.apiService.replayStream("Bearer $token", chatId)
        if (response.isSuccessful) {
            val body = response.body() ?: return@flow
            body.source().use { source ->
                parseSseSource(source, this)
            }
        }
    }.flowOn(Dispatchers.IO)

    private suspend fun parseSseSource(source: okio.BufferedSource, collector: kotlinx.coroutines.flow.FlowCollector<SseEvent>) {
        var currentEvent = ""
        try {
            // [关键优化] SSE 协议中，一个数据块可能由多行 data: 组成，直到遇到空行 \n\n 才表示一个事件结束
            // 我们需要缓冲 data 部分
            val dataBuffer = StringBuilder()

            while (true) {
                // readUtf8Line 可能会阻塞直到换行符
                val line = source.readUtf8Line() ?: break
                Timber.v("SSE Raw Line: [$line]")
                
                val trimmedLine = line.trim()
                
                when {
                    trimmedLine.startsWith("event:") -> {
                        currentEvent = trimmedLine.substring(6).trim()
                    }
                    trimmedLine.startsWith("data:") -> {
                        val dataPart = trimmedLine.substring(5).trim()
                        if (dataBuffer.isNotEmpty()) dataBuffer.append("\n")
                        dataBuffer.append(dataPart)
                    }
                    trimmedLine.isEmpty() -> {
                        // 遇到空行，分发当前累积的所有 data
                        val finalData = dataBuffer.toString()
                        if (finalData.isNotEmpty()) {
                            val sseEvent = parseSseEvent(currentEvent, finalData)
                            collector.emit(sseEvent)
                            // 关键日志：分发成功
                            Timber.d("SSE Event Dispatched: $currentEvent")
                            dataBuffer.clear()
                            // 原则上 SSE 一个数据包后 currentEvent 会重置，但有些实现会复用，
                            // 这里根据主流做法重置
                            currentEvent = ""
                        }
                    }
                }
            }
        } catch (e: Exception) {
            Timber.e(e, "Error parsing SSE source")
        }
    }

    private fun parseSseEvent(event: String, data: String): SseEvent {
        Timber.d("Parsing SSE: event=[$event], data=[$data]")
        if (data == "[DONE]") return SseEvent.Unknown("done", data)
        return try {
            val raw = gson.fromJson(data, RawSseData::class.java)
            when (event) {
                "agent_start" -> SseEvent.AgentStart(raw.query, raw.timestamp)
                "agent_stream_thinking" -> SseEvent.AgentStreamThinking(
                    thinking = raw.thinking,
                    isDone = raw.isDone || (raw.thinking == "[THINKING_DONE]"),
                    timestamp = raw.timestamp
                )
                "action_start" -> SseEvent.ActionStart(raw.action, raw.actionId, raw.input, raw.timestamp)
                "action_complete" -> SseEvent.ActionComplete(raw.action, raw.actionId, raw.result, raw.isDone, raw.timestamp)
                "tool_progress" -> SseEvent.ToolProgress(raw.tool, raw.actionId, raw.status, raw.timestamp)
                "message", "agent_complete" -> SseEvent.Message(raw.content ?: raw.result, raw.timestamp)
                "usage" -> SseEvent.Usage(raw.totalTokens, raw.timestamp)
                "compress_start" -> SseEvent.CompressStart(raw.originalLength, raw.timestamp)
                "compress_complete" -> SseEvent.CompressComplete(raw.originalLength, raw.compressedLength, raw.timestamp)
                else -> SseEvent.Unknown(event, data, raw.timestamp)
            }
        } catch (e: Exception) {
            Timber.w("GSON parse failed for event [$event], attempting fallback. Error: ${e.message}")
            // 兼容非 JSON 格式所在的 message
            if (event == "message" || event == "agent_complete" || event == "") {
                SseEvent.Message(data, null)
            } else {
                SseEvent.Unknown(event, data)
            }
        }
    }
}
