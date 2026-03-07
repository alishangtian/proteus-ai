package com.proteus.ai.ui

import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.proteus.ai.R
import com.proteus.ai.api.model.Conversation

private val conversationAvatarColors = listOf(
    Color(0xFFB5D5FB),
    Color(0xFFBBF7D0),
    Color(0xFFE9D5FF),
    Color(0xFFFDE68A),
    Color(0xFFFBCFE8),
    Color(0xFFBAE6FD),
    Color(0xFFD9F99D),
    Color(0xFFFED7AA),
)

/** Mask to ensure positive hash value for index computation. */
private const val HASH_CODE_MASK = 0x7FFFFFFF

private fun avatarColorForId(id: String): Color {
    val idx = (id.hashCode() and HASH_CODE_MASK) % conversationAvatarColors.size
    return conversationAvatarColors[idx]
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConversationsScreen(
    conversations: List<Conversation>,
    isLoading: Boolean,
    isStreaming: Boolean,
    currentConversationId: String?,
    onConversationClick: (Conversation) -> Unit,
    onConversationDelete: (Conversation) -> Unit,
    onNewConversation: () -> Unit,
    onRefresh: () -> Unit,
    onSettingsClick: () -> Unit
) {
    var conversationToDelete by remember { mutableStateOf<Conversation?>(null) }

    if (conversationToDelete != null) {
        AlertDialog(
            onDismissRequest = { conversationToDelete = null },
            title = { Text(stringResource(R.string.delete_conversation_title)) },
            text = {
                Text(
                    stringResource(
                        R.string.delete_conversation_confirm,
                        conversationToDelete?.title ?: stringResource(R.string.unnamed_conversation)
                    )
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        conversationToDelete?.let { onConversationDelete(it) }
                        conversationToDelete = null
                    },
                    colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error)
                ) { Text(stringResource(R.string.delete)) }
            },
            dismissButton = {
                TextButton(onClick = { conversationToDelete = null }) { Text(stringResource(R.string.cancel)) }
            }
        )
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        stringResource(R.string.nav_conversations),
                        style = MaterialTheme.typography.titleLarge.copy(fontWeight = FontWeight.Bold)
                    )
                },
                actions = {
                    IconButton(onClick = onRefresh) {
                        Icon(Icons.Default.Refresh, contentDescription = stringResource(R.string.retry))
                    }
                    IconButton(onClick = onNewConversation) {
                        Icon(Icons.Default.Edit, contentDescription = stringResource(R.string.new_conversation))
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onSettingsClick) {
                        Icon(Icons.Default.Settings, contentDescription = stringResource(R.string.settings))
                    }
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                ),
                modifier = Modifier.windowInsetsPadding(WindowInsets.statusBars)
            )
        }
    ) { paddingValues ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
        ) {
            if (conversations.isEmpty() && !isLoading) {
                EmptyConversationsHint(
                    modifier = Modifier.align(Alignment.Center),
                    onNewClick = onNewConversation
                )
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(vertical = 4.dp)
                ) {
                    items(conversations, key = { it.id ?: it.hashCode().toString() }) { conv ->
                        ConversationListItem(
                            conversation = conv,
                            isRunning = conv.isRunning || (isStreaming && conv.conversationId == currentConversationId),
                            onClick = { onConversationClick(conv) },
                            onLongClick = { conversationToDelete = conv }
                        )
                    }
                }
            }
            if (isLoading) {
                LinearProgressIndicator(
                    modifier = Modifier
                        .fillMaxWidth()
                        .align(Alignment.TopCenter)
                        .height(2.dp),
                    color = MaterialTheme.colorScheme.primary,
                    trackColor = Color.Transparent
                )
            }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun ConversationListItem(
    conversation: Conversation,
    isRunning: Boolean,
    onClick: () -> Unit,
    onLongClick: () -> Unit
) {
    val avatarColor = remember(conversation.id) {
        avatarColorForId(conversation.id ?: "default")
    }
    val iconTint = remember(avatarColor) {
        avatarColor.copy(
            red = (avatarColor.red * 0.55f).coerceIn(0f, 1f),
            green = (avatarColor.green * 0.55f).coerceIn(0f, 1f),
            blue = (avatarColor.blue * 0.55f).coerceIn(0f, 1f)
        )
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .combinedClickable(onClick = onClick, onLongClick = onLongClick)
            .padding(horizontal = 16.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        // Avatar circle
        Box(
            modifier = Modifier
                .size(50.dp)
                .clip(CircleShape)
                .background(avatarColor),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                Icons.Default.Chat,
                contentDescription = null,
                tint = iconTint,
                modifier = Modifier.size(24.dp)
            )
        }
        Spacer(modifier = Modifier.width(12.dp))
        Column(modifier = Modifier.weight(1f)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = conversation.title?.takeIf { it.isNotBlank() }
                        ?: stringResource(R.string.unnamed_conversation),
                    style = MaterialTheme.typography.bodyLarge.copy(fontWeight = FontWeight.SemiBold),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f)
                )
            }
            Spacer(modifier = Modifier.height(3.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                if (isRunning) {
                    RunningDotIndicator()
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        text = stringResource(R.string.running_conversations),
                        style = MaterialTheme.typography.bodySmall,
                        color = Color(0xFF16A34A),
                        modifier = Modifier.weight(1f)
                    )
                } else {
                    Text(
                        text = conversation.initialQuestion?.takeIf { it.isNotBlank() }
                            ?: stringResource(R.string.no_preview),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.55f),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f)
                    )
                }
            }
        }
    }
    HorizontalDivider(
        modifier = Modifier.padding(start = 78.dp),
        color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.4f)
    )
}

@Composable
private fun RunningDotIndicator() {
    val infiniteTransition = rememberInfiniteTransition(label = "dot")
    val alpha by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 0.2f,
        animationSpec = infiniteRepeatable(
            animation = androidx.compose.animation.core.tween(1000),
            repeatMode = androidx.compose.animation.core.RepeatMode.Reverse
        ),
        label = "alpha"
    )
    Box(
        modifier = Modifier
            .size(7.dp)
            .clip(CircleShape)
            .background(Color(0xFF22C55E).copy(alpha = alpha))
    )
}

@Composable
private fun EmptyConversationsHint(modifier: Modifier, onNewClick: () -> Unit) {
    Column(
        modifier = modifier.padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Icon(
            Icons.Default.Chat,
            contentDescription = null,
            modifier = Modifier.size(72.dp),
            tint = MaterialTheme.colorScheme.primary.copy(alpha = 0.15f)
        )
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            stringResource(R.string.no_conversations),
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
        )
        Spacer(modifier = Modifier.height(24.dp))
        Button(onClick = onNewClick, shape = RoundedCornerShape(12.dp)) {
            Icon(Icons.Default.Edit, contentDescription = null, modifier = Modifier.size(18.dp))
            Spacer(modifier = Modifier.width(8.dp))
            Text(stringResource(R.string.new_conversation))
        }
    }
}
