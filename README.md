# Proteus Workflow Engine

一个强大的、可扩展的多智能体工作流引擎，支持Multi-Agent系统、auto-workflow、MCP-SERVER接入等功能，支持多种工具和资源，提供智能代理和自动化服务执行。

## 项目名称由来

Proteus（普罗透斯）源自希腊神话中的海神，他以能够随意改变自己的形态而闻名。这个名字完美契合了本项目的核心特性：
- 强大的可变性：就像普罗透斯能够变化成任何形态，本引擎可以通过不同节点类型的组合实现各种复杂的工作流
- 智能适应：普罗透斯具有预知未来的能力，类似地，我们的Agent系统能够智能地选择最适合的工具和执行路径
- 灵活性：如同海神能够掌控海洋的变化，本引擎能够灵活处理各种任务场景和数据流

## 实际效果
详见  **examples** 文件夹中的研究报告示例：
- `中美人工智能发展报告.md`
- `印巴空战5.7研究报告.md`
- `细胞膜结构与功能研究进展.md`
- `美俄军力报告.md`

## 项目介绍

Proteus 是一个基于 Python 和 FastAPI 构建的现代化工作流引擎，它提供了以下核心特性：

- 🚀 基于 FastAPI 的高性能 API 服务
- 🤖 内置智能 Agent 系统（支持Chain-of-Thought推理）
- 🔌 丰富的节点类型支持（20+种内置节点，包括新增的handoff交接节点）
- 📊 实时执行状态监控（基于SSE的实时通信）
- 🌐 Web 可视化界面（多种模式：工作流、智能体、多智能体等）
- 🐳 Docker 支持（包含完整的容器化部署方案）
- 🔄 MCP（Model Context Protocol）支持，可扩展外部工具和资源
- 🛡️ 安全沙箱环境（用于安全执行代码节点）

## 快速开始

### 环境要求

- Python 3.11+
- Docker (可选，用于容器化部署)
- LLM API密钥 (支持多种LLM服务，默认配置为Deepseek Chat)

### 安装步骤

1. 克隆项目
```bash
git clone https://github.com/yourusername/proteus-ai.git
cd proteus-ai
```

2. 创建并激活虚拟环境
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
```

3. 安装依赖
```bash
pip install -r proteus/requirements.txt
```

4. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件，设置必要的环境变量
```

5. 浏览器自动化需要执行如下安装
```shell
playwright install
```

### 启动服务

#### 本地开发环境
```bash
# 确保已安装所有依赖
pip install -r proteus/requirements.txt

# 如果需要浏览器自动化功能，安装playwright
playwright install

# 启动服务
python proteus/main.py
```

#### 使用 Docker
```bash
# 构建Docker镜像（在项目根目录执行）
docker build -t proteus -f proteus/Dockerfile .

# 使用Docker Compose启动所有服务
docker-compose -f proteus/docker/docker-compose.yml up -d
```

服务启动后，访问 http://localhost:8000 即可打开 Web 界面。
也可以通过 https://localhost:9443 访问Nginx代理后的HTTPS服务。

### 命令行工具 (CLI)

本项目还提供了一个功能强大的命令行工具，方便开发者和用户在终端中与 Proteus AI 系统直接交互。

- **快速开始**:
  ```bash
  # 安装CLI依赖
  pip install -r cli/requirements_cli.txt
  # 运行CLI工具
  python cli/proteus-cli.py chat "你好"
  ```
- **获取更多信息**:
  关于CLI工具的详细用法和高级功能，请参阅 `cli/CLI_README.md`。

#### 配置说明
主要配置项在`.env`文件中，您需要从`.env.example`复制并配置：

- `API_KEY`: LLM API密钥（必填）
- `MODEL_NAME`: 使用的模型名称（默认为deepseek-chat）
- `REASONER_MODEL_NAME`: 推理模型名称（可选）
- `SERPER_API_KEY`: 用于Web搜索的Serper API密钥（可选）
- `MCP_CONFIG_PATH`: MCP配置文件路径（默认为./proteus/proteus_mcp_config.json）

## 功能特点

### 1. 多样化节点类型
- API 调用节点 (api_call): 调用外部API服务
- 文件操作节点 (file_read, file_write): 读写本地文件
- 数据库操作节点 (db_query, db_execute): 执行SQL查询和更新操作
- 搜索节点 (duckduckgo_search, arxiv_search, serper_search): 从不同搜索引擎获取信息
- Python 代码执行节点 (python_execute): 动态执行Python代码
- Web 爬虫节点 (web_crawler, web_crawler_local): 抓取网页内容，支持远程API和本地浏览器
- 天气预报节点 (weather_forecast): 获取天气信息
- 用户输入节点 (user_input): 获取用户交互输入
- 工作流嵌套节点 (workflow_node): 支持工作流嵌套
- 循环节点 (loop_node): 支持循环执行
- 聊天节点 (chat): 与LLM进行对话
- 浏览器代理节点 (browser_agent): 自动化浏览器操作
- MCP客户端节点 (mcp_client): 与MCP服务器交互
- 交接节点 (handoff): 任务交接给其他Agent

