package com.proteus.ai.repository

import com.google.gson.Gson
import com.proteus.ai.api.ApiClient
import com.proteus.ai.api.model.*
import kotlinx.coroutines.*
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.flowOn
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
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

    fun streamChatBlocking(token: String, chatId: String): Flow<SseEvent> = callbackFlow {
        val url = "${ApiClient.WS_BASE_URL}stream/blocking/$chatId"
        Timber.d("WebSocket stream connecting: $url")
        val request = Request.Builder()
            .url(url)
            .addHeader("Authorization", "Bearer $token")
            .build()

        val ws = ApiClient.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Timber.d("WebSocket stream opened for chatId: $chatId")
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                Timber.v("WebSocket message: $text")
                try {
                    val event = parseWsMessage(text)
                    trySend(event)
                } catch (e: Exception) {
                    Timber.e(e, "Error processing WebSocket stream message")
                }
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                Timber.d("WebSocket stream closing: $code $reason")
                webSocket.close(1000, null)
                channel.close()
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Timber.d("WebSocket stream closed: $code $reason")
                channel.close()
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Timber.e(t, "WebSocket stream failure")
                channel.close(t)
            }
        })

        awaitClose {
            Timber.d("WebSocket stream flow cancelled, closing WebSocket")
            ws.close(1000, "Flow cancelled")
        }
    }.flowOn(Dispatchers.IO)

    fun replayStream(token: String, chatId: String): Flow<SseEvent> = callbackFlow {
        val url = "${ApiClient.WS_BASE_URL}replay/stream/$chatId"
        Timber.d("WebSocket replay connecting: $url")
        val request = Request.Builder()
            .url(url)
            .addHeader("Authorization", "Bearer $token")
            .build()

        val ws = ApiClient.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Timber.d("WebSocket replay opened for chatId: $chatId")
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                Timber.v("WebSocket replay message: $text")
                try {
                    val event = parseWsMessage(text)
                    trySend(event)
                } catch (e: Exception) {
                    Timber.e(e, "Error processing WebSocket replay message")
                }
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                Timber.d("WebSocket replay closing: $code $reason")
                webSocket.close(1000, null)
                channel.close()
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Timber.d("WebSocket replay closed: $code $reason")
                channel.close()
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Timber.e(t, "WebSocket replay failure")
                channel.close(t)
            }
        })

        awaitClose {
            Timber.d("WebSocket replay flow cancelled, closing WebSocket")
            ws.close(1000, "Flow cancelled")
        }
    }.flowOn(Dispatchers.IO)

    private fun parseWsMessage(text: String): SseEvent {
        return try {
            val raw = gson.fromJson(text, RawWsMessage::class.java)
            val event = raw.event ?: ""
            val data = raw.data ?: ""
            Timber.d("WebSocket Event: event=[$event]")
            parseSseEvent(event, data)
        } catch (e: Exception) {
            val truncated = if (text.length > 200) text.take(200) + "..." else text
            Timber.e(e, "Failed to parse WebSocket message: $truncated")
            SseEvent.Unknown("", text)
        }
    }

    private fun parseSseEvent(event: String, data: String): SseEvent {
        Timber.d("Parsing event=[$event], data=[$data]")
        if (data == "[DONE]") return SseEvent.Unknown("done", data)
        if (event == "complete") return SseEvent.Complete(extractTextPayload(data))
        if (event == "error") return SseEvent.Error(extractTextPayload(data))
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
                "agent_error" -> SseEvent.Error(raw.error ?: raw.content ?: raw.result, raw.timestamp)
                "usage" -> SseEvent.Usage(raw.totalTokens, raw.timestamp)
                "compress_start" -> SseEvent.CompressStart(raw.originalLength, raw.timestamp)
                "compress_complete" -> SseEvent.CompressComplete(raw.originalLength, raw.compressedLength, raw.timestamp)
                else -> SseEvent.Unknown(event, data, raw.timestamp)
            }
        } catch (e: Exception) {
            Timber.w("GSON parse failed for event [$event], attempting fallback. Error: ${e.message}")
            SseEvent.Unknown(event, data)
        }
    }

    private fun extractTextPayload(data: String): String {
        // "complete"/"error" may arrive either as a JSON string literal or as plain text.
        val parsedString = runCatching { gson.fromJson(data, String::class.java) }.getOrNull()
        if (parsedString != null) return parsedString
        return data.trim('"')
    }
}
