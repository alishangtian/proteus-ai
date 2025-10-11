# Proteus：多智能体工作流引擎

Proteus 是一个强大的、可扩展的、基于 Python 和 FastAPI 构建的多智能体工作流引擎。它旨在提供一个灵活、高效的平台，用于构建和管理复杂的自动化任务和智能代理系统。通过集成多种工具、支持灵活的工作流编排和多智能体协作，Proteus 赋能用户实现从数据收集、分析到决策执行的全流程自动化。

## 项目名称由来

Proteus（普罗透斯）源自希腊神话中的海神，他以能够随意改变自己的形态而闻名。这个名字完美契合了本项目的核心特性：

- **强大的可变性**：引擎通过不同节点类型的组合实现各种复杂的工作流。
- **智能适应**：Agent 系统能够智能地选择最适合的工具和执行路径。
- **灵活性**：引擎能够灵活处理各种任务场景和数据流。

## 核心特性

Proteus 引擎提供以下核心功能，赋能您的自动化和智能代理需求：

### 1. 强大的多智能体系统

- **高级推理能力**：基于 Chain-of-Thought (CoT) 推理，支持复杂的任务分解和决策。
- **动态工具调用**：智能体能够根据任务需求动态选择并调用内置或外部工具。
- **多轮对话与上下文管理**：支持多轮对话，保持上下文连贯性，提升交互体验。
- **多样化智能体模式**：提供超级智能体、自动工作流智能体、MCP 智能体、多智能体协作、深度研究智能体和浏览器智能体等，满足不同应用场景。
- **任务交接**：支持智能体之间进行任务交接，实现更复杂的协作流程。

### 2. 灵活的工作流编排

- **可视化工作流构建**：直观的 Web 界面支持节点和边的拖拽，轻松构建复杂工作流。
- **完整的生命周期管理**：支持工作流的创建、启动、暂停、恢复和取消。
- **智能调度**：处理节点依赖关系，确保数据流和执行顺序正确。
- **异步执行与实时监控**：基于 SSE (Server-Sent Events) 实现实时通信，监控节点执行状态和结果。
- **高级工作流结构**：支持循环执行和工作流嵌套，提升复用性和灵活性。

### 3. 丰富的内置节点与可扩展性

内置超过 20 种节点类型，涵盖多种操作，并支持轻松扩展：

- **数据与文件**：文件读写 (`file_read`, `file_write`)、数据库操作 (`db_query`, `db_execute`)。
- **信息检索**：多种搜索引擎集成 (`duckduckgo_search`, `arxiv_search`, `serper_search`)、Web 爬虫 (`web_crawler`, `web_crawler_local`)。
- **代码与自动化**：Python 代码执行 (`python_execute`)、终端命令执行 (`terminal`)、浏览器自动化 (`browser_agent`)。
- **交互与通信**：API 调用 (`api_call`)、聊天 (`chat`)、用户输入 (`user_input`)、邮件发送 (`email_sender`)。
- **特殊功能**：天气预报 (`weather_forecast`)、MCP 客户端 (`mcp_client`)、团队生成 (`team_generator`)、工作流生成 (`workflow_generate`)。

### 4. 实时监控与可视化

- **SSE 实时通信**：通过 Server-Sent Events 实现前后端实时数据传输。
- **节点状态实时更新**：Web 界面实时展示节点执行进度、状态和结果。
- **智能体思考过程可视化**：实时显示智能体思考过程和操作，增强可观察性。
- **历史记录管理**：支持会话历史的查询、存储、摘要生成和恢复。

### 5. MCP (Model Context Protocol) 支持

- **标准化外部工具集成**：支持 MCP 标准，动态加载和管理外部工具和资源。
- **远程 MCP 服务器集成**：通过 MCP 客户端节点与外部服务无缝交互。
- **LLM 工具理解**：标准化的工具描述便于大型语言模型 (LLM) 理解和使用工具。

### 6. 安全沙箱环境

- 提供独立的沙箱环境，用于安全地执行 Python 代码和终端命令，隔离潜在风险。

### 7. 用户友好的界面与工具