### 2. 智能 Agent 系统
- 基于 Chain-of-Thought 的推理能力，支持复杂任务分解
- 自动工具选择和执行，可动态调用最适合的工具
- 多轮对话支持，保持上下文连贯性
- 历史记录管理，包括查询、结果存储和摘要生成
- 多种Agent模式：
  * 超级智能体 (super-agent): 综合能力的智能体
  * 自动工作流 (workflow): 自动生成和执行工作流
  * MCP智能体 (mcp-agent): 支持MCP协议的智能体
  * 多智能体 (multi-agent): 多个智能体协作
  * 深度研究 (research): 专注于研究任务的智能体
  * 浏览器智能体 (browser-agent): 专注于浏览器自动化任务

### 3. 实时状态监控
- SSE (Server-Sent Events) 实时通信
- 节点执行状态实时更新
- 执行结果即时反馈
- 支持工作流暂停、恢复和取消操作

### 4. Web 可视化界面
- 直观的工作流展示，支持节点和边的可视化
- 实时执行状态可视化，通过颜色和图标展示节点状态
- 历史记录查看和管理，支持会话恢复
- 多种交互模式：工作流模式、智能体模式、研究模式等
- 弹幕功能，支持实时显示执行过程中的思考和操作

## TODO 功能项

1. 核心功能增强
   - [ ] 支持工作流的暂停和恢复
   - [ ] 添加工作流模板系统
   - [ ] 实现工作流版本控制
   - [ ] 增加节点执行超时机制

2. 节点类型扩展
   - [ ] 添加更多 AI 模型集成节点
   - [ ] 实现文件格式转换节点
   - [ ] 添加邮件发送节点
   - [ ] 集成更多第三方服务 API

3. Agent 系统优化
   - [ ] 优化 Chain-of-Thought 推理
   - [ ] 添加多 Agent 协作机制
   - [ ] 实现 Agent 记忆系统
   - [ ] 增强错误处理和恢复能力

4. 用户体验改进
   - [ ] 优化 Web 界面交互
   - [ ] 添加工作流调试工具
   - [ ] 实现工作流执行日志导出
   - [ ] 添加性能监控面板

5. 部署和运维
   - [ ] 添加集群部署支持
   - [ ] 实现自动化测试
   - [ ] 优化资源使用效率
   - [ ] 增加监控告警机制

## 项目结构

```
proteus/
├── src/                    # 源代码目录
│   ├── agent/             # 智能Agent相关实现
│   │   ├── agent_engine.py # Agent引擎核心实现
│   │   ├── agent_manager.py # Agent管理器
│   │   ├── agent_router.py # Agent API路由
│   │   ├── danmaku_router.py # 弹幕功能路由
│   │   ├── multi_agent.py # 多智能体实现
│   │   ├── parse_xml.py   # XML解析工具
│   │   ├── task_manager.py # 任务管理器
│   │   └── prompt/        # Agent提示词模板
│   ├── api/               # API服务实现
│   │   ├── config.py      # API配置
│   │   ├── events.py      # 事件处理
│   │   ├── history_service.py # 历史记录服务
│   │   ├── llm_api.py     # LLM API集成
│   │   ├── stream_manager.py # 流管理器
│   │   ├── utils.py       # 工具函数
│   │   └── workflow_service.py # 工作流服务
│   ├── core/              # 核心功能实现
│   │   ├── engine.py      # 工作流引擎
│   │   ├── enums.py       # 枚举定义
│   │   ├── executor.py    # 节点执行器
│   │   ├── models.py      # 数据模型
│   │   ├── node_config.py # 节点配置管理
│   │   ├── params.py      # 参数处理
│   │   └── validator.py   # 验证器
│   ├── exception/         # 异常处理
│   ├── manager/           # 管理器
│   │   └── mcp_manager.py # MCP管理器
│   ├── nodes/             # 节点类型实现（20+种节点）
│   │   ├── base.py        # 基础节点类
│   │   ├── node_config.yaml # 节点配置文件
│   │   ├── agent_node_config.yaml # Agent节点配置
│   │   └── [各种节点实现]
│   └── utils/             # 工具函数
├── static/                # 前端静态资源
│   ├── agent/            # Agent页面资源
│   ├── icon/             # 图标资源
│   ├── superagent/       # 超级Agent页面资源
│   ├── card-styles.css   # 卡片样式
│   ├── card-view.js      # 卡片视图脚本
│   ├── danmaku.css       # 弹幕样式
│   ├── danmaku.js        # 弹幕脚本
│   ├── index.html        # 主页面
│   ├── main.js           # 主脚本
│   ├── marked.min.js     # Markdown渲染库
│   └── styles.css        # 主样式表
├── docker/                # Docker相关配置
│   ├── docker-compose.yml # Docker Compose配置
│   └── volumes/          # 卷配置
├── .env.example          # 环境变量示例
├── Dockerfile            # Docker构建文件
├── generate-ssl-cert.sh  # SSL证书生成脚本
├── LICENSE               # 许可证文件
├── main.py               # 应用入口
├── proteus_mcp_config.json # MCP配置文件
└── requirements.txt      # 依赖项列表
```

