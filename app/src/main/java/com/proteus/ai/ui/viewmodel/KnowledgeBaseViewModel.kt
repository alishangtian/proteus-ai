package com.proteus.ai.ui.viewmodel

import androidx.lifecycle.*
import androidx.lifecycle.ViewModelProvider.AndroidViewModelFactory.Companion.APPLICATION_KEY
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.proteus.ai.ProteusAIApplication
import com.proteus.ai.api.model.KnowledgeBaseItem
import com.proteus.ai.repository.KnowledgeBaseRepository
import com.proteus.ai.storage.TokenManager
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import timber.log.Timber

class KnowledgeBaseViewModel(
    private val tokenManager: TokenManager,
    private val repository: KnowledgeBaseRepository
) : ViewModel() {

    private val _token = MutableStateFlow<String?>(null)

    private val _items = MutableStateFlow<List<KnowledgeBaseItem>>(emptyList())
    val items: StateFlow<List<KnowledgeBaseItem>> = _items.asStateFlow()

    private val _loading = MutableStateFlow(false)
    val loading: StateFlow<Boolean> = _loading.asStateFlow()

    private val _uiState = MutableStateFlow<UiState>(UiState.Success)
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    private val _selectedItem = MutableStateFlow<KnowledgeBaseItem?>(null)
    val selectedItem: StateFlow<KnowledgeBaseItem?> = _selectedItem.asStateFlow()

    private val _showAddDialog = MutableStateFlow(false)
    val showAddDialog: StateFlow<Boolean> = _showAddDialog.asStateFlow()

    private val _showDetailDialog = MutableStateFlow(false)
    val showDetailDialog: StateFlow<Boolean> = _showDetailDialog.asStateFlow()

    init {
        viewModelScope.launch {
            tokenManager.tokenFlow().collect { token ->
                _token.value = token
                if (token != null) {
                    loadList(token)
                }
            }
        }
    }

    fun loadList(token: String? = null) {
        val t = token ?: _token.value ?: return
        viewModelScope.launch {
            _loading.value = true
            try {
                _items.value = repository.getList(t)
                _uiState.value = UiState.Success
            } catch (e: Exception) {
                Timber.e(e, "Failed to load knowledge base list")
                _uiState.value = UiState.Error("加载知识库失败: ${e.message}")
            } finally {
                _loading.value = false
            }
        }
    }

    fun loadItemDetail(itemId: String) {
        val token = _token.value ?: return
        viewModelScope.launch {
            _loading.value = true
            try {
                val item = repository.getItem(token, itemId)
                _selectedItem.value = item
                _showDetailDialog.value = true
                _uiState.value = UiState.Success
            } catch (e: Exception) {
                Timber.e(e, "Failed to load knowledge base item")
                _uiState.value = UiState.Error("加载条目失败: ${e.message}")
            } finally {
                _loading.value = false
            }
        }
    }

    fun saveItem(content: String) {
        val token = _token.value ?: return
        if (content.isBlank()) {
            _uiState.value = UiState.Error("内容不能为空")
            return
        }
        viewModelScope.launch {
            _loading.value = true
            try {
                val response = repository.saveItem(token, content)
                if (response.success) {
                    _showAddDialog.value = false
                    loadList(token)
                } else {
                    _uiState.value = UiState.Error("保存失败")
                }
            } catch (e: Exception) {
                Timber.e(e, "Failed to save knowledge base item")
                _uiState.value = UiState.Error("保存失败: ${e.message}")
            } finally {
                _loading.value = false
            }
        }
    }

    fun deleteItem(itemId: String) {
        val token = _token.value ?: return
        viewModelScope.launch {
            _loading.value = true
            try {
                val success = repository.deleteItem(token, itemId)
                if (success) {
                    _items.value = _items.value.filter { it.id != itemId }
                    if (_selectedItem.value?.id == itemId) {
                        _selectedItem.value = null
                        _showDetailDialog.value = false
                    }
                    _uiState.value = UiState.Success
                } else {
                    _uiState.value = UiState.Error("删除失败")
                }
            } catch (e: Exception) {
                Timber.e(e, "Failed to delete knowledge base item")
                _uiState.value = UiState.Error("删除失败: ${e.message}")
            } finally {
                _loading.value = false
            }
        }
    }

    fun showAddDialog() { _showAddDialog.value = true }
    fun hideAddDialog() { _showAddDialog.value = false }
    fun hideDetailDialog() { _showDetailDialog.value = false; _selectedItem.value = null }
    fun clearError() { _uiState.value = UiState.Success }

    companion object {
        val Factory: ViewModelProvider.Factory = viewModelFactory {
            initializer {
                val app = this[APPLICATION_KEY] as ProteusAIApplication
                KnowledgeBaseViewModel(app.tokenManager, KnowledgeBaseRepository())
            }
        }
    }
}
