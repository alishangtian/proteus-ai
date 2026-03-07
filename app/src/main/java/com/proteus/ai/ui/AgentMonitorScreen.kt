package com.proteus.ai.ui

import androidx.compose.animation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.proteus.ai.api.model.AgentInfo
import com.proteus.ai.ui.viewmodel.AgentMonitorViewModel
import com.proteus.ai.ui.viewmodel.UiState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AgentMonitorScreen(
    viewModel: AgentMonitorViewModel = viewModel(factory = AgentMonitorViewModel.Factory)
) {
    val agents by viewModel.agents.collectAsState()
    val loading by viewModel.loading.collectAsState()
    val uiState by viewModel.uiState.collectAsState()
    val statusFilter by viewModel.statusFilter.collectAsState()
    val totalMessage by viewModel.totalMessage.collectAsState()

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "Agent 监控",
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
                ),
                modifier = Modifier.windowInsetsPadding(WindowInsets.statusBars)
            )
        }
    ) { paddingValues ->
        Box(modifier = Modifier.fillMaxSize().padding(paddingValues)) {
            Column(modifier = Modifier.fillMaxSize()) {
                // Status filter chips
                StatusFilterRow(
                    currentFilter = statusFilter,
                    onFilterChange = { viewModel.setStatusFilter(it) }
                )

                if (totalMessage.isNotBlank()) {
                    Text(
                        totalMessage,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f),
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp)
                    )
                }

                if (loading && agents.isEmpty()) {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                } else if (agents.isEmpty()) {
                    EmptyAgentHint(Modifier.fillMaxSize())
                } else {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        items(agents, key = { it.agentId }) { agent ->
                            AgentCard(
                                agent = agent,
                                onStop = { viewModel.stopAgent(agent.agentId) },
                                onDelete = { viewModel.deleteAgent(agent.agentId) }
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

@Composable
private fun AgentCard(
    agent: AgentInfo,
    onStop: () -> Unit,
    onDelete: () -> Unit
) {
    var showDeleteConfirm by remember { mutableStateOf(false) }
    var showStopConfirm by remember { mutableStateOf(false) }
    var expanded by remember { mutableStateOf(false) }

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

    Card(
        onClick = { expanded = !expanded },
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                StatusIndicator(status = agent.status)
                Spacer(modifier = Modifier.width(8.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = agent.agentId.take(20) + if (agent.agentId.length > 20) "…" else "",
                        style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.SemiBold),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    Text(
                        text = statusLabel(agent.status),
                        style = MaterialTheme.typography.labelSmall,
                        color = statusColor(agent.status)
                    )
                }
                Row {
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
                                tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.4f)
                            )
                        }
                    }
                    IconButton(onClick = { expanded = !expanded }) {
                        Icon(
                            if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                            contentDescription = if (expanded) "收起" else "展开"
                        )
                    }
                }
            }

            AnimatedVisibility(visible = expanded) {
                Column(modifier = Modifier.padding(top = 8.dp)) {
                    HorizontalDivider()
                    Spacer(modifier = Modifier.height(8.dp))
                    AgentInfoRow("Agent ID", agent.agentId)
                    AgentInfoRow("Chat ID", agent.chatId)
                    if (agent.conversationId.isNotBlank()) AgentInfoRow("会话 ID", agent.conversationId)
                    if (agent.userName.isNotBlank()) AgentInfoRow("用户", agent.userName)
                    if (agent.modelName.isNotBlank()) AgentInfoRow("模型", agent.modelName)
                    if (agent.modul.isNotBlank()) AgentInfoRow("模式", agent.modul)
                    if (agent.updatedAt.isNotBlank()) AgentInfoRow("更新时间", agent.updatedAt.take(19).replace("T", " "))
                }
            }
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

@Composable
private fun StatusIndicator(status: String) {
    val color = statusColor(status)
    Surface(
        modifier = Modifier.size(10.dp),
        shape = RoundedCornerShape(50),
        color = color
    ) {}
}

@Composable
private fun statusColor(status: String): Color = when (status) {
    "running" -> Color(0xFF4CAF50)
    "complete" -> MaterialTheme.colorScheme.primary
    "stopped" -> MaterialTheme.colorScheme.onSurface.copy(alpha = 0.4f)
    "error" -> MaterialTheme.colorScheme.error
    else -> MaterialTheme.colorScheme.onSurface.copy(alpha = 0.3f)
}

private fun statusLabel(status: String): String = when (status) {
    "running" -> "运行中"
    "complete" -> "已完成"
    "stopped" -> "已停止"
    "error" -> "错误"
    "init" -> "初始化"
    else -> status
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
                "Agent 运行后将在此显示",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
            )
        }
    }
}
