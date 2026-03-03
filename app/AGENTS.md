# Proteus AI Android 客户端 — AI 智能体开发指南

本文档为 AI 编码智能体提供在 `app/` 目录（Android 客户端）中工作所需的关键信息。

## 项目概述

`app/` 是 Proteus AI 的 Android 客户端，基于 **Kotlin + Jetpack Compose + Material Design 3** 构建，通过 Retrofit 与后端 REST API 通信，通过 OkHttp 接收 SSE（Server-Sent Events）流式响应。

- **最低 SDK**：API 24
- **目标 SDK**：API 34
- **编译 SDK**：API 34
- **JDK**：17
- **Kotlin**：1.9.24
- **Compose Compiler**：1.5.14

## 构建与测试命令

```bash
# 进入 app 目录
cd app

# 编译调试版 APK
./gradlew assembleDebug

# 编译发布版 APK（需配置签名密钥）
./gradlew assembleRelease

# 运行单元测试
./gradlew test

# 运行所有检查（lint + 测试）
./gradlew check

# 清理构建产物
./gradlew clean
```

生成的 APK 位于 `app/build/outputs/apk/debug/app-debug.apk`。

## 代码结构

```
app/src/main/java/com/proteus/ai/
├── MainActivity.kt              # 应用入口 Activity
├── ProteusAIApplication.kt      # Application 类（Timber 日志初始化）
├── api/
│   ├── ApiClient.kt             # Retrofit/OkHttp 客户端单例，BASE_URL 配置在此
│   ├── ApiService.kt            # Retrofit 接口定义（REST 端点）
│   └── model/                   # 数据模型（请求/响应 DTO）
│       ├── Conversation.kt
│       ├── ConversationDetail.kt
│       ├── ModelsResponse.kt
│       ├── SseEvent.kt
│       ├── StopTaskRequest.kt
│       ├── StopTaskResponse.kt
│       └── SubmitTaskRequest.kt
├── repository/
│   ├── ChatRepository.kt        # 消息发送、SSE 流式读取
│   └── ConversationRepository.kt# 会话列表加载
├── storage/
│   └── TokenManager.kt          # DataStore 持久化 Bearer Token
└── ui/
    ├── MainScreen.kt            # 主界面（侧边栏 + 聊天区域）
    ├── viewmodel/
    │   └── MainViewModel.kt     # 状态管理，持有 ViewModel
    ├── components/
    │   ├── ConversationList.kt  # 侧边栏会话列表组件
    │   ├── MessageList.kt       # 聊天消息列表（含 Markdown 渲染）
    │   ├── MermaidWebView.kt    # Mermaid 图表渲染组件
    │   └── TokenDialog.kt       # Token 设置弹窗
    └── theme/
        ├── Theme.kt             # Material 3 主题配置
        └── Typography.kt        # 字体排版配置
```

## API 端点说明

客户端对接以下后端接口（`ApiService.kt`）：

| 端点 | 方法 | 说明 |
|------|------|------|
| `GET conversations` | GET | 获取会话列表 |
| `GET conversations/{id}` | GET | 获取会话详情 |
| `GET models` | GET | 获取可用模型列表 |
| `POST submit_task` | POST | 提交用户查询任务 |
| `GET stream/blocking/{chat_id}` | GET (SSE) | 实时接收 AI 回复流 |
| `GET replay/stream/{chat_id}` | GET (SSE) | 回放历史会话流 |
| `POST stop` | POST | 停止当前任务 |

默认 API 地址（`ApiClient.kt`）：
- Debug：`http://10.0.2.2:8888/`（模拟器访问本机）
- Release：`https://api.proteus-ai.com/`

## 任务提交参数

`SubmitTaskRequest` 包含以下字段，对应后端 `/submit_task` 接口：

| 字段 | 类型 | 说明 |
|------|------|------|
| `query` | String | 用户输入的问题或指令 |
| `modul` | String | 模式，固定为 `"chat"` |
| `chatId` | String | 当前聊天唯一 ID |
| `conversationId` | String? | 关联的会话 ID（可空） |
| `deepResearch` | Boolean | 是否启用深度研究模式 |
| `webSearch` | Boolean | 是否启用网络搜索 |
| `skillCall` | Boolean | 是否启用技能调用 |

## 关键注意事项

1. **Token 鉴权**：所有 API 请求通过 `Authorization: Bearer <token>` 头鉴权，Token 存储在 `DataStore` 中。
2. **SSE 流式解析**：`ChatRepository.streamChatBlocking()` 使用 OkHttp + Okio 逐行解析 `data:` 字段，解析为 `SseEvent`。
3. **Markdown 渲染**：消息列表使用 `compose-richtext` + `commonmark 0.21.0` 渲染 Markdown，已排除冲突的 `atlassian.commonmark`。
4. **Mermaid 图表**：`MermaidWebView` 通过 Android `WebView` 渲染 Mermaid 流程图。
5. **BASE_URL 修改**：如需连接自定义服务器，修改 `ApiClient.kt` 中的 `BASE_URL` 常量，或在 `build.gradle.kts` 的 `buildConfigField` 中覆盖。
