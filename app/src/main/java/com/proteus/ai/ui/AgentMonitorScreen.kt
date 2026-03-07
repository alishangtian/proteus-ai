package com.proteus.ai.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.SmartToy
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Snackbar
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.proteus.ai.api.model.AgentConversationGroup
import com.proteus.ai.api.model.AgentInfo
import com.proteus.ai.ui.viewmodel.AgentMonitorViewModel
import com.proteus.ai.ui.viewmodel.UiState
import kotlinx.coroutines.delay
import kotlin.math.roundToInt

// Backend uses this sentinel when an agent is not associated with any conversation.
private const val NO_CONVERSATION_ID = "__no_conversation__"
private const val AGENT_MONITOR_REFRESH_INTERVAL_MILLIS = 15000L

private fun String.isRealConversationId(): Boolean = isNotBlank() && this != NO_CONVERSATION_ID

private fun AgentConversationGroup.displayName(): String =
    title.ifBlank { conversationId.takeIf { it.isRealConversationId() } ?: "未关联会话" }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AgentMonitorScreen(
    viewModel: AgentMonitorViewModel = viewModel(factory = AgentMonitorViewModel.Factory)
) {
    val conversationGroups by viewModel.conversationGroups.collectAsState()
    val loading by viewModel.loading.collectAsState()
    val uiState by viewModel.uiState.collectAsState()
    val statusFilter by viewModel.statusFilter.collectAsState()
    val totalMessage by viewModel.totalMessage.collectAsState()
    val summary = remember(conversationGroups) { buildAgentSummary(conversationGroups) }
    val expandedStates = remember { mutableStateMapOf<String, Boolean>() }

    LaunchedEffect(statusFilter) {
        while (true) {
            delay(AGENT_MONITOR_REFRESH_INTERVAL_MILLIS)
            viewModel.loadAgents()
        }
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "智能体监控",
                        style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold)
                    )
                },
                actions = {
                    IconButton(onClick = { viewModel.loadAgents() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "刷新")
                    }
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            )
        }
    ) { paddingValues ->
        Box(modifier = Modifier.fillMaxSize().padding(paddingValues)) {
            Column(modifier = Modifier.fillMaxSize()) {
                StatusFilterRow(
                    currentFilter = statusFilter,
                    onFilterChange = { viewModel.setStatusFilter(it) }
                )

                SummaryRow(summary = summary)

                if (totalMessage.isNotBlank()) {
                    Text(
                        totalMessage,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.55f),
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp)
                    )
                }

                if (loading && conversationGroups.isEmpty()) {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                } else if (conversationGroups.isEmpty()) {
                    EmptyAgentHint(Modifier.fillMaxSize())
                } else {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        items(conversationGroups, key = { it.conversationId }) { group ->
                            val groupKey = group.conversationId.ifBlank { NO_CONVERSATION_ID }
                            val expanded = expandedStates[groupKey] ?: true
                            ConversationGroupCard(
                                group = group,
                                expanded = expanded,
                                onExpandedChange = { expandedStates[groupKey] = !expanded },
                                onStop = { viewModel.stopAgent(it) },
                                onDelete = { viewModel.deleteAgent(it) }
                            )
                        }
                    }
                }
            }

            AnimatedVisibility(
                visible = uiState is UiState.Error,
                enter = fadeIn(),
                exit = fadeOut(),
                modifier = Modifier.align(Alignment.BottomCenter)
            ) {
                if (uiState is UiState.Error) {
                    Snackbar(
                        modifier = Modifier.padding(16.dp),
                        action = {
                            TextButton(onClick = { viewModel.clearError() }) {
                                Text("关闭")
                            }
                        }
                    ) {
                        Text((uiState as UiState.Error).message)
                    }
                }
            }
        }
    }
}

@Composable
private fun StatusFilterRow(currentFilter: String?, onFilterChange: (String?) -> Unit) {
    val filters = listOf(
        null to "全部",
        "running" to "运行中",
        "complete" to "已完成",
        "stopped" to "已停止",
        "error" to "错误"
    )
    LazyRow(
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        items(filters) { (value, label) ->
            FilterChip(
                selected = currentFilter == value,
                onClick = { onFilterChange(value) },
                label = { Text(label) },
                leadingIcon = if (value == "running") {
                    { Icon(Icons.Default.PlayArrow, contentDescription = null, modifier = Modifier.size(16.dp)) }
                } else null
            )
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun SummaryRow(summary: AgentMonitorSummary) {
    FlowRow(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        SummaryCard("会话", summary.conversationCount.toString())
        SummaryCard("Agent", summary.agentCount.toString())
        SummaryCard("运行中", summary.runningCount.toString(), valueColor = Color(0xFF16A34A))
        SummaryCard("输入 Token", formatTokenCount(summary.totalInputTokens))
        SummaryCard("输出 Token", formatTokenCount(summary.totalOutputTokens))
    }
}

@Composable
private fun SummaryCard(label: String, value: String, valueColor: Color = MaterialTheme.colorScheme.onSurface) {
    Surface(
        shape = RoundedCornerShape(14.dp),
        color = MaterialTheme.colorScheme.surface,
        tonalElevation = 2.dp
    ) {
        Column(modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp)) {
            Text(
                text = label,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.55f)
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = value,
                style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold),
                color = valueColor
            )
        }
    }
}

