package com.proteus.ai.ui.viewmodel

import androidx.lifecycle.*
import androidx.lifecycle.ViewModelProvider.AndroidViewModelFactory.Companion.APPLICATION_KEY
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.proteus.ai.ProteusAIApplication
import com.proteus.ai.api.ApiClient
import com.proteus.ai.api.model.Conversation
import com.proteus.ai.api.model.SseEvent
import com.proteus.ai.repository.ChatRepository
import com.proteus.ai.repository.ConversationRepository
import com.proteus.ai.storage.TokenManager
import com.proteus.ai.ui.components.Message
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import timber.log.Timber
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import kotlin.random.Random

sealed class UiState {
    data object Loading : UiState()
    data object Success : UiState()
    data class Error(val message: String, val retryable: Boolean = true) : UiState()
}

class MainViewModel(
    private val tokenManager: TokenManager,
    private val conversationRepository: ConversationRepository,
    private val chatRepository: ChatRepository
) : ViewModel() {

    private val _tokenState = MutableStateFlow<String?>(null)
    val tokenState: StateFlow<String?> = _tokenState.asStateFlow()

    private val _serverUrlState = MutableStateFlow<String?>(null)
    val serverUrlState: StateFlow<String?> = _serverUrlState.asStateFlow()

    private val _showTokenDialog = MutableStateFlow(false)
    val showTokenDialog: StateFlow<Boolean> = _showTokenDialog.asStateFlow()

    private val _conversations = MutableStateFlow<List<Conversation>>(emptyList())
    val conversations: StateFlow<List<Conversation>> = _conversations.asStateFlow()

    private val _loading = MutableStateFlow(false)
    val loading: StateFlow<Boolean> = _loading.asStateFlow()

    private val _uiState = MutableStateFlow<UiState>(UiState.Success)
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    private val _messages = MutableStateFlow<List<Message>>(emptyList())
    val messages: StateFlow<List<Message>> = _messages.asStateFlow()

    private val _selectedConversationId = MutableStateFlow<String?>(null)
    val selectedConversationId: StateFlow<String?> = _selectedConversationId.asStateFlow()

    private val _isStreaming = MutableStateFlow(false)
    val isStreaming: StateFlow<Boolean> = _isStreaming.asStateFlow()

    private val _deepResearch = MutableStateFlow(false)
    val deepResearch: StateFlow<Boolean> = _deepResearch.asStateFlow()

    private val _webSearch = MutableStateFlow(false)
    val webSearch: StateFlow<Boolean> = _webSearch.asStateFlow()

    private val _skillCall = MutableStateFlow(false)
    val skillCall: StateFlow<Boolean> = _skillCall.asStateFlow()

    // 当前正在进行的任务信息，用于停止功能
    private val _currentChatId = MutableStateFlow<String?>(null)
    val currentChatId: StateFlow<String?> = _currentChatId.asStateFlow()

    private var streamingJob: Job? = null
    private val timeFormatter = DateTimeFormatter.ofPattern("HH:mm")

    init {
        viewModelScope.launch {
            tokenManager.tokenFlow().collect { token ->
                _tokenState.value = token
                if (token != null) {
                    try {
                        _conversations.value = conversationRepository.getConversations(token)
                    } catch (e: Exception) {
                        Timber.e(e)
                    }
                } else {
                    _showTokenDialog.value = true
                }
            }
        }
        viewModelScope.launch {
            tokenManager.serverUrlFlow().collect { url ->
                // 如果没有设置服务器地址，使用默认本机地址
                val effectiveUrl = url ?: TokenManager.DEFAULT_SERVER_URL
                _serverUrlState.value = effectiveUrl
                ApiClient.setBaseUrl(effectiveUrl)
            }
        }
    }

    private fun generateConversationId(): String {
        val timestamp = System.currentTimeMillis()
        val randomStr = StringBuilder()
        val charPool = "abcdefghijklmnopqrstuvwxyz0123456789"
        repeat(9) { randomStr.append(charPool[Random.nextInt(charPool.length)]) }
        return "$timestamp-$randomStr"
    }

    fun loadConversations(token: String) {
        viewModelScope.launch {
            _loading.value = true
            try {
                _conversations.value = conversationRepository.getConversations(token)
                _uiState.value = UiState.Success
            } catch (e: Exception) {
                Timber.e(e, "Failed to load conversations")
                _uiState.value = UiState.Error("获取会话列表失败: ${e.message}")
            } finally {
                _loading.value = false
            }
        }
    }

    fun deleteConversation(conversation: Conversation) {
        val token = _tokenState.value ?: return
        val cid = conversation.conversationId ?: return

        viewModelScope.launch {
            _loading.value = true
            try {
                val success = conversationRepository.deleteConversation(token, cid)
                if (success) {
                    _conversations.value = _conversations.value.filter { it.conversationId != cid }
                    if (_selectedConversationId.value == cid) {
                        newConversation()
                    }
                    _uiState.value = UiState.Success
                } else {
                    _uiState.value = UiState.Error("删除会话失败")
                }
            } catch (e: Exception) {
                Timber.e(e, "Failed to delete conversation")
                _uiState.value = UiState.Error("删除失败: ${e.message}")
            } finally {
                _loading.value = false
            }
        }
    }

    fun selectConversation(conversation: Conversation) {
        val token = _tokenState.value ?: return
        val cid = conversation.conversationId ?: return
        if (_selectedConversationId.value == cid && _messages.value.isNotEmpty()) return
        
        streamingJob?.cancel()
        _selectedConversationId.value = cid
        _messages.value = emptyList()
        loadConversationHistory(token, cid)
    }

    fun newConversation() {
        streamingJob?.cancel()
        _selectedConversationId.value = null
        _messages.value = emptyList()
        _currentChatId.value = null
    }

    private fun loadConversationHistory(token: String, conversationId: String) {
        streamingJob = viewModelScope.launch {
            _loading.value = true
            try {
                val detail = conversationRepository.getConversationDetail(token, conversationId)
                val chatIds = detail?.chatIds ?: emptyList()
                _loading.value = false
                
                chatIds.forEach { chatId ->
                    val msgId = "replay_$chatId"
                    try {
                        chatRepository.replayStream(token, chatId).collect { event ->
                            updateMessageWithEvent(msgId, event)
                        }
                    } catch (e: Exception) {
                        if (e is kotlinx.coroutines.CancellationException) throw e
                        Timber.e(e, "Replay failed for chatId: $chatId, continuing with next")
                    }
                }
                _uiState.value = UiState.Success
            } catch (e: Exception) {
                Timber.e(e, "History load failed")
                _uiState.value = UiState.Error("加载历史记录失败: ${e.message}")
            } finally {
                _loading.value = false
            }
        }
    }

    fun sendMessage(content: String) {
        val token = _tokenState.value ?: return
        _uiState.value = UiState.Success

        val conversationId = _selectedConversationId.value ?: generateConversationId()
        val chatId = "chat-${System.currentTimeMillis()}"
        _selectedConversationId.value = conversationId
        _currentChatId.value = chatId

        // 1. 添加用户消息
        val userMsg = Message(id = "u_${System.currentTimeMillis()}", isUser = true, content = content, timestamp = currentTime())
        
        // 2. 立即添加 AI 消息占位符
        val aiMsgId = "ai_$chatId"
        val aiPlaceholder = Message(id = aiMsgId, isUser = false, timestamp = currentTime(), events = emptyList())
        
        _messages.value = _messages.value + userMsg + aiPlaceholder

        streamingJob = viewModelScope.launch {
            try {
                val response = chatRepository.submitTask(token, content, chatId, conversationId, 
                    _deepResearch.value, _webSearch.value, _skillCall.value)
                
                if (!response.success) {
                    _uiState.value = UiState.Error(response.message ?: "提交任务失败")
                    _messages.value = _messages.value.filter { it.id != aiMsgId }
                    _currentChatId.value = null
                    return@launch
                }

                _isStreaming.value = true
                try {
                    chatRepository.streamChatBlocking(token, chatId).collect { event ->
                        updateMessageWithEvent(aiMsgId, event)
                    }
                } catch (e: Exception) {
                    Timber.e(e, "Streaming content failed")
                    if (e !is kotlinx.coroutines.CancellationException) {
                        _uiState.value = UiState.Error("流式回复中断: ${e.message}")
                    }
                } finally {
                    _isStreaming.value = false
                    _currentChatId.value = null
                    launch { 
                        try { _conversations.value = conversationRepository.getConversations(token) } catch(e:Exception){}
                    }
                }
            } catch (e: Exception) {
                Timber.e(e, "Send message request failed")
                _uiState.value = UiState.Error("发送失败: ${e.message}")
                _messages.value = _messages.value.filter { it.id != aiMsgId }
                _isStreaming.value = false
                _currentChatId.value = null
            }
        }
    }

    fun stopTask() {
        val token = _tokenState.value ?: return
        val conversationId = _selectedConversationId.value ?: return
        val chatId = _currentChatId.value ?: return

        viewModelScope.launch {
            try {
                streamingJob?.cancel()
                val response = chatRepository.stopTask(token, conversationId, chatId)
                if (response.success) {
                    _isStreaming.value = false
                    _currentChatId.value = null
                    Timber.d("Task stopped successfully")
                } else {
                    Timber.w("Stop task failed: ${response.message}")
                }
            } catch (e: Exception) {
                Timber.e(e, "Stop task failed")
                _isStreaming.value = false
                _currentChatId.value = null
            }
        }
    }

    private fun updateMessageWithEvent(messageId: String, event: SseEvent) {
        val current = _messages.value.toMutableList()
        val idx = current.indexOfFirst { it.id == messageId }
        
        if (idx == -1) {
            // 如果是回放历史，且收到了 AgentStart 且带 query，
            // 此时可能没有对应的用户消息（replay 模式下通常只推 AI 的 SSE）
            // 我们在 AI 消息前插入一个用户消息
            if (event is SseEvent.AgentStart && !event.query.isNullOrBlank()) {
                val userMsgId = "u_$messageId"
                if (current.none { it.id == userMsgId }) {
                    current.add(Message(id = userMsgId, isUser = true, content = event.query, timestamp = currentTime()))
                }
            }
            current.add(Message(id = messageId, isUser = false, timestamp = currentTime(), events = listOf(event)))
        } else {
            val oldMsg = current[idx]
            
            // 如果是在线聊天，且收到了 AgentStart 的 query，尝试更新前一条用户消息
            if (event is SseEvent.AgentStart && !event.query.isNullOrBlank()) {
                val userMsgIdx = idx - 1
                if (userMsgIdx >= 0 && current[userMsgIdx].isUser) {
                    current[userMsgIdx] = current[userMsgIdx].copy(content = event.query)
                } else if (idx == 0) {
                     // 容错：如果 AI 消息排在第一位，则前面补个用户消息
                     current.add(0, Message(id = "u_$messageId", isUser = true, content = event.query, timestamp = currentTime()))
                }
            }

            val newEvents = oldMsg.events + event
            val newContent = if (event is SseEvent.Message) {
                oldMsg.content + (event.content ?: "")
            } else {
                oldMsg.content
            }
            
            // 重新计算索引，因为可能插入了用户消息
            val newIdx = current.indexOfFirst { it.id == messageId }
            current[newIdx] = oldMsg.copy(events = newEvents, content = newContent)
        }
        _messages.value = current
    }

    fun setDeepResearch(v: Boolean) { _deepResearch.value = v }
    fun setWebSearch(v: Boolean) { _webSearch.value = v }
    fun setSkillCall(v: Boolean) { _skillCall.value = v }
    fun showTokenDialog() { _showTokenDialog.value = true }
    fun hideTokenDialog() { _showTokenDialog.value = false }
    
    fun saveSettings(token: String, serverUrl: String) {
        viewModelScope.launch {
            if (token.isNotBlank()) {
                tokenManager.saveToken(token)
            }
            // 如果设置了服务器地址则保存，否则不保存（使用默认值）
            if (serverUrl.isNotBlank()) {
                tokenManager.saveServerUrl(serverUrl)
                ApiClient.setBaseUrl(serverUrl)
            } else {
                // 使用默认本机地址
                ApiClient.setBaseUrl(TokenManager.DEFAULT_SERVER_URL)
            }
            _showTokenDialog.value = false
        }
    }

    private fun currentTime(): String = LocalDateTime.now().format(timeFormatter)

    companion object {
        val Factory: ViewModelProvider.Factory = viewModelFactory {
            initializer {
                val app = this[APPLICATION_KEY] as ProteusAIApplication
                MainViewModel(app.tokenManager, ConversationRepository(), ChatRepository())
            }
        }
    }
}
