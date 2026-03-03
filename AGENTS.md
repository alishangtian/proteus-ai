# Proteus AI 智能体系统详解

Proteus AI 提供了功能强大的 Chat 智能体，支持工具调用、上下文管理和技能系统，旨在满足从简单对话到复杂任务的各种需求。

## 目录

- [🤖 Chat 智能体](#-chat-智能体)
- [🔧 工具系统](#-工具系统)
- [📚 技能系统](#-技能系统)
- [💾 记忆系统](#-记忆系统)
- [🚀 智能体模式](#-智能体模式)
- [📱 Android 客户端](#-android-客户端)

---

## 🤖 Chat 智能体

Chat 智能体是 Proteus AI 的核心，支持工具调用和上下文管理，是处理日常查询和交互的理想选择。实现位于 `proteus/src/agent/chat_agent.py`。

### 配置示例

```python
# 使用 Chat 智能体进行对话
chat_agent = ChatAgent(
    stream_manager=stream_manager,
    model_name="deepseek-chat",
    enable_tools=True,
    tool_choices=["serper_search", "web_crawler", "python_execute"],
    max_tool_iterations=5,
    conversation_id=conversation_id,
    conversation_round=5,
    enable_tool_memory=True,
    enable_skills_memory=True,
    user_name=user_name,
    selected_skills=selected_skills,
    system_prompt=None,       # 可选，自定义系统提示词
    agentid=None,             # 可选，智能体唯一ID，不传则自动生成
    workspace_path=None,      # 可选，工作区路径
)

# 运行智能体
result = await chat_agent.run(
    chat_id=chat_id,
    text="请搜索最新的人工智能发展动态并进行分析",
    file_analysis_context=file_context
)
```

### 核心特性

- **多轮对话**：支持上下文记忆，能够理解对话历史。智能体会自动加载和管理会话历史，确保对话连贯性。
- **动态工具调用**：根据用户意图自动选择并调用合适的工具（如搜索、代码执行、网页爬取）。支持工具调用循环，可多次迭代执行工具。
- **文件分析**：支持上传文件并基于文件内容进行问答和分析。
- **流式响应**：通过 SSE (Server-Sent Events) 实时输出思考过程和回复内容，提供更好的用户体验。
- **技能系统**：支持技能调用和技能记忆，可扩展智能体能力。
- **工具记忆**：记录工具调用历史，优化后续交互。
- **上下文压缩**：当对话上下文超出模型窗口限制时，自动选择压缩策略（摘要、选择性裁剪或混合模式）。

### 参数说明

| 参数 | 类型 | 描述 |
|------|------|------|
| `stream_manager` | StreamManager | 流管理器实例，用于 SSE 通信，task 模式可为空 |
| `model_name` | str | 模型名称，默认为 "deepseek-chat" |
| `enable_tools` | bool | 是否启用工具调用 |
| `tool_choices` | List[str] | 指定可用的工具列表（工具类型名称） |
| `max_tool_iterations` | int | 最大工具调用迭代次数，默认 5 |
| `conversation_id` | str | 会话 ID，用于保存和恢复对话历史 |
| `conversation_round` | int | 会话轮次，默认 5 |
| `enable_tool_memory` | bool | 是否启用工具记忆功能 |
| `enable_skills_memory` | bool | 是否启用技能记忆功能 |
| `user_name` | str | 用户名，用于工具记忆隔离 |
| `selected_skills` | List[str] | 用户选中的技能列表 |
| `system_prompt` | str | 自定义系统提示词，默认使用内置 Mermaid 提示词 |
| `agentid` | str | 智能体唯一标识，不传时自动生成 UUID |
| `workspace_path` | str | 工作区路径，用于文件操作等场景 |

### 智能体生命周期管理

`ChatAgent` 内置缓存机制，支持同一 `chat_id` 下的多智能体管理：

```python
# 获取某个 chat_id 下的所有 agent
agents = ChatAgent.get_agents(chat_id)

# 停止 agent
await agent.stop()

# 清除缓存
ChatAgent.clear_agents(chat_id)
```

---

## 🔧 工具系统

Chat 智能体可以动态调用多种工具来完成复杂任务。工具定义自动从 `proteus/src/nodes/agent_node_config.yaml` 加载。

### 内置工具

| 工具名称 | 功能描述 |
|----------|----------|
| `serper_search` | Serper 搜索引擎，搜索最新信息（新闻、论坛、博客等） |
| `web_crawler` | 网页爬虫，根据链接抓取网页完整内容 |
| `python_execute` | Python/Shell 代码执行，在安全沙箱中运行 |
| `arxiv_search` | Arxiv 学术论文搜索，返回标题、作者、摘要、PDF 链接等 |
| `weather_forecast` | 天气预报查询，通过经纬度获取天气数据 |
| `api_call` | 通用 REST API 调用，支持 Bearer Token 认证 |
| `skills_extract` | 技能解析管理，列出、获取和读取技能文件 |
| `duckduckgo_search` | DuckDuckGo 搜索引擎，匿名搜索网络信息 |

### 工具调用流程

1. 智能体分析用户请求，确定需要调用的工具
2. 构造工具调用参数
3. 执行工具并获取结果
4. 将结果整合到响应中
5. 如需继续调用其他工具，重复上述步骤（最多 `max_tool_iterations` 次）

---

## 📚 技能系统

技能系统允许扩展智能体的能力，通过加载预定义的技能来处理特定类型的任务。

### 技能结构

技能存储在 `/app/.proteus/skills` 目录下（对应仓库中的 `proteus/docker/volumes/agent/skills/`），每个技能包含：

- `SKILL.md`：技能描述文件，包含技能的详细说明
- 相关资源文件：模板、配置等

### 技能使用

通过 `skills_extract` 工具可以：

- **列出技能**：`action: "list"` - 获取所有可用技能
- **获取详情**：`action: "get"` - 获取指定技能的详细信息（含文件夹结构和 `SKILL.md` 全文）
- **获取文件**：`action: "getContent"` - 获取技能目录中指定文件的内容

---

## 💾 记忆系统

### 对话历史管理

智能体自动管理对话历史，支持：

- 会话历史加载和恢复（基于 `conversation_id`）
- 消息链完整性验证（确保 tool_call/tool_result 配对）
- 对话上下文压缩（当上下文过长时，根据会话类型自动选择策略）

压缩策略配置位于 `proteus/conf/compression_strategies.yaml`，支持 `summary`（摘要）、`selective_pruning`（选择性裁剪）、`hybrid`（混合）三种模式。

### 工具记忆

启用工具记忆后，智能体会记录工具调用历史，用于：

- 避免重复调用
- 优化后续交互
- 用户隔离（基于 `user_name`）

### 技能记忆

启用技能记忆后，智能体会将选中的技能信息纳入上下文，帮助更好地理解和执行特定任务。

---

## 🚀 智能体模式

Proteus AI 支持多种智能体运行模式，适用于不同的使用场景：

| 模式 | 说明 |
|------|------|
| `chat` | 纯对话模式，支持工具调用和多轮对话，适合日常查询和交互 |
| `task` | 任务模式，自动规划并完成复杂任务 |
| `workflow` | 工作流模式，执行可视化工作流 |
| `super-agent` | 超级智能体，具备更强的规划与执行能力 |
| `mcp-agent` | MCP 模式，通过 Model Context Protocol 调用外部工具 |
| `browser-agent` | 浏览器操作模式，支持自动化网页交互 |
| `deep-research` | 深度研究模式，对指定主题进行系统性深度研究 |
| `deep-research-multi` | 多智能体协作深度研究模式 |
| `codeact-agent` | 代码执行智能体，通过编写和运行代码解决问题 |

各模式通过 `/submit_task` 接口的 `modul` 字段指定。

---

## 📱 Android 客户端

`app/` 目录包含 Proteus AI 的 Android 客户端，基于 Jetpack Compose + Kotlin 构建，详细说明见 [`app/AGENTS.md`](app/AGENTS.md) 和 [`app/README.md`](app/README.md)。

Android 客户端通过 Retrofit 与后端 REST API 通信，使用 OkHttp 接收 SSE 流式响应，主要功能包括：

- Token 管理与会话鉴权
- 会话列表浏览与切换
- 实时流式消息收发（SSE）
- 深度研究、网络搜索、技能调用等模式切换
