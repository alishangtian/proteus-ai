package com.proteus.ai.ui.viewmodel

import androidx.lifecycle.*
import androidx.lifecycle.ViewModelProvider.AndroidViewModelFactory.Companion.APPLICATION_KEY
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.proteus.ai.ProteusAIApplication
import com.proteus.ai.api.model.AgentConversationGroup
import com.proteus.ai.api.model.withoutAgent
import com.proteus.ai.repository.AgentRepository
import com.proteus.ai.storage.TokenManager
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import timber.log.Timber

class AgentMonitorViewModel(
    private val tokenManager: TokenManager,
    private val repository: AgentRepository
) : ViewModel() {

    private val _token = MutableStateFlow<String?>(null)

    private val _conversationGroups = MutableStateFlow<List<AgentConversationGroup>>(emptyList())
    val conversationGroups: StateFlow<List<AgentConversationGroup>> = _conversationGroups.asStateFlow()

    private val _loading = MutableStateFlow(false)
    val loading: StateFlow<Boolean> = _loading.asStateFlow()

    private val _uiState = MutableStateFlow<UiState>(UiState.Success)
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    private val _statusFilter = MutableStateFlow<String?>(null)
    val statusFilter: StateFlow<String?> = _statusFilter.asStateFlow()

    private val _totalMessage = MutableStateFlow("")
    val totalMessage: StateFlow<String> = _totalMessage.asStateFlow()

    init {
        viewModelScope.launch {
            tokenManager.tokenFlow().collect { token ->
                _token.value = token
                if (token != null) {
                    loadAgents()
                }
            }
        }
    }

    fun loadAgents() {
        val token = _token.value ?: return
        viewModelScope.launch {
            _loading.value = true
            try {
                val response = repository.getAgentsByConversation(token, status = _statusFilter.value)
                _conversationGroups.value = response.data
                _totalMessage.value = response.message
                _uiState.value = UiState.Success
            } catch (e: Exception) {
                Timber.e(e, "Failed to load agents")
                _uiState.value = UiState.Error("加载 Agent 列表失败: ${e.message}")
            } finally {
                _loading.value = false
            }
        }
    }

    fun setStatusFilter(status: String?) {
        _statusFilter.value = status
        loadAgents()
    }

    fun stopAgent(agentId: String) {
        val token = _token.value ?: return
        viewModelScope.launch {
            try {
                val response = repository.stopAgent(token, agentId)
                if (response.success) {
                    loadAgents()
                } else {
                    _uiState.value = UiState.Error(response.message.ifBlank { "停止 Agent 失败" })
                }
            } catch (e: Exception) {
                Timber.e(e, "Failed to stop agent")
                _uiState.value = UiState.Error("停止失败: ${e.message}")
            }
        }
    }

    fun deleteAgent(agentId: String) {
        val token = _token.value ?: return
        viewModelScope.launch {
            try {
                val response = repository.deleteAgent(token, agentId)
                if (response.success) {
                    _conversationGroups.value = _conversationGroups.value.mapNotNull { group ->
                        group.withoutAgent(agentId)
                    }
                    _uiState.value = UiState.Success
                } else {
                    _uiState.value = UiState.Error(response.message.ifBlank { "删除 Agent 失败" })
                }
            } catch (e: Exception) {
                Timber.e(e, "Failed to delete agent")
                _uiState.value = UiState.Error("删除失败: ${e.message}")
            }
        }
    }

    fun clearError() { _uiState.value = UiState.Success }

    companion object {
        val Factory: ViewModelProvider.Factory = viewModelFactory {
            initializer {
                val app = this[APPLICATION_KEY] as ProteusAIApplication
                AgentMonitorViewModel(app.tokenManager, AgentRepository())
            }
        }
    }
}
