package com.proteus.ai.ui

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.proteus.ai.R
import com.proteus.ai.ui.viewmodel.AgentMonitorViewModel
import com.proteus.ai.ui.viewmodel.KnowledgeBaseViewModel
import com.proteus.ai.ui.viewmodel.MainViewModel

enum class BottomNavTab { CONVERSATIONS, AGENTS, KNOWLEDGE_BASE, PROFILE }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(viewModel: MainViewModel = viewModel(factory = MainViewModel.Factory)) {
    val tokenState by viewModel.tokenState.collectAsState()
    val conversations by viewModel.conversations.collectAsState()
    val loading by viewModel.loading.collectAsState()
    val isStreaming by viewModel.isStreaming.collectAsState()
    val selectedConversationId by viewModel.selectedConversationId.collectAsState()

    var selectedTab by remember { mutableStateOf(BottomNavTab.CONVERSATIONS) }
    // Navigation state: when non-null, show full-screen ChatScreen (no bottom nav)
    var chatConversationTitle by remember { mutableStateOf<String?>(null) }
    var inChatMode by remember { mutableStateOf(false) }

    var showUploadSheet by remember { mutableStateOf(false) }

    // File picker for the center "+" button (creates new chat with attachment)
    val newChatGalleryLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        uri?.let {
            val name = guessFileName(it)
            viewModel.newConversation()
            viewModel.sendMessage("[附件: $name]")
            chatConversationTitle = "新对话"
            inChatMode = true
        }
    }
    val newChatFileLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        uri?.let {
            val name = guessFileName(it)
            viewModel.newConversation()
            viewModel.sendMessage("[附件: $name]")
            chatConversationTitle = "新对话"
            inChatMode = true
        }
    }

    if (showUploadSheet) {
        UploadBottomSheet(
            onDismiss = { showUploadSheet = false },
            onCamera = {
                showUploadSheet = false
                newChatGalleryLauncher.launch("image/*")
            },
            onGallery = {
                showUploadSheet = false
                newChatGalleryLauncher.launch("image/*")
            },
            onFile = {
                showUploadSheet = false
                newChatFileLauncher.launch(arrayOf("*/*"))
            }
        )
    }

    // Full-screen chat mode: hide bottom navigation
    AnimatedContent(
        targetState = inChatMode,
        transitionSpec = {
            if (targetState) {
                slideInHorizontally { it } + fadeIn() togetherWith
                    slideOutHorizontally { -it / 3 } + fadeOut()
            } else {
                slideInHorizontally { -it / 3 } + fadeIn() togetherWith
                    slideOutHorizontally { it } + fadeOut()
            }
        },
        label = "chatMode"
    ) { chatMode ->
        if (chatMode) {
            ChatScreen(
                viewModel = viewModel,
                conversationTitle = chatConversationTitle,
                onBack = {
                    inChatMode = false
                    chatConversationTitle = null
                }
            )
        } else {
            // Main navigation scaffold
            Scaffold(
                containerColor = MaterialTheme.colorScheme.background,
                bottomBar = {
                    ProteusBottomNav(
                        selectedTab = selectedTab,
                        onTabSelected = { selectedTab = it },
                        onCenterClick = {
                            if (tokenState != null) {
                                showUploadSheet = true
                            } else {
                                selectedTab = BottomNavTab.PROFILE
                            }
                        }
                    )
                }
            ) { paddingValues ->
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(paddingValues)
                ) {
                    when (selectedTab) {
                        BottomNavTab.CONVERSATIONS -> {
                            if (tokenState == null) {
                                TokenRequiredScreen { selectedTab = BottomNavTab.PROFILE }
                            } else {
                                ConversationsScreen(
                                    conversations = conversations,
                                    isLoading = loading,
                                    isStreaming = isStreaming,
                                    currentConversationId = selectedConversationId,
                                    onConversationClick = { conv ->
                                        viewModel.selectConversation(conv)
                                        chatConversationTitle = conv.title
                                        inChatMode = true
                                    },
                                    onConversationDelete = { viewModel.deleteConversation(it) },
                                    onNewConversation = {
                                        viewModel.newConversation()
                                        chatConversationTitle = null
                                        inChatMode = true
                                    },
                                    onRefresh = { viewModel.loadConversations(tokenState ?: "") },
                                    onSettingsClick = { selectedTab = BottomNavTab.PROFILE }
                                )
                            }
                        }
                        BottomNavTab.AGENTS -> AgentMonitorScreen(
                            viewModel = viewModel(factory = AgentMonitorViewModel.Factory)
                        )
                        BottomNavTab.KNOWLEDGE_BASE -> KnowledgeBaseScreen(
                            viewModel = viewModel(factory = KnowledgeBaseViewModel.Factory)
                        )
                        BottomNavTab.PROFILE -> SettingsScreen(viewModel = viewModel)
                    }
                }
            }
        }
    }
}

