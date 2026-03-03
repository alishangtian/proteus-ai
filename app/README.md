# Proteus AI Android 客户端

[![Android](https://img.shields.io/badge/Android-API%2024%2B-green)](https://developer.android.com/)
[![Kotlin](https://img.shields.io/badge/Kotlin-1.9.24-blue)](https://kotlinlang.org/)
[![Jetpack Compose](https://img.shields.io/badge/Jetpack%20Compose-2024.10-brightgreen)](https://developer.android.com/jetpack/compose)
[![Material Design 3](https://img.shields.io/badge/Material%20Design-3-purple)](https://m3.material.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)

Proteus AI 的官方 Android 客户端，让你随时随地通过手机使用强大的 AI 智能体服务。基于 **Kotlin + Jetpack Compose + Material Design 3** 构建，通过 SSE 实时流式接收 AI 回复。

---

## 📱 界面预览

应用主界面分为三个核心区域：

```
┌─────────────────────────────────────────┐
│  🔲 Proteus AI               ⚙️ 设置    │  ← 顶部导航栏
├────────────┬────────────────────────────┤
│            │                            │
│  📋 会话   │   💬 聊天消息区域           │
│  历史列表  │                            │
│            │   [AI 思考过程卡片]         │
│  对话1     │   [工具调用卡片]            │
│  对话2     │   ┌──────────────────────┐ │
│  对话3     │   │ AI 回复 (支持 MD)    │ │
│  ...       │   └──────────────────────┘ │
│            │             [用户消息气泡] │
│  ＋ 新对话 ├────────────────────────────┤
│            │ [🌐深研][🔍搜索][🛠技能]  │
│            │ ┌──────────────────────┐  │
│            │ │  输入问题...      ➤  │  │  ← 输入区域
│            │ └──────────────────────┘  │
└────────────┴────────────────────────────┘
     ↑ 侧边栏（可折叠）
```

---

## ✨ 功能特性

### 🗨️ 智能对话
- **实时流式回复**：通过 SSE (Server-Sent Events) 实时显示 AI 回复，无需等待全部生成
- **Markdown 渲染**：AI 回复支持富文本格式（标题、代码块、列表、表格等）
- **Mermaid 图表**：自动渲染流程图、时序图等 Mermaid 图表
- **思考过程展示**：可折叠的"思考过程"卡片，直观展示 AI 推理链路
- **工具调用可视化**：实时显示 AI 调用工具（搜索、代码执行等）的过程和结果

### 🚀 三种增强模式（发送消息时可独立开启）

| 模式 | 图标 | 说明 |
|------|------|------|
| **深度研究** | 🌐 | 对指定主题进行系统性深度研究，自动搜索、整理、分析多方信息 |
| **网络搜索** | 🔍 | 启用实时联网搜索，获取最新信息 |
| **技能调用** | 🛠️ | 启用预定义技能，完成专业领域任务 |

### 📋 会话管理
- **会话历史**：侧边栏展示所有历史对话，支持点击切换
- **历史回放**：选择历史会话后自动加载并回放完整对话记录
- **新建对话**：一键开始全新对话

### ⚙️ 其他功能
- **Token 管理**：首次使用时配置 Bearer Token，安全存储在本地
- **停止任务**：AI 回复过程中可随时点击停止按钮中断
- **错误提示**：网络异常或接口错误时展示友好提示，支持重试
- **深色/浅色主题**：自动跟随系统主题切换

---

## 🚀 快速开始

### 第一步：确保后端服务已启动

Android 客户端需要连接 Proteus AI 后端服务。请先按照[项目根目录 README](../README.md) 启动后端服务。

服务默认监听：
- **本机服务器（模拟器专用）**：`http://10.0.2.2:8888/`（Android 模拟器内访问开发机本地服务的专用地址）
- **真机访问**：需将手机和电脑连接同一局域网，使用电脑实际局域网 IP，例如 `http://192.168.1.100:8888/`（请替换为你的实际 IP）

### 第二步：编译并安装应用

#### 方法一：Android Studio（推荐新手）

1. 下载并安装 [Android Studio](https://developer.android.com/studio)（推荐 2023.3 Hedgehog 或更高版本）
2. 打开 Android Studio → **File** → **Open**，选择 `proteus-ai/app` 文件夹
3. 等待 Gradle 同步完成（首次可能需要几分钟下载依赖）
4. 连接 Android 手机（开启 USB 调试）或在 AVD Manager 中启动模拟器
5. 点击工具栏 ▶️ **Run** 按钮，或使用快捷键 `Shift+F10`

#### 方法二：命令行编译

**前提条件：**
- JDK 17+
- Android SDK（可通过 Android Studio 安装，或下载 [Command Line Tools](https://developer.android.com/studio#command-tools)）
- 设置环境变量 `ANDROID_HOME`

```bash
# 进入 app 目录
cd proteus-ai/app

# 编译调试版 APK（macOS/Linux）
./gradlew assembleDebug

# 编译调试版 APK（Windows）
gradlew.bat assembleDebug
```

APK 输出路径：`app/build/outputs/apk/debug/app-debug.apk`

通过 adb 安装到手机：
```bash
adb install app/build/outputs/apk/debug/app-debug.apk
```

### 第三步：配置 API 地址（连接自己的服务器）

应用默认 API 地址为 `http://10.0.2.2:8888/`（模拟器访问本机专用）。

**如果使用真机或自定义服务器，修改 `app/build.gradle.kts`：**

```kotlin
defaultConfig {
    // 将此处改为你的服务器地址
    buildConfigField("String", "BASE_URL", "\"http://192.168.1.100:8888/\"")
}
```

修改后重新编译即可生效。注意将 `192.168.1.100` 替换为你的电脑实际局域网 IP。

### 第四步：首次使用

1. 安装并启动应用后，若未配置 Token 会自动弹出设置对话框
2. 输入你的 **Bearer Token**（从 Proteus AI 后端服务获取）
3. 点击确认后，应用自动加载历史会话列表
4. 在底部输入框输入问题，点击 ➤ 发送即可开始对话

> **如何获取 Token？**  
> Token 由 Proteus AI 后端服务的认证模块生成。部署后端时，`SECRET_KEY`（见 `proteus/docker/volumes/agent/.env.example`）用于签发 JWT Token；请使用后端认证接口（如登录接口）换取实际的 JWT Token 或 API Key，再填入此处。

---

## ⚙️ 配置说明

### API 地址配置

| 场景 | 默认地址 | 修改方式 |
|------|---------|---------|
| Android 模拟器访问本机 | `http://10.0.2.2:8888/` | `build.gradle.kts` 中的 `BASE_URL`（defaultConfig 块） |
| Release 正式版 | 自定义（示例：`https://your-server.com/`） | `build.gradle.kts` 中的 `BASE_URL`（release 块） |
| 局域网真机调试 | 自定义 | 修改 `build.gradle.kts` 的 `defaultConfig` 中的 `BASE_URL` |

### 签名配置（发布应用时）

1. 生成签名密钥：

```bash
keytool -genkey -v -keystore my-release-key.jks \
  -keyalg RSA -keysize 2048 -validity 10000 -alias my-alias
```

2. 在 `app/build.gradle.kts` 中配置签名：

```kotlin
signingConfigs {
    create("release") {
        storeFile = file("my-release-key.jks")
        storePassword = "your_password"
        keyAlias = "my-alias"
        keyPassword = "your_password"
    }
}
buildTypes {
    release {
        signingConfig = signingConfigs.getByName("release")
        isMinifyEnabled = true
        isShrinkResources = true
        proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
    }
}
```

3. 执行发布构建：

```bash
./gradlew assembleRelease
# APK 位于：app/build/outputs/apk/release/app-release.apk

# 或生成 AAB（用于上传 Google Play）
./gradlew bundleRelease
# AAB 位于：app/build/outputs/bundle/release/app-release.aab
```

---

## 🏗️ 项目结构

```
app/src/main/java/com/proteus/ai/
├── MainActivity.kt              # 应用入口 Activity
├── ProteusAIApplication.kt      # Application 类（日志初始化）
├── api/
│   ├── ApiClient.kt             # Retrofit/OkHttp 客户端，BASE_URL 在此
│   ├── ApiService.kt            # REST 接口定义
│   └── model/                   # 数据模型
│       ├── Conversation.kt      # 会话列表模型
│       ├── ConversationDetail.kt# 会话详情模型
│       ├── SseEvent.kt          # SSE 事件模型（思考、工具、消息等）
│       ├── SubmitTaskRequest.kt # 任务提交请求体
│       ├── StopTaskRequest.kt   # 停止任务请求体
│       └── ModelsResponse.kt    # 模型列表响应
├── repository/
│   ├── ChatRepository.kt        # 消息发送、SSE 流式读取
│   └── ConversationRepository.kt# 会话列表加载
├── storage/
│   └── TokenManager.kt          # DataStore 持久化 Bearer Token
└── ui/
    ├── MainScreen.kt            # 主界面（侧边栏 + 聊天区域 + 输入框）
    ├── viewmodel/
    │   └── MainViewModel.kt     # 状态管理（消息、会话、流式状态等）
    ├── components/
    │   ├── ConversationList.kt  # 侧边栏会话列表
    │   ├── MessageList.kt       # 消息列表（气泡 + Markdown + 工具卡片）
    │   ├── MermaidWebView.kt    # Mermaid 图表渲染（WebView）
    │   └── TokenDialog.kt       # Token 设置弹窗
    └── theme/
        ├── Theme.kt             # Material 3 主题配置
        └── Typography.kt        # 字体排版配置
```

### 核心技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Kotlin | 1.9.24 | 主开发语言 |
| Jetpack Compose | BOM 2024.10 | 声明式 UI 框架 |
| Material Design 3 | — | UI 组件库 |
| Retrofit | 2.11.0 | HTTP 请求 |
| OkHttp | 4.12.0 | SSE 流式读取 |
| DataStore | 1.1.1 | Token 本地持久化 |
| compose-richtext | 0.16.0 | Markdown 渲染 |
| Coroutines | 1.8.1 | 异步编程 |
| Timber | 5.0.1 | 日志 |

---

## 🔌 对接的后端接口

客户端与以下后端接口通信（详见 `ApiService.kt`）：

| 接口 | 方法 | 说明 |
|------|------|------|
| `GET /conversations` | REST | 获取会话列表 |
| `GET /conversations/{id}` | REST | 获取会话详情（含 chatId 列表） |
| `GET /models` | REST | 获取可用模型列表 |
| `POST /submit_task` | REST | 提交对话任务（触发 AI 处理） |
| `GET /stream/blocking/{chat_id}` | SSE | 实时接收 AI 回复流 |
| `GET /replay/stream/{chat_id}` | SSE | 回放历史会话 |
| `POST /stop` | REST | 停止当前任务 |

### 任务提交参数（`/submit_task`）

| 字段 | 类型 | 说明 |
|------|------|------|
| `query` | String | 用户输入的问题 |
| `modul` | String | 固定为 `"chat"` |
| `chat_id` | String | 当前对话唯一 ID |
| `conversation_id` | String | 会话 ID（用于多轮对话） |
| `deep_research` | Boolean | 是否启用深度研究模式 |
| `web_search` | Boolean | 是否启用网络搜索 |
| `skill_call` | Boolean | 是否启用技能调用 |

---

## 🛠️ 常见问题

### Q：应用提示"请先配置 Token"怎么办？
点击右上角 ⚙️ 设置图标，在弹出对话框中输入 Bearer Token 并保存。Token 由部署的 Proteus AI 后端生成。

### Q：会话列表加载失败怎么办？
1. 确认手机能访问后端服务（可用浏览器访问 `http://<服务器IP>:8888/health`）
2. 确认 Token 正确
3. 若使用模拟器，确认使用 `10.0.2.2` 而非 `localhost` 或 `127.0.0.1`
4. 若使用真机，需将 `BASE_URL` 改为局域网 IP

### Q：AI 回复一直在转圈不显示内容？
检查后端服务是否正常运行，SSE 流式接口（`/stream/blocking/{chat_id}`）是否可访问。

### Q：如何修改默认模型？
在 `SubmitTaskRequest.kt` 中修改 `modelName` 字段的默认值：
```kotlin
val modelName: String? = "deepseek-chat"  // 改为你需要的模型
```

### Q：真机无法连接本地服务器？

1. 确保手机和电脑连接**同一局域网**
2. 修改 `build.gradle.kts` 中的 `BASE_URL` 为电脑的局域网 IP（如 `http://192.168.1.100:8888/`，请替换为实际 IP）
3. 重新编译并安装应用

> ⚠️ **注意**：Android 9 (API 28) 及以上默认禁止明文 HTTP 请求。如访问 `http://` 地址时遇到连接失败，需在 `app/src/main/AndroidManifest.xml` 的 `<application>` 标签中添加：
> ```xml
> android:usesCleartextTraffic="true"
> ```
> 或配置 Network Security Config 仅允许特定域名使用明文传输。

---

## 📋 编译要求

| 环境 | 要求 |
|------|------|
| Android Studio | 2023.3 (Hedgehog) 或更高 |
| JDK | 17+ |
| Android SDK | API 34 |
| 最低支持 Android 版本 | Android 7.0 (API 24) |
| 目标 Android 版本 | Android 14 (API 34) |

---

## 🔮 后续扩展建议

1. **文件上传**：扩展 `/submit_task` 接口，支持图片、文档等附件
2. **离线缓存**：使用 Room 数据库缓存会话和消息，支持离线查看
3. **推送通知**：集成 FCM，支持后台任务完成提醒
4. **语音输入**：接入 Android 语音识别 API，支持语音发送消息
5. **模型切换**：在 UI 中支持动态切换 AI 模型

---

## 📄 许可证

本项目基于 [MIT 许可证](../LICENSE) 开源。