package com.proteus.ai.ui.components

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.ThumbUp
import androidx.compose.material.icons.outlined.ThumbUp
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.proteus.ai.R
import com.proteus.ai.api.model.SseEvent
import com.proteus.ai.ui.theme.Typography
import com.halilibo.richtext.markdown.Markdown
import com.halilibo.richtext.ui.material3.Material3RichText
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.filter

data class Message(
    val id: String,
    val isUser: Boolean,
    val timestamp: String,
    val content: String = "",
    val events: List<SseEvent> = emptyList()
)

@Composable
fun MessageList(
    messages: List<Message>,
    modifier: Modifier = Modifier,
    isStreaming: Boolean = false
) {
    val listState = rememberLazyListState()

    var autoScrollEnabled by remember { mutableStateOf(true) }

    LaunchedEffect(listState) {
        snapshotFlow {
            val layout = listState.layoutInfo
            val visibleItems = layout.visibleItemsInfo
            if (visibleItems.isEmpty() || layout.totalItemsCount == 0) {
                return@snapshotFlow true
            }
            val lastVisible = visibleItems.last()
            val viewportHeight = layout.viewportEndOffset - layout.viewportStartOffset
            val threshold = (viewportHeight * 0.10f).toInt()

            val isLastItem = lastVisible.index >= layout.totalItemsCount - 1
            val lastItemBottom = lastVisible.offset + lastVisible.size
            val viewportBottom = layout.viewportEndOffset - layout.afterContentPadding
            isLastItem && (viewportBottom - lastItemBottom) <= threshold
        }
            .distinctUntilChanged()
            .collect { isAtBottom ->
                if (isAtBottom) {
                    autoScrollEnabled = true
                } else if (listState.isScrollInProgress) {
                    autoScrollEnabled = false
                }
            }
    }

    suspend fun scrollToBottomWithGap() {
        val layout = listState.layoutInfo
        val total = layout.totalItemsCount
        if (total == 0) return

        val viewportHeight = layout.viewportEndOffset - layout.viewportStartOffset
        val lastItemSize = layout.visibleItemsInfo
            .lastOrNull { it.index == total - 1 }?.size
            ?: 0
        val gap = (viewportHeight * 0.10f).toInt()
        val offset = (lastItemSize - viewportHeight + gap).coerceAtLeast(0)

        listState.animateScrollToItem(index = total - 1, scrollOffset = offset)
    }

    val lastMessage = messages.lastOrNull()
    val lastContentLength = lastMessage?.content?.length ?: 0
    val lastEventsSize = lastMessage?.events?.size ?: 0

    LaunchedEffect(messages.size, lastContentLength, lastEventsSize) {
        if (lastMessage?.isUser == true) {
            autoScrollEnabled = true
        }
        if (autoScrollEnabled) {
            scrollToBottomWithGap()
        }
    }

    LaunchedEffect(listState) {
        snapshotFlow {
            val layout = listState.layoutInfo
            val items = layout.visibleItemsInfo
            if (items.isEmpty()) 0
            else items.first().offset + items.sumOf { it.size }
        }
            .distinctUntilChanged()
            .filter { autoScrollEnabled && !listState.isScrollInProgress }
            .collect {
                scrollToBottomWithGap()
            }
    }

    LazyColumn(
        state = listState,
        modifier = modifier,
        verticalArrangement = Arrangement.spacedBy(16.dp),
        contentPadding = PaddingValues(top = 16.dp, bottom = 120.dp)
    ) {
        itemsIndexed(messages, key = { _, message -> message.id }) { index, message ->
            val isLastAiMessage = !message.isUser && (
                index == messages.lastIndex || 
                messages.subList(index + 1, messages.size).all { it.isUser }
            )
            MessageBubble(
                message = message,
                showActions = isLastAiMessage && !isStreaming && message.content.isNotEmpty()
            )
        }
    }
}

@Composable
fun MessageBubble(message: Message, showActions: Boolean = false) {
    val alignment = if (message.isUser) Alignment.End else Alignment.Start

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 8.dp)
            .animateContentSize(),
        horizontalAlignment = alignment
    ) {
        if (message.isUser) {
            UserMessageContent(message)
        } else {
            AiMessageContent(message, showActions = showActions)
        }
    }
}

