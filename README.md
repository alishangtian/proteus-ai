# Proteus 工作流引擎

一个强大的、可扩展的多智能体工作流引擎，支持多智能体系统、自动化工作流、MCP-SERVER 接入等功能，提供智能代理和自动化服务执行。

## 项目简介

Proteus 是一个基于 Python 和 FastAPI 构建的现代化工作流引擎，旨在提供一个灵活、高效的平台，用于构建和管理复杂的自动化任务和智能代理系统。它通过集成多种工具、支持灵活的工作流编排和多智能体协作，帮助用户实现从数据收集、分析到决策执行的全流程自动化。

## 项目名称由来

Proteus（普罗透斯）源自希腊神话中的海神，他以能够随意改变自己的形态而闻名。这个名字完美契合了本项目的核心特性：

- **强大的可变性**：就像普罗透斯能够变化成任何形态，本引擎可以通过不同节点类型的组合实现各种复杂的工作流。
- **智能适应**：普罗透斯具有预知未来的能力，类似地，我们的 Agent 系统能够智能地选择最适合的工具和执行路径。
- **灵活性**：如同海神能够掌控海洋的变化，本引擎能够灵活处理各种任务场景和数据流。

## 核心特性

Proteus 引擎提供以下核心功能，赋能您的自动化和智能代理需求：

### 1. 多智能体系统

- **基于 Chain-of-Thought (CoT) 推理**：支持复杂的任务分解和高级推理能力。
- **动态工具选择与执行**：智能体能够根据任务需求动态选择并调用最适合的内置或外部工具。
- **多轮对话与上下文管理**：支持多轮对话，保持上下文连贯性，提升交互体验。
- **多种智能体模式**：包括超级智能体、自动工作流智能体、MCP 智能体、多智能体协作、深度研究智能体和浏览器智能体等，满足不同应用场景。
- **任务交接 (Handoff) 节点**：支持智能体之间进行任务交接，实现更复杂的协作流程。

### 2. 灵活的工作流引擎

- **可视化工作流编排**：直观的 Web 界面支持节点和边的拖拽，轻松构建复杂工作流。
- **工作流生命周期管理**：支持工作流的创建、启动、暂停、恢复和取消。
- **节点依赖关系处理**：智能调度节点执行顺序，确保数据流正确。
- **异步执行与实时状态更新**：基于 SSE (Server-Sent Events) 实现实时通信，监控节点执行状态和结果。
- **循环节点与嵌套工作流**：支持循环执行和工作流嵌套，提升工作流的复用性和灵活性。

### 3. 丰富的节点类型

内置超过 20 种节点类型，涵盖多种操作，并支持轻松扩展：

- **数据与文件操作**：文件读写 (`file_read`, `file_write`)、数据库查询与执行 (`db_query`, `db_execute`)。
- **信息检索**：多种搜索引擎集成 (`duckduckgo_search`, `arxiv_search`, `serper_search`)、Web 爬虫 (`web_crawler`, `web_crawler_local`)。
- **代码与自动化**：Python 代码执行 (`python_execute`)、终端命令执行 (`terminal`)、浏览器自动化 (`browser_agent`)。
- **交互与通信**：API 调用 (`api_call`)、聊天 (`chat`)、用户输入 (`user_input`)、邮件发送 (`email_sender`)。
- **特殊功能**：天气预报 (`weather_forecast`)、MCP 客户端 (`mcp_client`)、团队生成 (`team_generator`)、工作流生成 (`workflow_generate`)。

### 4. 实时监控与可视化

- **SSE 实时通信**：通过 Server-Sent Events 实现前后端实时数据传输。
- **节点执行状态实时更新**：Web 界面实时展示节点执行进度、状态和结果。
- **弹幕功能**：实时显示智能体思考过程和操作，增强可观察性。
- **历史记录管理**：支持会话历史的查询、存储、摘要生成和恢复。

