package com.proteus.ai.ui

import androidx.compose.animation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.proteus.ai.api.model.KnowledgeBaseItem
import com.proteus.ai.ui.viewmodel.KnowledgeBaseViewModel
import com.proteus.ai.ui.viewmodel.UiState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun KnowledgeBaseScreen(
    viewModel: KnowledgeBaseViewModel = viewModel(factory = KnowledgeBaseViewModel.Factory)
) {
    val items by viewModel.items.collectAsState()
    val loading by viewModel.loading.collectAsState()
    val uiState by viewModel.uiState.collectAsState()
    val showAddDialog by viewModel.showAddDialog.collectAsState()
    val selectedItem by viewModel.selectedItem.collectAsState()
    val inDetailMode = selectedItem != null
    var showDetailDeleteConfirm by remember { mutableStateOf(false) }

    if (showAddDialog) {
        AddKnowledgeBaseDialog(
            onDismiss = { viewModel.hideAddDialog() },
            onConfirm = { content -> viewModel.saveItem(content) }
        )
    }

    if (showDetailDeleteConfirm) {
        selectedItem?.let { detailItem ->
            AlertDialog(
                onDismissRequest = { showDetailDeleteConfirm = false },
                title = { Text("删除条目") },
                text = { Text("确定要删除「${detailItem.title.takeIf { it.isNotBlank() } ?: "此条目"}」吗？") },
                confirmButton = {
                    TextButton(
                        onClick = {
                            showDetailDeleteConfirm = false
                            viewModel.deleteItem(detailItem.id)
                        },
                        colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error)
                    ) { Text("删除") }
                },
                dismissButton = {
                    TextButton(onClick = { showDetailDeleteConfirm = false }) { Text("取消") }
                }
            )
        }
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            CenterAlignedTopAppBar(
                navigationIcon = {
                    if (inDetailMode) {
                        IconButton(onClick = { viewModel.hideDetailDialog() }) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回列表")
                        }
                    }
                },
                title = {
                    Text(
                        selectedItem?.title?.ifBlank { "条目详情" } ?: "知识库",
                        style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold)
                    )
                },
                actions = {
                    if (inDetailMode && selectedItem != null) {
                        IconButton(onClick = { showDetailDeleteConfirm = true }) {
                            Icon(Icons.Default.Delete, contentDescription = "删除条目")
                        }
                    } else {
                        TextButton(onClick = { viewModel.showAddDialog() }) {
                            Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("添加条目")
                        }
                        IconButton(onClick = { viewModel.loadList() }) {
                            Icon(Icons.Default.Refresh, contentDescription = "刷新")
                        }
                    }
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            )
        }
    ) { paddingValues ->
        Box(modifier = Modifier.fillMaxSize().padding(paddingValues)) {
            if (loading && items.isEmpty() && !inDetailMode) {
                CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
            } else if (inDetailMode && selectedItem != null) {
                KnowledgeBaseDetailContent(
                    item = selectedItem,
                    modifier = Modifier.fillMaxSize()
                )
            } else if (items.isEmpty()) {
                EmptyKnowledgeBaseHint(Modifier.align(Alignment.Center)) {
                    viewModel.showAddDialog()
                }
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(items, key = { it.id }) { item ->
                        KnowledgeBaseItemCard(
                            item = item,
                            onClick = { viewModel.loadItemDetail(item.id) },
                            onDelete = { viewModel.deleteItem(item.id) }
                        )
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
private fun KnowledgeBaseItemCard(
    item: KnowledgeBaseItem,
    onClick: () -> Unit,
    onDelete: () -> Unit
) {
    var showDeleteConfirm by remember { mutableStateOf(false) }

    if (showDeleteConfirm) {
        AlertDialog(
            onDismissRequest = { showDeleteConfirm = false },
            title = { Text("删除条目") },
            text = { Text("确定要删除「${item.title.ifBlank { "此条目" }}」吗？") },
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

    Card(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                Icons.Default.Book,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(24.dp)
            )
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = item.title.ifBlank { "未命名条目" },
                    style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.SemiBold),
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = item.updatedAt.take(10),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                )
            }
            IconButton(onClick = { showDeleteConfirm = true }) {
                Icon(
                    Icons.Default.Delete,
                    contentDescription = "删除",
                    tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.4f)
                )
            }
        }
    }
}

@Composable
private fun EmptyKnowledgeBaseHint(modifier: Modifier, onAddClick: () -> Unit) {
    Column(modifier = modifier, horizontalAlignment = Alignment.CenterHorizontally) {
        Icon(
            Icons.Default.LibraryBooks,
            contentDescription = null,
            modifier = Modifier.size(64.dp),
            tint = MaterialTheme.colorScheme.primary.copy(alpha = 0.2f)
        )
        Spacer(modifier = Modifier.height(16.dp))
        Text("知识库为空", style = MaterialTheme.typography.bodyLarge)
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            "点击添加条目创建知识内容",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
        )
        Spacer(modifier = Modifier.height(24.dp))
        Button(onClick = onAddClick, shape = RoundedCornerShape(12.dp)) {
            Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.size(18.dp))
            Spacer(modifier = Modifier.width(8.dp))
            Text("添加条目")
        }
    }
}

@Composable
private fun AddKnowledgeBaseDialog(onDismiss: () -> Unit, onConfirm: (String) -> Unit) {
    var content by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("添加知识条目") },
        text = {
            OutlinedTextField(
                value = content,
                onValueChange = { content = it },
                placeholder = { Text("输入内容（支持 Markdown）") },
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 120.dp),
                maxLines = 10,
                shape = RoundedCornerShape(8.dp)
            )
        },
        confirmButton = {
            Button(
                onClick = { if (content.isNotBlank()) onConfirm(content) },
                enabled = content.isNotBlank()
            ) { Text("保存") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("取消") }
        }
    )
}

@Composable
private fun KnowledgeBaseDetailContent(
    item: KnowledgeBaseItem,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 12.dp)
    ) {
        Card(
            shape = RoundedCornerShape(16.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(
                    "更新时间：${item.updatedAt.take(19).replace("T", " ")}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                )
                if (item.author.isNotBlank()) {
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        "作者：${item.author}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                    )
                }
                Spacer(modifier = Modifier.height(12.dp))
                Text(
                    item.content ?: "（内容为空）",
                    style = MaterialTheme.typography.bodyMedium
                )
            }
        }
    }
}