@Composable
private fun UserMessageContent(message: Message) {
    val gradient = Brush.linearGradient(
        colors = listOf(
            MaterialTheme.colorScheme.primary,
            MaterialTheme.colorScheme.secondary
        )
    )

    Column(horizontalAlignment = Alignment.End) {
        Surface(
            shape = RoundedCornerShape(20.dp, 20.dp, 4.dp, 20.dp),
            modifier = Modifier
                .clip(RoundedCornerShape(20.dp, 20.dp, 4.dp, 20.dp))
                .background(gradient),
            color = Color.Transparent,
            contentColor = MaterialTheme.colorScheme.onPrimary,
            shadowElevation = 2.dp
        ) {
            Text(
                text = message.content,
                style = Typography.bodyLarge,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp)
            )
        }
        Text(
            text = message.timestamp,
            style = Typography.labelSmall.copy(fontSize = 10.sp),
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.4f),
            modifier = Modifier.padding(top = 4.dp, end = 4.dp)
        )
    }
}

sealed class MergedEvent {
    data class Thinking(val events: List<SseEvent.AgentStreamThinking>) : MergedEvent()
    data class Tool(val actionId: String, val events: List<SseEvent>) : MergedEvent()
    data class Message(val content: String) : MergedEvent()
    data class Compress(val event: SseEvent) : MergedEvent()
}

@Composable
private fun AiMessageContent(message: Message, showActions: Boolean = false) {
    Column(
        modifier = Modifier
            .fillMaxWidth(0.92f)
            .animateContentSize()
    ) {
        if (message.events.isEmpty() && message.content.isEmpty()) {
            AiLoadingPlaceholder()
        } else {
            val displayItems = remember(message.events, message.content) {
                val items = mutableListOf<MergedEvent>()
                val toolGroups = mutableMapOf<String, MutableList<SseEvent>>()
                var currentThinkingGroup = mutableListOf<SseEvent.AgentStreamThinking>()
                var currentMessageContent = StringBuilder()

                message.events.forEach { event ->
                    when (event) {
                        is SseEvent.AgentStreamThinking -> {
                            if (currentMessageContent.isNotEmpty()) {
                                items.add(MergedEvent.Message(currentMessageContent.toString()))
                                currentMessageContent = StringBuilder()
                            }
                            currentThinkingGroup.add(event)
                            if (event.isDone) {
                                items.add(MergedEvent.Thinking(currentThinkingGroup))
                                currentThinkingGroup = mutableListOf()
                            }
                        }
                        is SseEvent.ActionStart, is SseEvent.ActionComplete, is SseEvent.ToolProgress -> {
                            if (currentThinkingGroup.isNotEmpty()) {
                                items.add(MergedEvent.Thinking(currentThinkingGroup))
                                currentThinkingGroup = mutableListOf()
                            }
                            if (currentMessageContent.isNotEmpty()) {
                                items.add(MergedEvent.Message(currentMessageContent.toString()))
                                currentMessageContent = StringBuilder()
                            }
                            val actionId = when (event) {
                                is SseEvent.ActionStart -> event.actionId
                                is SseEvent.ActionComplete -> event.actionId
                                is SseEvent.ToolProgress -> event.actionId
                                else -> null
                            }
                            if (actionId != null) {
                                if (!toolGroups.containsKey(actionId)) {
                                    val group = mutableListOf(event)
                                    toolGroups[actionId] = group
                                    items.add(MergedEvent.Tool(actionId, group))
                                } else {
                                    toolGroups[actionId]?.add(event)
                                }
                            }
                        }
                        is SseEvent.Message -> {
                            if (currentThinkingGroup.isNotEmpty()) {
                                items.add(MergedEvent.Thinking(currentThinkingGroup))
                                currentThinkingGroup = mutableListOf()
                            }
                            currentMessageContent.append(event.content ?: "")
                        }
                        is SseEvent.CompressStart, is SseEvent.CompressComplete -> {
                            if (currentMessageContent.isNotEmpty()) {
                                items.add(MergedEvent.Message(currentMessageContent.toString()))
                                currentMessageContent = StringBuilder()
                            }
                            // Replace any existing compress event rather than adding a new one
                            val existingIdx = items.indexOfFirst { it is MergedEvent.Compress }
                            if (existingIdx >= 0) {
                                items[existingIdx] = MergedEvent.Compress(event)
                            } else {
                                items.add(MergedEvent.Compress(event))
                            }
                        }
                        else -> {}
                    }
                }

                if (currentThinkingGroup.isNotEmpty()) items.add(MergedEvent.Thinking(currentThinkingGroup))
                if (currentMessageContent.isNotEmpty()) {
                    items.add(MergedEvent.Message(currentMessageContent.toString()))
                }
                
                if (items.none { it is MergedEvent.Message } && message.content.isNotEmpty()) {
                    items.add(MergedEvent.Message(message.content))
                }

                items
            }

            displayItems.forEachIndexed { index, item ->
                when (item) {
                    is MergedEvent.Thinking -> ThinkingProcessCard(item.events)
                    is MergedEvent.Tool -> ToolExecutionCard(item.events)
                    is MergedEvent.Message -> AiTextMessage(item.content)
                    is MergedEvent.Compress -> CompressEventBar(item.event)
                }
                if (index < displayItems.size - 1) Spacer(modifier = Modifier.height(8.dp))
            }

            if (showActions) {
                MessageActionButtons(messageContent = message.content)
            }
        }
    }
}