@Composable
private fun ConversationGroupCard(
    group: AgentConversationGroup,
    expanded: Boolean,
    onExpandedChange: () -> Unit,
    onStop: (String) -> Unit,
    onDelete: (String) -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable(onClick = onExpandedChange)
                    .padding(horizontal = 16.dp, vertical = 14.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = group.displayName(),
                        style = MaterialTheme.typography.bodyLarge.copy(fontWeight = FontWeight.SemiBold),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        ConversationStatusBadge(hasRunning = group.hasRunning)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "${group.agents.size} 个 Agent",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.55f)
                        )
                    }
                    if (group.conversationId.isRealConversationId()) {
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = "会话 ID：${group.conversationId}",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.45f),
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                }
                Icon(
                    if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                    contentDescription = if (expanded) "收起" else "展开",
                    tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                )
            }

            AnimatedVisibility(
                visible = expanded,
                enter = expandVertically() + fadeIn(),
                exit = shrinkVertically() + fadeOut()
            ) {
                Column {
                    HorizontalDivider()
                    Column(
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        group.agents.forEach { agent ->
                            AgentCard(
                                agent = agent,
                                onStop = { onStop(agent.agentId) },
                                onDelete = { onDelete(agent.agentId) }
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ConversationStatusBadge(hasRunning: Boolean) {
    Surface(
        shape = RoundedCornerShape(999.dp),
        color = if (hasRunning) Color(0xFFDCFCE7) else MaterialTheme.colorScheme.surfaceVariant
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .background(
                        color = if (hasRunning) Color(0xFF22C55E) else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.3f),
                        shape = CircleShape
                    )
            )
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = if (hasRunning) "运行中" else "空闲",
                style = MaterialTheme.typography.labelSmall,
                color = if (hasRunning) Color(0xFF15803D) else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
            )
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun AgentCard(
    agent: AgentInfo,
    onStop: () -> Unit,
    onDelete: () -> Unit
) {
    var showDeleteConfirm by remember { mutableStateOf(false) }
    var showStopConfirm by remember { mutableStateOf(false) }

    if (showDeleteConfirm) {
        AlertDialog(
            onDismissRequest = { showDeleteConfirm = false },
            title = { Text("删除记录") },
            text = { Text("确定要删除此 Agent 记录吗？") },
            confirmButton = {
                TextButton(
                    onClick = { showDeleteConfirm = false; onDelete() },
                    colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error)
                ) { Text("删除") }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteConfirm = false }) { Text("取消") }
            }
        )
    }

    if (showStopConfirm) {
        AlertDialog(
            onDismissRequest = { showStopConfirm = false },
            title = { Text("停止 Agent") },
            text = { Text("确定要停止此 Agent 吗？") },
            confirmButton = {
                TextButton(
                    onClick = { showStopConfirm = false; onStop() },
                    colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error)
                ) { Text("停止") }
            },
            dismissButton = {
                TextButton(onClick = { showStopConfirm = false }) { Text("取消") }
            }
        )
    }

    Surface(
        shape = RoundedCornerShape(14.dp),
        color = MaterialTheme.colorScheme.background,
        tonalElevation = 1.dp
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                StatusBadge(status = agent.status)
                Spacer(modifier = Modifier.width(8.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = agent.modelName.ifBlank { "未知模型" },
                        style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.SemiBold)
                    )
                    if (agent.taskText.isNotBlank()) {
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(
                            text = agent.taskText,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                }
                if (agent.status == "running") {
                    IconButton(onClick = { showStopConfirm = true }) {
                        Icon(
                            Icons.Default.Stop,
                            contentDescription = "停止",
                            tint = MaterialTheme.colorScheme.error
                        )
                    }
                } else {
                    IconButton(onClick = { showDeleteConfirm = true }) {
                        Icon(
                            Icons.Default.Delete,
                            contentDescription = "删除",
                            tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.45f)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            if (agent.maxIterations > 0) {
                IterationProgressRow(
                    current = agent.currentIteration,
                    max = agent.maxIterations
                )
                Spacer(modifier = Modifier.height(10.dp))
            }

            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                AgentMetaChip("耗时", formatElapsedTime(agent.elapsedTime))
                AgentMetaChip("输入", formatTokenCount(agent.totalInputTokens))
                AgentMetaChip("输出", formatTokenCount(agent.totalOutputTokens))
                if (agent.modul.isNotBlank()) AgentMetaChip("模式", agent.modul)
                if (agent.userName.isNotBlank()) AgentMetaChip("用户", agent.userName)
            }

            Spacer(modifier = Modifier.height(10.dp))
            HorizontalDivider()
            Spacer(modifier = Modifier.height(8.dp))

            AgentInfoRow("Agent ID", agent.agentId)
            if (agent.chatId.isNotBlank()) AgentInfoRow("Chat ID", agent.chatId)
            if (agent.conversationId.isNotBlank()) AgentInfoRow("会话 ID", agent.conversationId)
            if (agent.updatedAt.isNotBlank()) AgentInfoRow("更新时间", agent.updatedAt.take(19).replace("T", " "))
        }
    }
}

@Composable
private fun StatusBadge(status: String) {
    val (bg, fg) = when (status) {
        "running" -> Color(0xFFDCFCE7) to Color(0xFF15803D)
        "complete" -> MaterialTheme.colorScheme.primaryContainer to MaterialTheme.colorScheme.onPrimaryContainer
        "stopped" -> Color(0xFFFEF3C7) to Color(0xFFB45309)
        "error" -> MaterialTheme.colorScheme.errorContainer to MaterialTheme.colorScheme.onErrorContainer
        "init" -> Color(0xFFDBEAFE) to Color(0xFF1D4ED8)
        else -> MaterialTheme.colorScheme.surfaceVariant to MaterialTheme.colorScheme.onSurfaceVariant
    }
    Surface(shape = RoundedCornerShape(999.dp), color = bg) {
        Text(
            text = statusLabel(status),
            style = MaterialTheme.typography.labelSmall,
            color = fg,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp)
        )
    }
}