- **Web 可视化界面**：提供直观的 Web 界面进行工作流构建、智能体交互和状态监控。
- **命令行工具 (CLI)**：功能强大的 CLI 工具，方便开发者和用户在终端中直接与 Proteus AI 系统交互，支持快速测试和自动化脚本。

## 实际效果

请查看 **examples** 文件夹中的研究报告示例，展示 Proteus 在复杂信息收集和分析方面的能力：

- [`中美人工智能发展报告.md`](examples/deep-research/中美人工智能发展报告.md)
- [`印巴空战5.7研究报告.md`](examples/deep-research/印巴空战5.7研究报告.md)
- [`细胞膜结构与功能研究进展.md`](examples/deep-research/细胞膜结构与功能研究进展.md)
- [`美俄军力报告.md`](examples/deep-research/美俄军力报告.md)

## 快速开始

### 环境要求

-   Python 3.11+
-   Docker (可选，用于容器化部署)
-   LLM API 密钥 (支持多种 LLM 服务，默认配置为 Deepseek Chat)

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

3.  **安装核心依赖**
    ```bash
    pip install -r proteus/requirements.txt
    ```

4.  **配置环境变量**
    复制 `.env.example` 到 `.env`，并根据需要编辑 `.env` 文件，设置必要的环境变量（如 `API_KEY`）。
    ```bash
    cp .env.example .env
    ```

5.  **浏览器自动化依赖 (可选)**
    如果需要使用浏览器自动化功能（如 `browser_agent` 或 `web_crawler_local` 节点），请安装 Playwright：
    ```shell
    playwright install
    ```

### 启动服务

#### 本地开发

```bash
# 确保已安装所有依赖
pip install -r proteus/requirements.txt
playwright install # 如果需要浏览器自动化功能

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

本项目提供功能强大的命令行工具，方便开发者和用户在终端中与 Proteus AI 系统直接交互。

-   **快速开始**:
    ```bash
    # 安装 CLI 依赖
    pip install -r cli/requirements_cli.txt
    # 运行 CLI 工具进行聊天
    python cli/proteus-cli.py chat "你好"
    ```
-   **更多信息**:
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

此示例展示了如何通过 `mcp_client` 节点调用外部 MCP 服务器提供的工具来查询天气。

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
      server_name: "amap-maps" # 假设已配置名为 "amap-maps" 的 MCP 服务器
      tool_name: "maps_weather" # 调用该服务器上的 "maps_weather" 工具
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
2.  继承 `BaseNode` 类并实现必要方法。
3.  在 `proteus/src/nodes/node_config.yaml` 中注册节点配置。

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

-   **单元测试**：`python -m pytest tests/unit/`
-   **集成测试**：`python -m pytest tests/integration/`
-   **端到端测试**：`python -m pytest tests/e2e/`

### 5. 使用 MCP 功能

1.  **配置 MCP 服务器**：
    在 `proteus/proteus_mcp_config.json` 中配置 MCP 服务器信息，例如：
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

-   **核心功能增强**：完善工作流的暂停和恢复机制，引入工作流模板系统，实现工作流版本控制，增加节点执行超时机制。
-   **节点类型扩展**：集成更多主流 AI 模型和第三方服务 API，实现文件格式转换节点，添加邮件和消息通知节点。
-   **Agent 系统优化**：进一步优化 Chain-of-Thought 推理，增强多智能体协作机制，实现智能体记忆系统和知识共享，增强错误处理和恢复能力。
-   **用户体验改进**：优化 Web 界面交互，添加工作流调试工具，实现工作流执行日志导出功能，增加性能监控面板。
-   **部署和运维**：添加集群部署支持，实现自动化测试框架，优化资源使用效率，增加监控告警机制。

## 贡献指南

欢迎提交 Issue 和 Pull Request 来帮助改进项目。在提交代码前，请确保：

-   代码符合项目的编码规范。
-   添加了必要的测试用例。
-   更新了相关文档。
-   遵循 Git 提交规范。
-   通过所有 CI 检查。

## 许可证

本项目采用 MIT 许可证，详见 [`LICENSE`](LICENSE) 文件。