@Composable
private fun CompressEventBar(event: SseEvent) {
    var visible by remember { mutableStateOf(true) }
    
    // 如果是完成事件，3秒后自动消失
    if (event is SseEvent.CompressComplete) {
        LaunchedEffect(Unit) {
            delay(3000)
            visible = false
        }
    }

    AnimatedVisibility(
        visible = visible,
        enter = expandVertically() + fadeIn(),
        exit = shrinkVertically() + fadeOut()
    ) {
        Surface(
            modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
            shape = RoundedCornerShape(8.dp),
            color = MaterialTheme.colorScheme.tertiaryContainer.copy(alpha = 0.3f),
            border = BorderStroke(0.5.dp, MaterialTheme.colorScheme.tertiary.copy(alpha = 0.5f))
        ) {
            Row(
                modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                if (event is SseEvent.CompressStart) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(14.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.tertiary
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "📏 Token 超限(${event.originalLength})，正在压缩历史...",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onTertiaryContainer
                    )
                } else if (event is SseEvent.CompressComplete) {
                    Icon(
                        imageVector = Icons.Default.Info,
                        contentDescription = null,
                        modifier = Modifier.size(14.dp),
                        tint = MaterialTheme.colorScheme.tertiary
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "✅ 压缩完成！(${event.originalLength} -> ${event.compressedLength})",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onTertiaryContainer
                    )
                }
            }
        }
    }
}

@Composable
private fun AiTextMessage(content: String) {
    val mermaidRegex = """```mermaid\n([\s\S]*?)```""".toRegex()
    val parts = remember(content) {
        val result = mutableListOf<Pair<String, Boolean>>()
        var lastIndex = 0
        mermaidRegex.findAll(content).forEach { match ->
            if (match.range.first > lastIndex) {
                result.add(content.substring(lastIndex, match.range.first) to false)
            }
            result.add(match.groupValues[1] to true)
            lastIndex = match.range.last + 1
        }
        if (lastIndex < content.length) {
            result.add(content.substring(lastIndex) to false)
        }
        if (result.isEmpty() && content.isNotEmpty()) result.add(content to false)
        result
    }

    var fullscreenMermaidCode by remember { mutableStateOf<String?>(null) }

    Surface(
        shape = RoundedCornerShape(4.dp, 20.dp, 20.dp, 20.dp),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
        border = androidx.compose.foundation.BorderStroke(0.5.dp, MaterialTheme.colorScheme.outlineVariant),
        tonalElevation = 1.dp
    ) {
        SelectionContainer {
            Column(modifier = Modifier.padding(16.dp).animateContentSize()) {
                parts.forEach { (text, isMermaid) ->
                    if (isMermaid) {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable { fullscreenMermaidCode = text.trim() }
                        ) {
                            MermaidWebView(mermaidCode = text.trim())
                        }
                    } else {
                        Material3RichText {
                            Markdown(content = text)
                        }
                    }
                }
            }
        }
    }

    if (fullscreenMermaidCode != null) {
        MermaidFullscreenDialog(
            mermaidCode = fullscreenMermaidCode!!,
            onDismiss = { fullscreenMermaidCode = null }
        )
    }
}

@Composable
private fun AiLoadingPlaceholder() {
    Box(
        modifier = Modifier
            .padding(start = 12.dp, top = 8.dp)
            .size(24.dp),
        contentAlignment = Alignment.Center
    ) {
        CircularProgressIndicator(
            modifier = Modifier.size(18.dp),
            strokeWidth = 2.5.dp,
            color = MaterialTheme.colorScheme.primary,
            trackColor = MaterialTheme.colorScheme.primary.copy(alpha = 0.1f)
        )
    }
}

