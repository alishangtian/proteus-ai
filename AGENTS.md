# Proteus AI 智能体系统详解

Proteus AI 提供了多种强大的智能体模式，每种模式针对不同的应用场景设计，旨在满足从简单对话到复杂研究和自动化任务的各种需求。

## 目录

- [🤖 Chat 智能体](#-chat-智能体)
- [🔬 深度研究智能体 (Deep Research)](#-深度研究智能体-deep-research)
- [💻 CodeAct 智能体](#-codeact-智能体)
- [🌐 浏览器智能体 (Browser Agent)](#-浏览器智能体-browser-agent)
- [🦸 超级智能体 (Super Agent)](#-超级智能体-super-agent)
- [👥 多智能体团队协作 (Multi-Agent Team)](#-多智能体团队协作-multi-agent-team)

---

## 🤖 Chat 智能体

基础的对话智能体，支持工具调用和上下文管理，是处理日常查询和交互的理想选择。

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
    user_name=user_name
)

# 运行智能体
result = await chat_agent.run(
    chat_id=chat_id,
    text="请搜索最新的人工智能发展动态并进行分析",
    file_analysis_context=file_context
)
```

### 核心特性
- **多轮对话**：支持上下文记忆，能够理解对话历史。
- **动态工具调用**：根据用户意图自动选择并调用合适的工具（如搜索、代码执行）。
- **文件分析**：支持上传文件并基于文件内容进行问答和分析。
- **流式响应**：实时输出思考过程和回复内容，提供更好的用户体验。

---

## 🔬 深度研究智能体 (Deep Research)

专门用于复杂研究任务的智能体，能够像人类研究员一样进行多轮深度探索和分析。

### 配置示例

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

### 研究能力
- **多源信息收集**：自动利用搜索引擎、学术数据库和网页抓取获取信息。
- **深度分析**：对收集到的信息进行综合分析、去重和验证。
- **长篇报告生成**：能够生成结构严谨、内容详实的深度研究报告。
- **自我反思**：在研究过程中不断评估信息充足度，自动补充缺失信息。

---

## 💻 CodeAct 智能体

专注于代码执行的智能体，特别适合编程、数据分析和自动化任务。它通过编写和执行 Python 代码来解决问题。

### 配置示例

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

### 编程能力
- **代码编写与执行**：在安全沙箱中编写并运行 Python 代码。
- **数据处理**：能够处理 CSV, Excel, JSON 等多种格式的数据。
- **可视化生成**：使用 Matplotlib, Seaborn 等库生成图表。
- **自动化脚本**：生成可复用的自动化脚本解决重复性任务。

---

## 🌐 浏览器智能体 (Browser Agent)

集成浏览器自动化的智能体，能够像真实用户一样操作浏览器，支持网页交互和动态数据提取。

### 配置示例

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

### 浏览器能力
- **网页自动化**：点击、输入、滚动、导航等操作。
- **动态内容抓取**：处理 JavaScript 渲染的页面和动态加载的内容。
- **视觉理解**：结合视觉模型理解页面布局和元素。
- **交互模拟**：模拟用户登录、表单填写等复杂交互流程。

---

## 🦸 超级智能体 (Super Agent)

基于真实代码实现的智能团队组建和协调系统，能够自动分析复杂任务需求并组建专业团队。这是 Proteus AI 最强大的模式之一。

### 核心工作流程

超级智能体遵循严格的 **问题评估 → 策略选择 → 团队组建 → 用户确认 → 团队执行** 的完整流程。

#### 1. 问题复杂度评估
- **简单问题**：直接回答，不使用团队，节省资源。
- **复杂问题**：识别需要多步骤思考、专业知识、多领域结合或深度分析的问题，启动团队模式。

#### 2. 团队组建流程

1.  **生成团队配置**：根据任务需求，设计包含不同角色（如数据科学家、分析师、工程师）的团队结构。
2.  **用户确认**：向用户展示生成的团队配置，征求用户同意或调整建议。
3.  **团队运行**：用户确认后，实例化团队并开始协作执行任务。

### 核心特性
- **智能团队组建**：基于任务需求自动生成最优团队配置。
- **用户确认机制**：确保团队配置符合用户预期，增加可控性。
- **多角色协作**：支持协调员、研究员、分析师等多种角色分工协作。
- **动态角色管理**：支持动态创建和配置团队角色。
- **配置持久化**：支持将团队配置保存为 YAML 文件以便复用。

---

## 👥 多智能体团队协作 (Multi-Agent Team)

预配置的专业团队，针对特定类型的任务（如软件开发、市场调研）进行了优化。

### 配置示例

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

### 团队特性
- **预定义角色**：开箱即用的专业角色配置。
- **SOP (标准作业程序)**：遵循最佳实践的工作流程。
- **记忆共享**：团队成员之间共享关键信息和上下文。
- **任务交接**：高效的任务流转和进度跟踪机制。