### 5. MCP (Model Context Protocol) 支持

- **可扩展外部工具与资源**：支持 MCP 标准，动态加载和管理外部工具和资源。
- **与远程 MCP 服务器集成**：通过 MCP 客户端节点与外部服务无缝交互。
- **标准化工具描述**：便于大型语言模型 (LLM) 理解和使用工具。

### 6. 安全沙箱环境

- 提供独立的沙箱环境，用于安全地执行 Python 代码和终端命令，隔离潜在风险。

### 7. Web 用户界面与命令行工具 (CLI)

- **Web 可视化界面**：提供直观的 Web 界面进行工作流构建、智能体交互和状态监控。
- **功能强大的 CLI 工具**：方便开发者和用户在终端中直接与 Proteus AI 系统交互，支持快速测试和自动化脚本。

## 实际效果

详见 **examples** 文件夹中的研究报告示例，展示了 Proteus 在复杂信息收集和分析方面的能力：

- [`中美人工智能发展报告.md`](examples/deep-research/中美人工智能发展报告.md)
- [`印巴空战5.7研究报告.md`](examples/deep-research/印巴空战5.7研究报告.md)
- [`细胞膜结构与功能研究进展.md`](examples/deep-research/细胞膜结构与功能研究进展.md)
- [`美俄军力报告.md`](examples/deep-research/美俄军力报告.md)

## 快速开始

### 环境要求

- Python 3.11+
- Docker (可选，用于容器化部署)
- LLM API 密钥 (支持多种 LLM 服务，默认配置为 Deepseek Chat)

### 安装步骤

1.  **克隆项目**
    ```bash
    git clone https://github.com/yourusername/proteus-ai.git
    cd proteus-ai
    ```

2.  **创建并激活虚拟环境**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Linux/macOS
    venv\Scripts\activate     # Windows
    ```

3.  **安装依赖**
    ```bash
    pip install -r proteus/requirements.txt
    ```

4.  **配置环境变量**
    ```bash
    cp .env.example .env
    # 编辑 .env 文件，设置必要的环境变量
    ```

5.  **浏览器自动化依赖 (可选)**
    如果需要使用浏览器自动化功能（如 `browser_agent` 或 `web_crawler_local` 节点），请安装 Playwright：
    ```shell
    playwright install
    ```

### 启动服务

#### 本地开发环境

```bash
# 确保已安装所有依赖
pip install -r proteus/requirements.txt

# 如果需要浏览器自动化功能，安装 playwright
playwright install

# 启动服务
python proteus/main.py
```

服务启动后，访问 `http://localhost:8000` 即可打开 Web 界面。

#### 使用 Docker 部署

```bash
# 构建 Docker 镜像（在项目根目录执行）
docker build -t proteus -f proteus/Dockerfile .

# 使用 Docker Compose 启动所有服务
docker-compose -f proteus/docker/docker-compose.yml up -d
```

服务启动后，访问 `http://localhost:8000` 即可打开 Web 界面。也可以通过 `https://localhost:9443` 访问 Nginx 代理后的 HTTPS 服务。

### 命令行工具 (CLI)

本项目还提供了一个功能强大的命令行工具，方便开发者和用户在终端中与 Proteus AI 系统直接交互。

-   **快速开始**:
    ```bash
    # 安装 CLI 依赖
    pip install -r cli/requirements_cli.txt
    # 运行 CLI 工具进行聊天
    python cli/proteus-cli.py chat "你好"
    ```
-   **获取更多信息**:
    关于 CLI 工具的详细用法和高级功能，请参阅 [`cli/CLI_README.md`](cli/CLI_README.md)。

## 配置说明

主要配置项在 `.env` 文件中，您需要从 `.env.example` 复制并配置：