@Composable
private fun ThinkingProcessCard(events: List<SseEvent.AgentStreamThinking>) {
    var expanded by remember { mutableStateOf(false) }
    val isDone = events.any { it.isDone }
    val fullThinking = events.filter { !it.isDone }.joinToString("") { it.thinking ?: "" }

    val infiniteTransition = rememberInfiniteTransition(label = "thinking")
    val alpha by infiniteTransition.animateFloat(
        initialValue = 0.4f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(1000, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ), label = "alpha"
    )

    val scrollState = rememberScrollState()
    val density = LocalDensity.current
    var textHeight by remember { mutableIntStateOf(0) }
    
    // 自动滚动
    LaunchedEffect(fullThinking, expanded) {
        if (fullThinking.isNotEmpty() && !expanded) {
            scrollState.animateScrollTo(scrollState.maxValue)
        }
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .animateContentSize(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceColorAtElevation(1.dp)),
        shape = RoundedCornerShape(12.dp),
        border = androidx.compose.foundation.BorderStroke(0.5.dp, MaterialTheme.colorScheme.outlineVariant)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            // 状态栏
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { expanded = !expanded },
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .size(8.dp)
                        .clip(CircleShape)
                        .background(
                            if (isDone) MaterialTheme.colorScheme.primary
                            else MaterialTheme.colorScheme.primary.copy(alpha = alpha)
                        )
                )
                Spacer(modifier = Modifier.width(12.dp))
                Text(
                    text = if (isDone) "思考已完成" else "正在思考...",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.weight(1f)
                )
                Icon(
                    imageVector = if (expanded) Icons.Default.KeyboardArrowUp else Icons.Default.KeyboardArrowDown,
                    contentDescription = null,
                    modifier = Modifier.size(20.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.5f)
                )
            }

            // 思考内容区域
            if (fullThinking.isNotEmpty()) {
                val oneLineHeight = with(density) { 20.sp.toDp() }
                val threeLinesHeight = with(density) { 60.sp.toDp() }
                
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 8.dp)
                        .then(
                            if (expanded) {
                                Modifier.wrapContentHeight().heightIn(max = 400.dp)
                            } else {
                                // 逻辑：初始占1行高度，超过1行则扩展到3行，超过3行则滚动
                                val currentTextHeightDp = with(density) { textHeight.toDp() }
                                if (currentTextHeightDp <= oneLineHeight) {
                                    Modifier.height(oneLineHeight)
                                } else {
                                    Modifier.height(threeLinesHeight)
                                }
                            }
                        )
                        .verticalScroll(scrollState)
                ) {
                    SelectionContainer {
                        Text(
                            text = fullThinking,
                            style = MaterialTheme.typography.bodySmall.copy(
                                fontSize = 12.sp,
                                lineHeight = 18.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.85f)
                            ),
                            modifier = Modifier.onGloballyPositioned { coordinates ->
                                textHeight = coordinates.size.height
                            }
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ToolExecutionCard(events: List<SseEvent>) {
    val start = events.filterIsInstance<SseEvent.ActionStart>().firstOrNull()
    val complete = events.filterIsInstance<SseEvent.ActionComplete>().firstOrNull()
    val progresses = events.filterIsInstance<SseEvent.ToolProgress>()
    var expanded by remember { mutableStateOf(false) }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .animateContentSize(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.1f)
        ),
        shape = RoundedCornerShape(12.dp),
        border = androidx.compose.foundation.BorderStroke(
            0.5.dp,
            MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)
        )
    ) {
        Column(modifier = Modifier.animateContentSize()) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { expanded = !expanded }
                    .padding(12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                if (complete == null) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(16.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.secondary
                    )
                } else {
                    Icon(
                        imageVector = Icons.Default.Settings,
                        contentDescription = null,
                        modifier = Modifier.size(16.dp),
                        tint = MaterialTheme.colorScheme.secondary
                    )
                }
                Spacer(modifier = Modifier.width(12.dp))
                Column(modifier = Modifier.weight(1f)) {
                    val toolName = start?.action ?: progresses.lastOrNull()?.tool ?: "处理中"
                    Text(
                        text = "工具调用: $toolName",
                        style = MaterialTheme.typography.labelMedium.copy(fontWeight = FontWeight.Bold)
                    )
                    val statusText = complete?.let { "执行完毕" } 
                        ?: progresses.lastOrNull()?.status 
                        ?: "正在运行..."
                    Text(
                        text = statusText,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f)
                    )
                }
                Icon(
                    imageVector = if (expanded) Icons.Default.KeyboardArrowUp else Icons.Default.KeyboardArrowDown,
                    contentDescription = null,
                    modifier = Modifier.size(20.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            AnimatedVisibility(visible = expanded) {
                Column(modifier = Modifier.padding(start = 12.dp, end = 12.dp, bottom = 12.dp)) {
                    if (start?.input != null) ToolInfoSection(title = "输入 (Input)", content = start.input.toString())
                    
                    if (progresses.isNotEmpty()) {
                        Spacer(modifier = Modifier.height(8.dp))
                        Column {
                            Text(
                                text = "执行进度",
                                style = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.Bold),
                                color = MaterialTheme.colorScheme.secondary
                            )
                            progresses.forEach { prog ->
                                Text(
                                    text = "• ${prog.status}",
                                    style = MaterialTheme.typography.bodySmall.copy(fontSize = 11.sp),
                                    modifier = Modifier.padding(start = 8.dp, top = 2.dp)
                                )
                            }
                        }
                    }

                    if (complete?.result != null) {
                        Spacer(modifier = Modifier.height(8.dp))
                        ToolInfoSection(title = "输出 (Output)", content = complete.result)
                    }
                }
            }
        }
    }
}

