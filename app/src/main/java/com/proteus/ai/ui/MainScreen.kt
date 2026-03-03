package com.proteus.ai.ui

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.proteus.ai.R
import com.proteus.ai.ui.components.ConversationList
import com.proteus.ai.ui.components.MessageList
import com.proteus.ai.ui.components.TokenDialog
import com.proteus.ai.ui.viewmodel.MainViewModel
import com.proteus.ai.ui.viewmodel.UiState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(viewModel: MainViewModel = viewModel(factory = MainViewModel.Factory)) {
    val tokenState by viewModel.tokenState.collectAsState()
    val serverUrlState by viewModel.serverUrlState.collectAsState()
    val showTokenDialog by viewModel.showTokenDialog.collectAsState()
    val conversations by viewModel.conversations.collectAsState()
    val loading by viewModel.loading.collectAsState()
    val uiState by viewModel.uiState.collectAsState()
    val messages by viewModel.messages.collectAsState()
    val isStreaming by viewModel.isStreaming.collectAsState()
    val selectedConversationId by viewModel.selectedConversationId.collectAsState()

    var inputText by remember { mutableStateOf("") }
    var sidebarExpanded by remember { mutableStateOf(false) }

    if (showTokenDialog) {
        TokenDialog(
            onDismissRequest = { viewModel.hideTokenDialog() },
            onConfirm = { token, serverUrl -> viewModel.saveSettings(token, serverUrl) },
            initialToken = tokenState ?: "",
            initialServerUrl = serverUrlState ?: ""
        )
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            CenterAlignedTopAppBar(
                title = { 
                    Text(
                        stringResource(R.string.app_name),
                        style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold)
                    ) 
                },
                navigationIcon = {
                    IconButton(onClick = { sidebarExpanded = !sidebarExpanded }) {
                        Icon(if (sidebarExpanded) Icons.Default.Close else Icons.Default.Menu, contentDescription = null)
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.showTokenDialog() }) {
                        Icon(Icons.Default.Settings, contentDescription = null)
                    }
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                    containerColor = Color.Transparent
                )
            )
        }
    ) { paddingValues ->
        if (tokenState == null) {
            TokenRequiredPlaceholder(paddingValues) { viewModel.showTokenDialog() }
        } else {
            Box(modifier = Modifier.fillMaxSize().padding(paddingValues)) {
                Row(modifier = Modifier.fillMaxSize()) {
                    AnimatedVisibility(
                        visible = sidebarExpanded,
                        enter = expandHorizontally() + fadeIn(),
                        exit = shrinkHorizontally() + fadeOut()
                    ) {
                        ConversationList(
                            conversations = conversations,
                            selectedConversationId = selectedConversationId,
                            isLoading = loading,
                            onConversationClick = {
                                viewModel.selectConversation(it)
                                sidebarExpanded = false
                            },
                            onNewConversation = {
                                sidebarExpanded = false
                                viewModel.newConversation()
                            },
                            onRefresh = {
                                viewModel.loadConversations(tokenState ?: "")
                            },
                            modifier = Modifier
                                .fillMaxHeight()
                                .width(300.dp)
                                .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.3f))
                        )
                    }

                    Column(modifier = Modifier.fillMaxSize()) {
                        ErrorMessageBar(uiState, viewModel)

                        MessageList(
                            messages = messages,
                            modifier = Modifier.weight(1f).fillMaxWidth()
                        )

                        InputArea(
                            inputText = inputText,
                            onInputTextChange = { inputText = it },
                            isStreaming = isStreaming,
                            onSendClick = {
                                if (inputText.isNotBlank() && !isStreaming) {
                                    viewModel.sendMessage(inputText.trim())
                                    inputText = ""
                                }
                            },
                            onStopClick = {
                                viewModel.stopTask()
                            }
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun InputArea(
    inputText: String,
    onInputTextChange: (String) -> Unit,
    isStreaming: Boolean,
    onSendClick: () -> Unit,
    onStopClick: () -> Unit
) {
    val keyboardController = LocalSoftwareKeyboardController.current
    val focusRequester = remember { FocusRequester() }

    // 添加整体边距，与屏幕边缘保持距离
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 8.dp)
    ) {
        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .shadow(elevation = 8.dp, shape = RoundedCornerShape(24.dp)),
            shape = RoundedCornerShape(24.dp),
            color = MaterialTheme.colorScheme.surface,
            tonalElevation = 3.dp
        ) {
            Column(
                modifier = Modifier
                    .windowInsetsPadding(WindowInsets.navigationBars)
                    .padding(horizontal = 12.dp, vertical = 12.dp)
            ) {
                TextField(
                    value = inputText,
                    onValueChange = onInputTextChange,
                    placeholder = { 
                        Text(
                            stringResource(R.string.input_hint), 
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.4f)
                        ) 
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .focusRequester(focusRequester),
                    enabled = !isStreaming,
                    maxLines = 6,
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                    keyboardActions = KeyboardActions(onSend = {
                        if (inputText.isNotBlank() && !isStreaming) {
                            onSendClick()
                            keyboardController?.hide()
                        }
                    }),
                    colors = TextFieldDefaults.colors(
                        focusedContainerColor = Color.Transparent,
                        unfocusedContainerColor = Color.Transparent,
                        disabledContainerColor = Color.Transparent,
                        focusedIndicatorColor = Color.Transparent,
                        unfocusedIndicatorColor = Color.Transparent,
                        disabledIndicatorColor = Color.Transparent
                    ),
                    trailingIcon = {
                        if (isStreaming) {
                            // 停止按钮 - 红色外圆内方，带进度环
                            StopButton(onClick = onStopClick)
                        } else {
                            // 发送按钮
                            FilledIconButton(
                                onClick = onSendClick,
                                enabled = inputText.isNotBlank(),
                                shape = CircleShape,
                                colors = IconButtonDefaults.filledIconButtonColors(
                                    containerColor = MaterialTheme.colorScheme.primary
                                ),
                                modifier = Modifier
                                    .padding(end = 4.dp)
                                    .size(42.dp)
                            ) {
                                Icon(Icons.AutoMirrored.Filled.Send, contentDescription = null, modifier = Modifier.size(22.dp))
                            }
                        }
                    }
                )
            }
        }
    }
}

@Composable
private fun StopButton(onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .padding(end = 4.dp)
            .size(42.dp),
        contentAlignment = Alignment.Center
    ) {
        // 1. 背景红色圆圈（可点击）
        Box(
            modifier = Modifier
                .size(32.dp)
                .clip(CircleShape)
                .background(MaterialTheme.colorScheme.error)
                .clickable(onClick = onClick),
            contentAlignment = Alignment.Center
        ) {
            // 2. 内部白色方形图标 (Stop Icon)
            Box(
                modifier = Modifier
                    .size(12.dp)
                    .background(MaterialTheme.colorScheme.onError, shape = RoundedCornerShape(2.dp))
            )
        }

        // 3. 外部转圈的进度条
        CircularProgressIndicator(
            modifier = Modifier.size(40.dp),
            strokeWidth = 2.dp,
            color = MaterialTheme.colorScheme.error,
            trackColor = MaterialTheme.colorScheme.error.copy(alpha = 0.1f)
        )
    }
}

