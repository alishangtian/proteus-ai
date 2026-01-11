# Proteus AI：多智能体工作流引擎

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.2-green)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Proteus AI 是一个强大的、可扩展的、基于 Python 和 FastAPI 构建的多智能体工作流引擎。它旨在提供一个灵活、高效的平台，用于构建和管理复杂的自动化任务和智能代理系统。

## 🌊 项目名称由来

Proteus（普罗透斯）源自希腊神话中的海神，他以能够随意改变自己的形态而闻名。这个名字完美契合了本项目的核心特性：

- **强大的可变性**：引擎通过不同节点类型的组合实现各种复杂的工作流
- **智能适应**：Agent 系统能够智能地选择最适合的工具和执行路径  
- **灵活性**：引擎能够灵活处理各种任务场景和数据流

## ✨ 核心特性

### 🧠 强大的多智能体系统
- **高级推理能力**：基于 Chain-of-Thought (CoT) 推理，支持复杂的任务分解和决策
- **动态工具调用**：智能体能够根据任务需求动态选择并调用内置或外部工具
- **多轮对话与上下文管理**：支持多轮对话，保持上下文连贯性，提升交互体验
- **多样化智能体模式**：提供超级智能体、自动工作流智能体、MCP 智能体、多智能体协作、深度研究智能体和浏览器智能体等
- **任务交接**：支持智能体之间进行任务交接，实现更复杂的协作流程

### 🔄 灵活的工作流编排
- **可视化工作流构建**：直观的 Web 界面支持节点和边的拖拽，轻松构建复杂工作流
- **完整的生命周期管理**：支持工作流的创建、启动、暂停、恢复和取消
- **智能调度**：处理节点依赖关系，确保数据流和执行顺序正确
- **异步执行与实时监控**：基于 SSE (Server-Sent Events) 实现实时通信，监控节点执行状态和结果
- **高级工作流结构**：支持循环执行和工作流嵌套，提升复用性和灵活性

### 🛠️ 丰富的内置节点与可扩展性
内置超过 20 种节点类型，涵盖多种操作，并支持轻松扩展：

| 类别 | 节点类型 | 功能描述 |
|------|----------|----------|
| **数据与文件** | `file_read`, `file_write` | 文件读写操作 |
| **数据库操作** | `db_query`, `db_execute`, `mysql_node` | 数据库查询和执行 |
| **信息检索** | `duckduckgo_search`, `arxiv_search`, `serper_search` | 多种搜索引擎集成 |
| **Web 爬虫** | `web_crawler`, `web_crawler_local` | 网页内容抓取 |
| **代码与自动化** | `python_execute`, `terminal` | Python 代码和终端命令执行 |
| **浏览器自动化** | `browser_agent` | 浏览器操作自动化 |
| **交互与通信** | `api_call`, `chat`, `user_input`, `email_sender` | API 调用、聊天、用户输入、邮件发送 |
| **特殊功能** | `weather_forecast`, `mcp_client`, `team_generator`, `workflow_generate` | 天气预报、MCP 客户端、团队生成、工作流生成 |

### 📊 实时监控与可视化
- **SSE 实时通信**：通过 Server-Sent Events 实现前后端实时数据传输
- **节点状态实时更新**：Web 界面实时展示节点执行进度、状态和结果
- **智能体思考过程可视化**：实时显示智能体思考过程和操作，增强可观察性
- **历史记录管理**：支持会话历史的查询、存储、摘要生成和恢复

### 🔌 MCP (Model Context Protocol) 支持
- **标准化外部工具集成**：支持 MCP 标准，动态加载和管理外部工具和资源
- **远程 MCP 服务器集成**：通过 MCP 客户端节点与外部服务无缝交互
- **LLM 工具理解**：标准化的工具描述便于大型语言模型 (LLM) 理解和使用工具