@Composable
private fun ToolInfoSection(title: String, content: String) {
    Column {
        Text(
            text = title,
            style = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.Bold),
            color = MaterialTheme.colorScheme.secondary
        )
        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 4.dp),
            shape = RoundedCornerShape(8.dp),
            color = MaterialTheme.colorScheme.surface.copy(alpha = 0.5f),
            border = androidx.compose.foundation.BorderStroke(0.5.dp, MaterialTheme.colorScheme.outlineVariant)
        ) {
            SelectionContainer {
                Text(
                    text = content,
                    modifier = Modifier.padding(8.dp),
                    style = MaterialTheme.typography.bodySmall.copy(
                        fontFamily = FontFamily.Monospace,
                        fontSize = 11.sp
                    )
                )
            }
        }
    }
}

@Composable
private fun MessageActionButtons(messageContent: String) {
    val clipboardManager = LocalClipboardManager.current
    var copied by remember { mutableStateOf(false) }
    var liked by remember { mutableStateOf(false) }
    var disliked by remember { mutableStateOf(false) }

    LaunchedEffect(copied) {
        if (copied) {
            delay(2000)
            copied = false
        }
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 8.dp),
        horizontalArrangement = Arrangement.Start,
        verticalAlignment = Alignment.CenterVertically
    ) {
        // Copy button
        IconButton(
            onClick = {
                clipboardManager.setText(AnnotatedString(messageContent))
                copied = true
            },
            modifier = Modifier.size(32.dp)
        ) {
            Icon(
                painter = painterResource(
                    id = if (copied) R.drawable.ic_check else R.drawable.ic_copy
                ),
                contentDescription = "复制",
                modifier = Modifier.size(16.dp),
                tint = if (copied) MaterialTheme.colorScheme.primary
                       else MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f)
            )
        }

        // Like button
        IconButton(
            onClick = {
                liked = !liked
                if (liked) disliked = false
            },
            modifier = Modifier.size(32.dp)
        ) {
            Icon(
                imageVector = if (liked) Icons.Filled.ThumbUp else Icons.Outlined.ThumbUp,
                contentDescription = "点赞",
                modifier = Modifier.size(16.dp),
                tint = if (liked) MaterialTheme.colorScheme.primary
                       else MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f)
            )
        }

        // Dislike button (rotated ThumbUp)
        IconButton(
            onClick = {
                disliked = !disliked
                if (disliked) liked = false
            },
            modifier = Modifier.size(32.dp)
        ) {
            Icon(
                imageVector = if (disliked) Icons.Filled.ThumbUp else Icons.Outlined.ThumbUp,
                contentDescription = "点踩",
                modifier = Modifier
                    .size(16.dp)
                    .rotate(180f),
                tint = if (disliked) MaterialTheme.colorScheme.error
                       else MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f)
            )
        }

        // Skill generation button
        IconButton(
            onClick = { /* Skill generation action */ },
            modifier = Modifier.size(32.dp)
        ) {
            Icon(
                painter = painterResource(id = R.drawable.ic_skill),
                contentDescription = "技能生成",
                modifier = Modifier.size(16.dp),
                tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f)
            )
        }
    }
}

@Composable
private fun MermaidFullscreenDialog(mermaidCode: String, onDismiss: () -> Unit) {
    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Surface(
            modifier = Modifier.fillMaxSize(),
            color = MaterialTheme.colorScheme.background
        ) {
            Box(modifier = Modifier.fillMaxSize()) {
                MermaidWebView(
                    mermaidCode = mermaidCode,
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(top = 56.dp)
                )
                // Close button
                IconButton(
                    onClick = onDismiss,
                    modifier = Modifier
                        .align(Alignment.TopEnd)
                        .padding(8.dp)
                ) {
                    Icon(
                        painter = painterResource(id = R.drawable.ic_close),
                        contentDescription = "关闭",
                        modifier = Modifier.size(24.dp),
                        tint = MaterialTheme.colorScheme.onSurface
                    )
                }
            }
        }
    }
}