@Composable
private fun ProteusBottomNav(
    selectedTab: BottomNavTab,
    onTabSelected: (BottomNavTab) -> Unit,
    onCenterClick: () -> Unit
) {
    Surface(
        color = MaterialTheme.colorScheme.surface,
        shadowElevation = 12.dp,
        tonalElevation = 3.dp
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .navigationBarsPadding()
                .height(64.dp),
            horizontalArrangement = Arrangement.SpaceAround,
            verticalAlignment = Alignment.CenterVertically
        ) {
            // 对话
            BottomNavItem(
                icon = Icons.Default.Chat,
                label = stringResource(R.string.nav_conversations),
                selected = selectedTab == BottomNavTab.CONVERSATIONS,
                onClick = { onTabSelected(BottomNavTab.CONVERSATIONS) },
                modifier = Modifier.weight(1f)
            )
            // 智能体
            BottomNavItem(
                icon = Icons.Default.SmartToy,
                label = stringResource(R.string.nav_agent_monitor),
                selected = selectedTab == BottomNavTab.AGENTS,
                onClick = { onTabSelected(BottomNavTab.AGENTS) },
                modifier = Modifier.weight(1f)
            )
            // Center "+" FAB
            Box(
                modifier = Modifier.weight(1f),
                contentAlignment = Alignment.Center
            ) {
                FilledIconButton(
                    onClick = onCenterClick,
                    modifier = Modifier
                        .size(52.dp)
                        .shadow(elevation = 6.dp, shape = CircleShape),
                    shape = CircleShape,
                    colors = IconButtonDefaults.filledIconButtonColors(
                        containerColor = MaterialTheme.colorScheme.primary
                    )
                ) {
                    Icon(
                        Icons.Default.Add,
                        contentDescription = "创作",
                        modifier = Modifier.size(26.dp),
                        tint = MaterialTheme.colorScheme.onPrimary
                    )
                }
            }
            // 知识库
            BottomNavItem(
                icon = Icons.Default.LibraryBooks,
                label = stringResource(R.string.nav_knowledge_base),
                selected = selectedTab == BottomNavTab.KNOWLEDGE_BASE,
                onClick = { onTabSelected(BottomNavTab.KNOWLEDGE_BASE) },
                modifier = Modifier.weight(1f)
            )
            // 我的
            BottomNavItem(
                icon = Icons.Default.Person,
                label = stringResource(R.string.nav_profile),
                selected = selectedTab == BottomNavTab.PROFILE,
                onClick = { onTabSelected(BottomNavTab.PROFILE) },
                modifier = Modifier.weight(1f)
            )
        }
    }
}

@Composable
private fun BottomNavItem(
    icon: ImageVector,
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val color = if (selected) MaterialTheme.colorScheme.primary
    else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)

    IconButton(
        onClick = onClick,
        modifier = modifier.fillMaxHeight()
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Icon(
                icon,
                contentDescription = label,
                tint = color,
                modifier = Modifier.size(24.dp)
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = label,
                style = MaterialTheme.typography.labelSmall.copy(fontSize = 10.sp),
                color = color
            )
        }
    }
}

@Composable
private fun TokenRequiredScreen(onSettingsClick: () -> Unit) {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(
                Icons.Default.Lock,
                contentDescription = null,
                modifier = Modifier.size(64.dp),
                tint = MaterialTheme.colorScheme.primary.copy(alpha = 0.2f)
            )
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                stringResource(R.string.token_required),
                style = MaterialTheme.typography.bodyLarge
            )
            Spacer(modifier = Modifier.height(24.dp))
            Button(onClick = onSettingsClick, shape = RoundedCornerShape(12.dp)) {
                Text(stringResource(R.string.settings))
            }
        }
    }
}