### 🛡️ 安全沙箱环境
提供独立的沙箱环境，用于安全地执行 Python 代码和终端命令，隔离潜在风险。

### 🎨 用户友好的界面与工具
- **Web 可视化界面**：提供直观的 Web 界面进行工作流构建、智能体交互和状态监控
- **命令行工具 (CLI)**：功能强大的 CLI 工具，方便开发者和用户在终端中直接与 Proteus AI 系统交互

## 📋 实际效果展示

请查看 [`examples/`](examples/) 文件夹中的研究报告示例，展示 Proteus 在复杂信息收集和分析方面的能力：

- [中美人工智能发展报告](examples/deep-research/中美人工智能发展报告.md)
- [印巴空战5.7研究报告](examples/deep-research/印巴空战5.7研究报告.md)  
- [细胞膜结构与功能研究进展](examples/deep-research/细胞膜结构与功能研究进展.md)
- [美俄军力报告](examples/deep-research/美俄军力报告.md)

## 🚀 快速开始

请严格遵循以下流程构建和启动项目。

### 前提条件

- **Docker** & **Docker Compose**
- **OpenSSL** (用于生成 SSL 证书)

### 构建与启动流程

#### 1. 构建 Sandbox 镜像

首先构建用于安全执行代码的沙箱环境镜像。

```bash
cd sandbox
./build.sh
cd ..
```

#### 2. 构建 Proteus 镜像

构建核心 Agent 服务的镜像。

```bash
cd proteus
docker build -t proteus-agent .
```

#### 3. 生成 SSL 证书

为 Nginx 服务生成 SSL 证书，以支持 HTTPS 访问。

```bash
# 确保在 proteus 目录下
./bin/generate-ssl-cert.sh
```

#### 4. 启动服务

进入 Docker 目录并启动所有服务。

```bash
cd docker

# 首次启动前，请确保配置了必要的环境变量
# 复制示例配置文件
# cp volumes/agent/.env.example volumes/agent/.env
# cp volumes/sandbox/.env.example volumes/sandbox/.env

# 启动服务
docker-compose up -d
```

服务启动后：
- Web 界面访问地址: `https://localhost` (通过 Nginx 代理) 或 `http://localhost:8000`
- Sandbox 服务运行在: `http://localhost:8000` (容器内部端口)

## ⚙️ 配置说明

主要配置项位于 `proteus/docker/volumes/agent/.env` 文件中。您需要从 `.env.example` 复制并配置：

## 🧠 Agent 功能详解

Proteus AI 提供了多种强大的智能体模式，每种模式针对不同的应用场景设计：

### 🤖 Chat 智能体
基础的对话智能体，支持工具调用和上下文管理：

```python
# 使用 Chat 智能体进行对话
chat_agent = ChatAgent(
    stream_manager=stream_manager,
    model_name="deepseek-chat",
    enable_tools=True,
    tool_choices=["serper_search", "web_crawler", "python_execute"],
    max_tool_iterations=5,
    conversation_id=conversation_id,
    user_name=user_name
)

# 运行智能体
result = await chat_agent.run(
    chat_id=chat_id,
    text="请搜索最新的人工智能发展动态并进行分析",
    file_analysis_context=file_context
)
```

**核心特性：**
- 支持多轮对话和上下文记忆
- 动态工具调用和选择
- 文件上传和内容分析
- 实时流式响应

### 🔬 深度研究智能体 (Deep Research)
专门用于复杂研究任务的智能体，支持多轮深度探索：

```python
# 深度研究智能体配置
deep_research_agent = ReactAgent(
    tools=["python_execute", "serper_search", "web_crawler", "user_input"],
    instruction="",
    stream_manager=stream_manager,
    max_iterations=10,
    model_name="deepseek-chat",
    prompt_template=REACT_PLAYBOOK_PROMPT_v3,
    role_type=TeamRole.GENERAL_AGENT,
    conversation_id=conversation_id,
    user_name=user_name
)

# 执行深度研究任务
result = await deep_research_agent.run(
    query="深入研究中美人工智能政策差异及其对产业发展的影响",
    chat_id=chat_id
)
```