-   `API_KEY`: LLM API 密钥（必填）。
-   `MODEL_NAME`: 使用的模型名称（默认为 `deepseek-chat`）。
-   `REASONER_MODEL_NAME`: 推理模型名称（可选）。
-   `SERPER_API_KEY`: 用于 Web 搜索的 Serper API 密钥（可选）。
-   `MCP_CONFIG_PATH`: MCP 配置文件路径（默认为 `./proteus/proteus_mcp_config.json`）。
-   `REDIS_HOST`: Redis 服务器地址（默认为 `localhost`）。
-   `REDIS_PORT`: Redis 服务器端口（默认为 `6379`）。
-   `REDIS_DB`: Redis 数据库索引（默认为 `0`）。
-   `REDIS_PASSWORD`: Redis 密码（可选）。
-   `SANDBOX_URL`: 沙箱服务 URL（默认为 `http://localhost:8001`）。

## 核心功能详解

### 1. API 入口与 Agent 调度 (`proteus/main.py`)

-   **FastAPI 应用入口**：作为整个 Proteus AI 系统的核心入口，负责初始化 FastAPI 应用。
-   **路由管理**：定义并管理所有 API 路由，包括健康检查、文件上传/删除、聊天会话、流式响应、用户输入处理以及工作流执行等。
-   **静态文件服务**：负责提供前端静态资源，支持 Web 用户界面。
-   **文件处理**：提供文件上传和删除功能，并集成文件解析服务，将文件内容作为 Agent 上下文。
-   **Agent 模式调度**：根据请求参数动态调度不同类型的智能体模式（如 `deep-research`、`super-agent`、`codeact-agent`、`workflow`、`browser-agent` 等），实现多样化的智能任务处理。
-   **实时通信**：通过 Server-Sent Events (SSE) 管理客户端与服务器的实时数据流，确保前端能实时获取 Agent 思考过程和工具执行状态。
-   **认证与授权**：集成用户认证中间件，保障系统安全。

### 2. 工作流引擎 (`proteus/src/core/engine.py`)

-   **核心执行器**：负责工作流的解析、验证、调度和执行。
-   **节点生命周期管理**：全面管理工作流中各个节点的创建、执行、暂停、恢复和取消。
-   **依赖关系处理**：智能解析和调度节点间的依赖关系，确保数据流和执行顺序的正确性。
-   **异步并发执行**：利用 Python 的 `asyncio` 实现高效的并发执行，提升工作流处理能力。
-   **状态追踪与错误处理**：实时追踪工作流和节点状态，提供健壮的错误处理机制，确保系统稳定性。
-   **流式执行支持**：支持流式数据处理和通过 SSE 进行实时状态反馈，增强可观察性。

### 3. 基础智能体 (`proteus/src/agent/agent.py`)

-   **Agent 生命周期管理**：负责 Agent 实例的创建、缓存、停止和上下文清理。
-   **工具调用**：管理 Agent 可用的工具集，并根据 LLM 的决策动态调用内置或外部工具。
-   **提示词构建**：根据当前任务、历史对话、工具描述和上下文信息，动态构建发送给大型语言模型 (LLM) 的提示词。
-   **LLM 交互**：封装与 LLM API 的通信逻辑，处理模型响应并进行解析。
-   **用户输入处理**：提供异步等待机制，允许 Agent 在执行过程中暂停并等待用户输入。
-   **Agent 间通信**：通过 Redis 队列实现 Agent 间的事件订阅和发布，支持多智能体协作和任务交接。
-   **终止条件**：支持多种终止条件，确保 Agent 在达到特定目标或限制时能够优雅地停止。

### 4. 节点系统 (`proteus/src/nodes/`)

-   **统一的节点接口定义**：所有节点遵循统一接口，易于扩展和管理。
-   **丰富的内置节点类型**：提供多样化的预定义节点，覆盖常见任务需求。
-   **节点参数验证**：确保节点输入参数的有效性和正确性。
-   **节点执行状态管理**：详细记录每个节点的执行状态、输入和输出。
-   **支持同步和异步执行**：根据节点特性选择合适的执行模式。
-   **错误重试机制**：针对可恢复错误提供自动重试功能。