@Composable
private fun TokenRequiredPlaceholder(padding: PaddingValues, onSettingsClick: () -> Unit) {
    Box(modifier = Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(Icons.Default.Lock, contentDescription = null, modifier = Modifier.size(64.dp), tint = MaterialTheme.colorScheme.primary.copy(alpha = 0.2f))
            Spacer(modifier = Modifier.height(16.dp))
            Text(stringResource(R.string.token_required), style = MaterialTheme.typography.bodyLarge)
            Spacer(modifier = Modifier.height(24.dp))
            Button(onClick = onSettingsClick, shape = RoundedCornerShape(12.dp)) {
                Text(stringResource(R.string.settings))
            }
        }
    }
}

@Composable
private fun ErrorMessageBar(uiState: UiState, viewModel: MainViewModel) {
    AnimatedVisibility(
        visible = uiState is UiState.Error,
        enter = expandVertically() + fadeIn(),
        exit = shrinkVertically() + fadeOut()
    ) {
        if (uiState is UiState.Error) {
            Surface(
                color = MaterialTheme.colorScheme.errorContainer,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                shape = RoundedCornerShape(12.dp),
                border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.error.copy(alpha = 0.2f)),
                tonalElevation = 4.dp
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector = Icons.Default.Warning,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.error,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(12.dp))
                    Text(
                        text = uiState.message,
                        modifier = Modifier.weight(1f),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onErrorContainer
                    )
                    if (uiState.retryable) {
                        val token = viewModel.tokenState.collectAsState().value ?: ""
                        TextButton(
                            onClick = { viewModel.loadConversations(token) },
                            colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error)
                        ) {
                            Text(stringResource(R.string.retry), fontWeight = FontWeight.Bold)
                        }
                    }
                    IconButton(onClick = { /* 可以在 ViewModel 中添加清除错误状态的方法 */ }) {
                        Icon(Icons.Default.Close, null, modifier = Modifier.size(16.dp))
                    }
                }
            }
        }
    }
}