**研究能力：**
- 多源信息收集（搜索引擎、学术论文、网页内容）
- 深度分析和综合报告生成
- 自动化的数据验证和交叉验证
- 结构化研究成果输出

### 💻 CodeAct 智能体
专注于代码执行的智能体，特别适合编程和自动化任务：

```python
# CodeAct 智能体配置
codeact_agent = ReactAgent(
    tools=["python_execute", "user_input"],
    instruction="""
    你是一个CodeAct Agent，主要使用Python代码执行工具来完成用户请求的任务。
    你可以使用Python代码进行任何计算、数据获取和处理。
    在编写代码时，请确保代码安全且只执行必要的操作。
    """,
    stream_manager=stream_manager,
    max_iterations=8,
    model_name="deepseek-chat",
    prompt_template=REACT_PLAYBOOK_PROMPT_v2,
    role_type=TeamRole.GENERAL_AGENT,
    conversation_id=conversation_id,
    user_name=user_name
)

# 执行代码任务
result = await codeact_agent.run(
    query="请编写一个Python脚本来分析这个数据集并生成可视化图表",
    chat_id=chat_id,
    context=dataset_context
)
```

**编程能力：**
- Python 代码编写和执行
- 数据处理和分析
- 自动化脚本生成
- 沙箱环境安全执行

### 🌐 浏览器智能体 (Browser Agent)
集成浏览器自动化的智能体，支持网页交互和数据提取：

```python
# 浏览器智能体配置
browser_agent = ReactAgent(
    tools=["browser_agent", "python_execute", "user_input", "serper_search", "web_crawler"],
    instruction="",
    stream_manager=stream_manager,
    max_iterations=6,
    model_name="deepseek-chat",
    prompt_template=COT_BROWSER_USE_PROMPT_TEMPLATES,
    role_type=TeamRole.GENERAL_AGENT,
    conversation_id=conversation_id,
    user_name=user_name
)

# 执行浏览器任务
result = await browser_agent.run(
    query="请登录电商网站并搜索最新款手机的价格和评价",
    chat_id=chat_id
)
```

**浏览器能力：**
- 网页自动化操作（点击、滚动、表单填写）
- 动态内容抓取
- 用户交互模拟
- 截图和页面状态记录

### 🦸 超级智能体 (Super Agent)
基于真实代码实现的智能团队组建和协调系统，能够自动分析复杂任务需求并组建专业团队：

#### 核心工作流程
超级智能体遵循严格的问题评估→策略选择→团队组建→用户确认→团队执行的完整流程。

**1. 问题复杂度评估**
- **简单问题**：直接回答，不使用团队
- **复杂问题**：需要多步骤思考、专业知识、多领域结合或深度分析的问题

**2. 团队组建流程**
（此处省略详细 XML 示例，详见源码或完整文档）

**核心特性：**
- **智能团队组建**：基于任务需求自动生成专业团队配置
- **用户确认机制**：团队配置必须经过用户确认才能执行
- **多角色协作**：支持协调员、研究员、分析师等多种角色
- **动态角色管理**：支持动态创建和配置团队角色
- **完整生命周期**：团队生成→用户确认→团队运行→结果整合
- **配置持久化**：支持将团队配置保存为YAML文件
- **实时监控**：通过SSE实时展示团队执行进度和结果

### 👥 多智能体团队协作 (Multi-Agent Team)
预配置的专业团队，针对特定任务类型优化：

```python
# 多智能体团队配置（基于YAML配置文件）
team = PagenticTeam(
    team_rules=team_config["team_rules"],
    tools_config=tools_config,
    start_role=getattr(TeamRole, team_config["start_role"]),
    conversation_round=conversation_round,
    user_name=user_name,
    tool_memory_enabled=True,
    sop_memory_enabled=True
)

# 注册并运行团队
await team.register_agents(chat_id)
result = await team.run(
    query="完成一个完整的技术研究报告，包括市场分析、技术评估和未来趋势预测",
    chat_id=chat_id
)
```