## 核心功能详解

### 1. 工作流引擎 (core/engine.py)
- 工作流生命周期管理
- 节点依赖关系处理
- 异步执行调度
- 状态追踪和错误处理
- 支持流式执行和实时状态更新
- 提供工作流暂停、恢复和取消功能

### 2. 节点系统 (nodes/)
- 统一的节点接口定义
- 丰富的内置节点类型
- 节点参数验证
- 节点执行状态管理
- 支持同步和异步执行
- 错误重试机制

### 3. Agent系统 (agent/)
- 基于CoT的推理实现
- 动态工具调用
- 上下文管理
- 多轮对话处理
- 支持多种Agent模式
- 用户输入交互
- 历史记录管理

### 4. API服务 (api/)
- RESTful API设计
- 实时通信(SSE)支持
- 工作流生成和执行
- 历史记录管理
- 事件驱动架构
- 认证和授权

### 5. MCP系统 (manager/mcp_manager.py)
- Model Context Protocol (MCP) 标准支持
- 动态加载和管理外部工具和资源
- 与远程MCP服务器集成（支持SSE通信）
- 扩展智能体能力，提供更丰富的交互方式
- 标准化的工具描述格式，便于模型理解和使用

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

### 示例2: 使用MCP工具查询天气

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

1. 在 `src/nodes/` 目录下创建新的节点文件
2. 继承 `BaseNode` 类并实现必要方法：
```python
from src.nodes.base import BaseNode

class MyCustomNode(BaseNode):
    def __init__(self, node_id: str, params: dict):
        super().__init__(node_id, params)
        
    async def execute(self, context: dict) -> dict:
        # 实现节点逻辑
        result = await self._process_data(context)
        return {"success": True, "data": result}
```
3. 在 `node_config.yaml` 中注册节点配置：
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

### 2. 扩展Agent功能

1. 在 `src/agent/prompt/` 中添加新的提示词模板
2. 修改 `src/agent/agent.py` 实现新的推理方法
3. 注册新的工具到Agent系统

### 3. 前端开发

1. 静态资源位于 `static/` 目录
2. 使用 SSE 接收实时更新：
```javascript
const eventSource = new EventSource(`/stream/${chatId}`);
eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // 处理实时数据
};
```

### 4. 测试指南

1. 单元测试：
```bash
python -m pytest tests/unit/
```

2. 集成测试：
```bash
python -m pytest tests/integration/
```

3. 端到端测试：
```bash
python -m pytest tests/e2e/
```

### 5. 使用MCP功能

1. 配置MCP服务器
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

2. 在代码中使用MCP管理器
```python
from src.manager.mcp_manager import get_mcp_manager, initialize_mcp_manager

# 初始化MCP管理器
await initialize_mcp_manager()

# 获取MCP管理器实例
mcp_manager = get_mcp_manager()

# 获取所有工具
tools = mcp_manager.get_all_tools()

# 获取所有资源
resources = mcp_manager.get_all_resources()
```

3. 在Agent中使用MCP工具
   - 选择"MCP智能体"模式
   - 或在自定义Agent中配置MCP工具

## 贡献指南

欢迎提交 Issue 和 Pull Request 来帮助改进项目。在提交代码前，请确保：

1. 代码符合项目的编码规范
2. 添加了必要的测试用例
3. 更新了相关文档
4. 遵循Git提交规范
5. 通过所有CI检查

## 接下来需要做的事情

基于对项目代码和结构的分析，以下是接下来可能需要优先考虑的工作：

1. **完善MCP集成功能**
   - 增强MCP工具的错误处理和重试机制
   - 优化MCP资源的缓存策略
   - 添加更多MCP服务器示例和文档

2. **增强多智能体协作能力**
   - 完善智能体间的通信机制
   - 实现智能体记忆和知识共享
   - 添加智能体角色定制功能

3. **优化工作流执行引擎**
   - 实现工作流的暂停和恢复功能
   - 添加工作流执行的监控和日志记录
   - 优化节点执行的并行处理能力

4. **改进用户界面**
   - 增强工作流可视化编辑功能
   - 优化移动端适配
   - 添加更多交互反馈和提示

5. **扩展节点类型**
   - 添加更多AI模型集成节点
   - 实现文件格式转换节点
   - 添加邮件和消息通知节点

## 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE) 文件。