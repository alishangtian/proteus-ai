package com.proteus.ai.ui.components

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.proteus.ai.R
import com.proteus.ai.api.model.Conversation
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

@Composable
fun ConversationList(
    conversations: List<Conversation>,
    selectedConversationId: String?,
    isLoading: Boolean,
    onConversationClick: (Conversation) -> Unit,
    onConversationDelete: (Conversation) -> Unit,
    onNewConversation: () -> Unit,
    onRefresh: () -> Unit,
    modifier: Modifier = Modifier,
    isStreaming: Boolean = false,
    currentConversationId: String? = null
) {
    var conversationToDelete by remember { mutableStateOf<Conversation?>(null) }

    // A conversation is running if the API reports it OR it's the current streaming conversation
    val (runningConversations, historyConversations) = remember(conversations, isStreaming, currentConversationId) {
        conversations.partition { conv ->
            conv.isRunning || (isStreaming && conv.conversationId == currentConversationId)
        }
    }

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
                        // 运行中区域
                        if (runningConversations.isNotEmpty()) {
                            item {
                                Text(
                                    text = stringResource(R.string.running_conversations),
                                    style = MaterialTheme.typography.labelSmall.copy(
                                        fontWeight = FontWeight.SemiBold,
                                        letterSpacing = 0.05.sp
                                    ),
                                    color = Color(0xFF16A34A),
                                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp)
                                )
                            }
                            items(
                                items = runningConversations,
                                key = { "running_${it.id ?: it.hashCode()}" }
                            ) { conv ->
                                ConversationItem(
                                    conversation = conv,
                                    isSelected = conv.id == selectedConversationId,
                                    isRunning = true,
                                    onClick = { onConversationClick(conv) },
                                    onLongClick = { conversationToDelete = conv }
                                )
                            }
                        }

                        // 历史会话区域
                        if (historyConversations.isNotEmpty()) {
                            if (runningConversations.isNotEmpty()) {
                                item {
                                    Text(
                                        text = stringResource(R.string.history_conversations),
                                        style = MaterialTheme.typography.labelSmall.copy(
                                            fontWeight = FontWeight.SemiBold,
                                            letterSpacing = 0.05.sp
                                        ),
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp)
                                    )
                                }
                            }
                            items(
                                items = historyConversations,
                                key = { it.id ?: it.hashCode().toString() }
                            ) { conv ->
                                ConversationItem(
                                    conversation = conv,
                                    isSelected = conv.id == selectedConversationId,
                                    isRunning = false,
                                    onClick = { onConversationClick(conv) },
                                    onLongClick = { conversationToDelete = conv }
                                )
                            }
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

    // 删除确认对话框
    if (conversationToDelete != null) {
        AlertDialog(
            onDismissRequest = { conversationToDelete = null },
            title = { Text(text = stringResource(R.string.delete_conversation_title)) },
            text = { 
                Text(
                    text = stringResource(
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
                ) {
                    Text(text = stringResource(R.string.delete))
                }
            },
            dismissButton = {
                TextButton(onClick = { conversationToDelete = null }) {
                    Text(text = stringResource(R.string.cancel))
                }
            }
        )
    }
}