### 5. Agent 系统 (`proteus/src/agent/`)

-   **基于 Chain-of-Thought (CoT) 推理**：通过 Chain-of-Thought 提示词，引导 LLM 进行多步骤推理。
-   **动态工具选择与执行**：智能体能够根据推理结果，灵活选择并调用可用工具。
-   **上下文管理**：有效管理对话和任务上下文，保持智能体行为的连贯性。
-   **多轮对话处理**：支持复杂的交互式多轮对话。
-   **支持多种 Agent 模式**：提供多种预设智能体模式，以适应不同任务场景。
-   **用户输入交互**：智能体能够接收并处理用户输入，进行实时互动。
-   **历史记录管理**：自动记录智能体交互历史，便于回顾和分析。

### 4. API 服务 (`proteus/src/api/`)

-   **RESTful API 设计**：提供清晰、标准的 RESTful API 接口。
-   **实时通信 (SSE) 支持**：通过 Server-Sent Events 实现客户端与服务器的实时数据流。
-   **工作流生成和执行**：提供 API 接口用于创建、启动和管理工作流。
-   **历史记录管理**：API 支持查询和管理所有会话和工作流的历史记录。
-   **事件驱动架构**：基于事件的内部通信机制，提高系统解耦性。
-   **认证和授权**：提供用户认证和权限管理功能，确保系统安全。

### 5. MCP 系统 (`proteus/src/manager/mcp_manager.py`)

-   **Model Context Protocol (MCP) 标准支持**：遵循 MCP 协议，实现模型与外部工具和资源的标准化交互。
-   **动态加载和管理外部工具和资源**：允许系统动态发现和集成新的工具和数据源。
-   **与远程 MCP 服务器集成**：通过 MCP 客户端节点，无缝连接和利用远程 MCP 服务提供的能力。
-   **扩展智能体能力**：为智能体提供更丰富的工具集和数据访问能力。
-   **标准化的工具描述格式**：确保 LLM 能够准确理解和使用各种工具。

## 使用示例

### 示例1: 创建简单研究工作流

以下是一个简单的研究工作流示例，用于收集和分析主题信息：

```yaml
name: 简单研究流程
description: 一个简单的研究工作流示例
nodes:
  - type: user_input
    id: input
    params:
      question: "请输入研究主题"
  - type: duckduckgo_search
    id: search
    params:
      query: "{{input.output}}"
      max_results: 5
  - type: web_crawler
    id: crawler
    params:
      urls: "{{search.output}}"
  - type: chat
    id: analysis
    params:
      prompt: |
        请基于以下内容进行分析总结：
        {{crawler.output}}
  - type: file_write
    id: output
    params:
      path: "./research_output.md"
      content: "{{analysis.output}}"
```

### 示例2: 使用 MCP 工具查询天气

```yaml
name: 天气查询
description: 使用MCP工具查询天气
nodes:
  - type: user_input
    id: input
    params:
      question: "请输入城市名称"
  - type: mcp_client
    id: weather
    params:
      server_name: "amap-maps"
      tool_name: "maps_weather"
      arguments: |
        {
          "city": "{{input.output}}"
        }
  - type: chat
    id: format
    params:
      prompt: |
        将天气数据格式化为友好回复：
        {{weather.output}}
```

## 开发指南

### 1. 添加新节点类型

1.  在 `proteus/src/nodes/` 目录下创建新的节点文件。
2.  继承 `BaseNode` 类并实现必要方法：
    ```python
    from proteus.src.nodes.base import BaseNode

    class MyCustomNode(BaseNode):
        def __init__(self, node_id: str, params: dict):
            super().__init__(node_id, params)

        async def execute(self, context: dict) -> dict:
            # 实现节点逻辑
            result = await self._process_data(context)
            return {"success": True, "data": result}
    ```
