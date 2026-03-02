package com.proteus.ai.ui.components

import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.proteus.ai.R
import com.proteus.ai.api.model.Conversation

@Composable
fun ConversationList(
    conversations: List<Conversation>,
    selectedConversationId: String?,
    isLoading: Boolean,
    onConversationClick: (Conversation) -> Unit,
    onNewConversation: () -> Unit,
    onRefresh: () -> Unit,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier,
        tonalElevation = 4.dp
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            // 标题 + 刷新 + 新建按钮
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(start = 16.dp, end = 4.dp, top = 8.dp, bottom = 8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = stringResource(R.string.conversations),
                    style = MaterialTheme.typography.titleMedium.copy(
                        fontWeight = FontWeight.Bold
                    ),
                    modifier = Modifier.weight(1f)
                )

                // 刷新按钮
                IconButton(
                    onClick = onRefresh,
                    enabled = !isLoading
                ) {
                    Icon(
                        imageVector = Icons.Default.Refresh,
                        contentDescription = "刷新",
                        tint = if (isLoading) 
                            MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.3f) 
                        else 
                            MaterialTheme.colorScheme.primary
                    )
                }

                // 新建按钮
                IconButton(onClick = onNewConversation) {
                    Icon(
                        imageVector = Icons.Default.Add,
                        contentDescription = stringResource(R.string.new_conversation),
                        tint = MaterialTheme.colorScheme.primary
                    )
                }
            }
            Divider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f))

            Box(modifier = Modifier.fillMaxSize()) {
                if (conversations.isEmpty() && !isLoading) {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = stringResource(R.string.no_conversations),
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                } else {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(vertical = 8.dp)
                    ) {
                        items(
                            items = conversations,
                            key = { it.id ?: it.hashCode().toString() }
                        ) { conv ->
                            ConversationItem(
                                conversation = conv,
                                isSelected = conv.id == selectedConversationId,
                                onClick = { onConversationClick(conv) }
                            )
                        }
                    }
                }

                // 加载中进度条（置顶展示，更轻量）
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
}

@Composable
fun ConversationItem(
    conversation: Conversation,
    isSelected: Boolean,
    onClick: () -> Unit
) {
    val bgColor = if (isSelected)
        MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.7f)
    else
        Color.Transparent

    Surface(
        onClick = onClick,
        color = bgColor,
        shape = RoundedCornerShape(12.dp),
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 2.dp)
    ) {
        Column(modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp)) {
            Text(
                text = conversation.title?.takeIf { it.isNotBlank() } 
                    ?: stringResource(R.string.unnamed_conversation),
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = if (isSelected) FontWeight.SemiBold else null,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                color = if (isSelected) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurface
            )
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 4.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "${stringResource(R.string.message_count)}: ${conversation.chatCount}",
                    style = MaterialTheme.typography.labelSmall,
                    color = if (isSelected) 
                        MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.7f) 
                    else 
                        MaterialTheme.colorScheme.onSurfaceVariant
                )
                Text(
                    text = conversation.updatedAt?.take(10) ?: "",
                    style = MaterialTheme.typography.labelSmall,
                    color = if (isSelected) 
                        MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.5f) 
                    else 
                        MaterialTheme.colorScheme.outline
                )
            }
        }
    }
}