private const val RUNNING_DOT_ANIMATION_DURATION_MS = 1500

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun ConversationItem(
    conversation: Conversation,
    isSelected: Boolean,
    isRunning: Boolean = false,
    onClick: () -> Unit,
    onLongClick: () -> Unit
) {
    val bgColor = when {
        isSelected -> MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.7f)
        isRunning -> Color(0xFFF0FDF4)
        else -> Color.Transparent
    }
    val borderColor = when {
        isSelected -> MaterialTheme.colorScheme.primary
        isRunning -> Color(0xFF86EFAC)
        else -> Color.Transparent
    }

    val formattedTime = remember(conversation.updatedAt) {
        formatConversationTime(conversation.updatedAt)
    }

    // Animated dot for running state
    val infiniteTransition = rememberInfiniteTransition(label = "running")
    val dotAlpha by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 0.2f,
        animationSpec = infiniteRepeatable(
            animation = tween(RUNNING_DOT_ANIMATION_DURATION_MS, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "dotAlpha"
    )

    Surface(
        color = bgColor,
        shape = RoundedCornerShape(12.dp),
        border = if (isRunning || isSelected) androidx.compose.foundation.BorderStroke(1.dp, borderColor) else null,
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 2.dp)
            .combinedClickable(
                onClick = onClick,
                onLongClick = onLongClick
            )
    ) {
        Column(modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp)) {
            Text(
                text = conversation.title?.takeIf { it.isNotBlank() } 
                    ?: stringResource(R.string.unnamed_conversation),
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = if (isSelected) FontWeight.SemiBold else null,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                color = when {
                    isSelected -> MaterialTheme.colorScheme.onPrimaryContainer
                    isRunning -> Color(0xFF15803D)
                    else -> MaterialTheme.colorScheme.onSurface
                }
            )
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 4.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                if (isRunning) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        Box(
                            modifier = Modifier
                                .size(7.dp)
                                .background(
                                    Color(0xFF22C55E).copy(alpha = dotAlpha),
                                    shape = CircleShape
                                )
                        )
                        Text(
                            text = stringResource(R.string.running_conversations),
                            style = MaterialTheme.typography.labelSmall,
                            color = Color(0xFF16A34A),
                            fontWeight = FontWeight.Medium
                        )
                    }
                } else {
                    Text(
                        text = "${stringResource(R.string.message_count)}: ${conversation.chatCount}",
                        style = MaterialTheme.typography.labelSmall,
                        color = if (isSelected) 
                            MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.7f) 
                        else 
                            MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(
                        text = formattedTime,
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
}

private fun formatConversationTime(updatedAt: String?): String {
    if (updatedAt.isNullOrBlank()) return ""
    return try {
        // 后端可能返回带或不带时区信息的字符串
        // 如果后端直接返回 "2023-10-27 10:30:00" 且没给时区，Java 默认会按本地时间解析，这会导致错误
        
        val date: Date? = if (updatedAt.contains("T")) {
            // ISO 格式处理
            val pattern = if (updatedAt.contains(".")) "yyyy-MM-dd'T'HH:mm:ss.SSS" else "yyyy-MM-dd'T'HH:mm:ss"
            val parser = SimpleDateFormat(pattern, Locale.getDefault())
            
            if (updatedAt.endsWith("Z")) {
                parser.timeZone = TimeZone.getTimeZone("UTC")
                parser.parse(updatedAt)
            } else if (updatedAt.contains("+") || (updatedAt.lastIndexOf("-") > 10)) {
                // 自带偏移量如 +08:00，SimpleDateFormat 默认能处理一部分，或者这里保持默认
                parser.parse(updatedAt)
            } else {
                // 有 T 但没标志，通常默认为 UTC
                parser.timeZone = TimeZone.getTimeZone("UTC")
                parser.parse(updatedAt)
            }
        } else {
            // 非 ISO 格式 (yyyy-MM-dd HH:mm:ss)
            // 绝大多数后端接口如果不带 T，通常是存储的 UTC 时间字符串
            SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).apply {
                timeZone = TimeZone.getTimeZone("UTC")
            }.parse(updatedAt)
        }
        
        val outputFormat = SimpleDateFormat("MM-dd HH:mm", Locale.getDefault())
        // 关键：确保输出格式化器使用系统的当前时区
        outputFormat.timeZone = TimeZone.getDefault()
        
        date?.let { outputFormat.format(it) } ?: updatedAt.take(16).replace("T", " ")
    } catch (e: Exception) {
        if (updatedAt.length >= 16) {
            updatedAt.substring(5, 16).replace("T", " ")
        } else {
            updatedAt
        }
    }
}