@Composable
private fun IterationProgressRow(current: Int, max: Int) {
    val progress = (current.toFloat() / max.toFloat()).coerceIn(0f, 1f)
    Column {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                "迭代进度",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.55f)
            )
            Text(
                "$current/$max",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
            )
        }
        Spacer(modifier = Modifier.height(6.dp))
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(6.dp)
                .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(999.dp))
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth(progress)
                    .height(6.dp)
                    .background(MaterialTheme.colorScheme.primary, RoundedCornerShape(999.dp))
            )
        }
    }
}

@Composable
private fun AgentMetaChip(label: String, value: String) {
    Surface(
        shape = RoundedCornerShape(10.dp),
        color = MaterialTheme.colorScheme.surfaceVariant
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "$label：",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.65f)
            )
            Text(
                text = value,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun AgentInfoRow(label: String, value: String) {
    Row(modifier = Modifier.padding(vertical = 2.dp)) {
        Text(
            "$label: ",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
            modifier = Modifier.width(72.dp)
        )
        Text(
            value,
            style = MaterialTheme.typography.labelSmall,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis
        )
    }
}

private fun statusLabel(status: String): String = when (status) {
    "running" -> "运行中"
    "complete" -> "已完成"
    "stopped" -> "已停止"
    "error" -> "错误"
    "init" -> "初始化"
    else -> status
}

internal data class AgentMonitorSummary(
    val conversationCount: Int,
    val agentCount: Int,
    val runningCount: Int,
    val totalInputTokens: Long,
    val totalOutputTokens: Long
)

internal fun buildAgentSummary(groups: List<AgentConversationGroup>): AgentMonitorSummary {
    val agents = groups.flatMap { it.agents }
    return AgentMonitorSummary(
        conversationCount = groups.size,
        agentCount = agents.size,
        runningCount = agents.count { it.status == "running" },
        totalInputTokens = agents.sumOf { it.totalInputTokens },
        totalOutputTokens = agents.sumOf { it.totalOutputTokens }
    )
}

internal fun formatElapsedTime(seconds: Double): String {
    val totalSeconds = seconds.roundToInt().coerceAtLeast(0)
    val hours = totalSeconds / 3600
    val minutes = (totalSeconds % 3600) / 60
    val secs = totalSeconds % 60
    return when {
        hours > 0 -> "${hours}h ${minutes}m"
        minutes > 0 -> "${minutes}m ${secs}s"
        else -> "${secs}s"
    }
}

private fun formatScaledWithOneDecimal(value: Long, divisor: Long, suffix: String): String {
    // Round to one decimal place using integer arithmetic to avoid floating-point drift.
    val scaledTimesTen = (value * 10L + divisor / 2) / divisor
    val whole = scaledTimesTen / 10
    val decimal = scaledTimesTen % 10
    return "$whole.$decimal$suffix"
}

internal fun formatTokenCount(value: Long): String = when {
    value >= 1_000_000L -> formatScaledWithOneDecimal(value, 1_000_000L, "M")
    value >= 1_000L -> formatScaledWithOneDecimal(value, 1_000L, "K")
    else -> value.toString()
}

@Composable
private fun EmptyAgentHint(modifier: Modifier) {
    Box(modifier = modifier, contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(
                Icons.Default.SmartToy,
                contentDescription = null,
                modifier = Modifier.size(64.dp),
                tint = MaterialTheme.colorScheme.primary.copy(alpha = 0.2f)
            )
            Spacer(modifier = Modifier.height(16.dp))
            Text("暂无 Agent 记录", style = MaterialTheme.typography.bodyLarge)
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                "按会话展示的 Agent 状态会显示在这里",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
            )
        }
    }
}