**团队特性：**
- 预定义角色和职责（研究员、分析师、协调员等）
- 专业化工具配置
- 记忆共享和知识传递
- 任务交接和进度跟踪

## 🛠️ 开发指南

### 1. 项目结构

```
proteus-ai/
├── proteus/                 # 主应用目录
│   ├── src/                # 源代码
│   │   ├── agent/          # 智能体系统
│   │   ├── nodes/          # 节点实现
│   │   ├── api/            # API 接口
│   │   ├── core/           # 核心引擎
│   │   └── utils/          # 工具函数
│   ├── static/             # 静态文件
│   ├── conf/               # 配置文件
│   ├── docker/             # Docker 配置
│   └── requirements.txt    # Python 依赖
├── sandbox/                # 沙箱环境
├── examples/               # 使用示例
├── cli/                    # 命令行工具
└── docs/                   # 文档
```

### 2. 添加新节点类型

1. **在 `proteus/src/nodes/` 目录下创建新的节点文件**
2. **在 `proteus/src/nodes/node_config.yaml` 中注册节点配置**

### 3. 扩展 Agent 功能

1. **在 `proteus/src/agent/prompt/` 中添加新的提示词模板**
2. **修改 `proteus/src/agent/agent.py` 实现新的推理方法**
3. **注册新的工具到 Agent 系统**

### 4. 前端开发

1. **静态资源位于 `proteus/static/` 目录**
2. **使用 SSE 接收实时更新**

### 5. 测试指南

```bash
# 单元测试
python -m pytest tests/unit/

# 集成测试  
python -m pytest tests/integration/

# 端到端测试
python -m pytest tests/e2e/
```

### 6. 使用 MCP 功能

1. **配置 MCP 服务器**
2. **在代码中使用 MCP 管理器**
3. **在 Agent 中使用 MCP 工具**

## 🔮 未来计划

我们致力于不断改进 Proteus 引擎，以下是未来可能优先考虑的功能和优化：

### 核心功能增强
- 完善工作流的暂停和恢复机制
- 引入工作流模板系统
- 实现工作流版本控制
- 增加节点执行超时机制

### 节点类型扩展  
- 集成更多主流 AI 模型和第三方服务 API
- 实现文件格式转换节点
- 添加邮件和消息通知节点

### Agent 系统优化
- 进一步优化 Chain-of-Thought 推理
- 增强多智能体协作机制  
- 实现智能体记忆系统和知识共享
- 增强错误处理和恢复能力

### 用户体验改进
- 优化 Web 界面交互
- 添加工作流调试工具
- 实现工作流执行日志导出功能
- 增加性能监控面板

### 部署和运维
- 添加集群部署支持
- 实现自动化测试框架
- 优化资源使用效率
- 增加监控告警机制

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request 来帮助改进项目。在提交代码前，请确保：

- 代码符合项目的编码规范
- 添加了必要的测试用例
- 更新了相关文档
- 遵循 Git 提交规范
- 通过所有 CI 检查

## 📄 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE) 文件。

## 🔗 相关资源

- [API 文档](http://localhost:8000/docs) (启动服务后访问)
- [示例配置](proteus/conf/)
- [Docker 部署指南](proteus/docker/)
- [CLI 工具文档](cli/CLI_README.md)

## 💬 支持与反馈

如果您在使用过程中遇到问题或有改进建议，请通过以下方式联系我们：

- 提交 [GitHub Issue](https://github.com/alishangtian/proteus-ai/issues)
- 查看 [文档](docs/)
- 参与社区讨论

---

*Proteus AI - 让复杂任务变得简单自动化*