3.  在 `proteus/src/nodes/node_config.yaml` 中注册节点配置：
    ```yaml
    MyCustomNode:
      type: my_custom_node
      description: "自定义节点描述"
      params:
        param1:
          type: string
          required: true
          description: "参数1描述"
    ```

### 2. 扩展 Agent 功能

1.  在 `proteus/src/agent/prompt/` 中添加新的提示词模板。
2.  修改 `proteus/src/agent/agent.py` 实现新的推理方法。
3.  注册新的工具到 Agent 系统。

### 3. 前端开发

1.  静态资源位于 `proteus/static/` 目录。
2.  使用 SSE 接收实时更新：
    ```javascript
    const eventSource = new EventSource(`/stream/${chatId}`);
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        // 处理实时数据
    };
    ```

### 4. 测试指南

1.  **单元测试**：
    ```bash
    python -m pytest tests/unit/
    ```

2.  **集成测试**：
    ```bash
    python -m pytest tests/integration/
    ```

3.  **端到端测试**：
    ```bash
    python -m pytest tests/e2e/
    ```

### 5. 使用 MCP 功能

1.  **配置 MCP 服务器**：
    在 `proteus/proteus_mcp_config.json` 中配置 MCP 服务器信息：
    ```json
    {
        "mcpServers": {
            "server-name": {
                "type": "sse",
                "url": "https://your-mcp-server-url"
            }
        }
    }
    ```

2.  **在代码中使用 MCP 管理器**：
    ```python
    from proteus.src.manager.mcp_manager import get_mcp_manager, initialize_mcp_manager

    # 初始化 MCP 管理器
    await initialize_mcp_manager()

    # 获取 MCP 管理器实例
    mcp_manager = get_mcp_manager()

    # 获取所有工具
    tools = mcp_manager.get_all_tools()

    # 获取所有资源
    resources = mcp_manager.get_all_resources()
    ```

3.  **在 Agent 中使用 MCP 工具**：
    -   选择“MCP 智能体”模式。
    -   或在自定义 Agent 中配置 MCP 工具。

## 未来计划

我们致力于不断改进 Proteus 引擎，以下是未来可能优先考虑的功能和优化：

1.  **核心功能增强**
    -   完善工作流的暂停和恢复机制。
    -   引入工作流模板系统，简化常用工作流的创建。
    -   实现工作流版本控制，支持历史回溯和管理。
    -   增加节点执行超时机制，提升系统稳定性。

2.  **节点类型扩展**
    -   集成更多主流 AI 模型和第三方服务 API。
    -   实现文件格式转换节点，支持更多数据处理场景。
    -   添加邮件和消息通知节点，增强工作流的通知能力。

3.  **Agent 系统优化**
    -   进一步优化 Chain-of-Thought 推理的效率和准确性。
    -   增强多智能体协作机制，实现更智能的任务分配和协同。
    -   实现智能体记忆系统和知识共享机制。
    -   增强错误处理和恢复能力，提升智能体的鲁棒性。

4.  **用户体验改进**
    -   优化 Web 界面交互，提供更流畅的用户体验。
    -   添加工作流调试工具，方便开发者排查问题。
    -   实现工作流执行日志导出功能。
    -   增加性能监控面板，实时查看系统运行状态。

5.  **部署和运维**
    -   添加集群部署支持，提升系统可伸缩性。
    -   实现自动化测试框架，确保代码质量。
    -   优化资源使用效率，降低运行成本。
    -   增加监控告警机制，及时发现和处理问题。

## 贡献指南

欢迎提交 Issue 和 Pull Request 来帮助改进项目。在提交代码前，请确保：

1.  代码符合项目的编码规范。
2.  添加了必要的测试用例。
3.  更新了相关文档。
4.  遵循 Git 提交规范。
5.  通过所有 CI 检查。

## 许可证

本项目采用 MIT 许可证，详见 [`LICENSE`](LICENSE) 文件。