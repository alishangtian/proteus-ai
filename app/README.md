# Proteus AI Android 客户端

这是一个用于 Proteus AI 服务的 Android 客户端应用，提供 Token 管理、会话列表查看、消息发送与接收等功能。

## 功能特性

- **Token 管理**：通过设置弹窗存储和更新 Bearer Token
- **会话列表**：侧边栏显示用户的对话历史，支持点击切换会话
- **消息界面**：仿聊天气泡设计，区分用户消息和 AI 回复
- **任务提交**：通过 `/submit_task` 接口发送用户查询
- **可折叠侧边栏**：支持展开/收起，适配不同屏幕尺寸
- **Material Design 3**：现代化的 UI 设计，支持深色/浅色主题

## 编译与打包

### 前提条件

1. **Android Studio**（推荐 2023.3+）
2. **JDK 17** 或更高版本
3. **Android SDK**（API 34）

### 方法一：使用 Android Studio（推荐）

1. 打开 Android Studio，选择 "Open" 并导航到 `proteus-ai/app` 文件夹。
2. 等待 Gradle 同步完成（可能需要下载依赖）。
3. 连接 Android 设备或启动模拟器。
4. 点击菜单 **Build** → **Make Project** 编译项目。
5. 点击 **Run** → **Run 'app'** 安装并运行应用。

### 方法二：命令行打包（需已配置 Android SDK 环境变量）

#### 步骤 1：生成 Gradle 包装器（如尚未生成）

如果项目中没有 `gradlew` 脚本，请先安装 Gradle 并生成包装器：

```bash
# 安装 Gradle（如未安装）
brew install gradle  # macOS
# 或从官网下载

# 进入项目目录
cd /path/to/proteus-ai/app

# 生成 Gradle 包装器
gradle wrapper --gradle-version 8.5
```

#### 步骤 2：生成调试版 APK

```bash
./gradlew assembleDebug
```

生成的 APK 位于 `app/build/outputs/apk/debug/app-debug.apk`。

#### 步骤 3：生成发布版 APK（需配置签名密钥）

1. 创建签名密钥（如尚无）：

```bash
keytool -genkey -v -keystore my-release-key.jks -keyalg RSA -keysize 2048 -validity 10000 -alias my-alias
```

2. 在 `app/build.gradle.kts` 的 `android` 块中添加签名配置：

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
        proguardFiles(...)
    }
}
```

3. 执行发布构建：

```bash
./gradlew assembleRelease
```

发布版 APK 位于 `app/build/outputs/apk/release/app-release.apk`。

#### 步骤 4：生成 AAB（用于 Google Play 上传）

```bash
./gradlew bundleRelease
```

AAB 文件位于 `app/build/outputs/bundle/release/app-release.aab`。

## 配置说明

### 修改 API 基础地址

默认 API 地址为 `http://10.0.2.2:8000/`（适用于 Android 模拟器访问本地服务器）。如需更改，请修改 `ApiClient.kt` 中的 `BASE_URL` 常量：

```kotlin
private const val BASE_URL = "https://your-server.com/"
```

### 调整侧边栏宽度

侧边栏默认宽度为 `300.dp`，可在 `MainScreen.kt` 中修改 `width(300.dp)` 参数。

## 已知限制

- SSE 流式响应目前仅模拟实现，实际需对接后端 `/replay/stream/{chat_id}` 端点。
- 消息渲染暂不支持 Markdown 和图片（可后续集成 `compose-markdown` 库）。
- 会话历史加载功能待完善（目前仅显示示例消息）。

## 后续扩展建议

1. **SSE 流式接收**：使用 OkHttp EventSource 或 `ktor-sse` 实现真正的流式消息推送。
2. **Markdown 渲染**：集成 `compose-markdown` 库，支持富文本显示。
3. **文件上传**：扩展 `submit_task` 接口，支持图片、文档等附件。
4. **离线存储**：使用 Room 数据库缓存会话和消息。

## 许可证

本项目基于 MIT 许可证开源。