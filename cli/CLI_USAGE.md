# Proteus AI 命令行工具使用指南

## 简介

Proteus AI CLI工具是一个专门设计用于与Proteus AI系统进行交互的命令行客户端。它提供了友好的命令行界面，支持发送问题到AI接口以及建立SSE连接接收流式响应。

## 功能特性

- 🚀 **多模型支持**: 支持所有Proteus AI模型（workflow、super-agent、home、mcp-agent、multi-agent、browser-agent、deep-research）
- 📡 **实时流式响应**: 通过SSE连接实时接收AI处理结果
- 💬 **交互式模式**: 提供类似聊天的交互体验
- ⚙️ **配置管理**: 保存常用配置，简化使用
- 🎨 **彩色输出**: 美观的终端输出界面
- 🔧 **灵活配置**: 支持自定义服务器地址、模型类型、迭代次数等

## 安装依赖

```bash
# 安装Python依赖
pip install -r requirements_cli.txt
```

## 快速开始

### 1. 基本使用

```bash
# 发送简单问题
python cli_tool.py chat "你好，请介绍一下自己"

# 使用特定模型
python cli_tool.py chat "分析一下当前市场趋势" --model deep-research

# 指定迭代次数
python cli_tool.py chat "创建一个数据处理工作流" --model workflow --iterations 10

# 指定服务器地址
python cli_tool.py chat "你好" --url http://192.168.1.100:8000
```

### 2. 交互式模式

```bash
# 进入交互式模式
python cli_tool.py interactive

# 交互式模式中可用命令：
> 你好，请介绍一下自己                    # 直接发送问题
> model deep-research                    # 切换模型
> url http://localhost:8000              # 更改服务器地址  
> iterations 8                           # 设置迭代次数
> help                                   # 显示帮助
> exit                                   # 退出
```

### 3. 配置管理

```bash
# 配置工具设置
python cli_tool.py configure

# 列出可用模型
python cli_tool.py list-models
```

## 详细使用说明

### 命令行参数

#### chat命令
- `text`: 要发送的问题文本（必需）
- `--model, -m`: AI模型类型（可选）
  - workflow: 工作流模型
  - super-agent: 超级智能体
  - home: 默认模型
  - mcp-agent: MCP智能体
  - multi-agent: 多智能体
  - browser-agent: 浏览器智能体
  - deep-research: 深度研究模型
- `--url, -u`: 服务器地址（默认: http://localhost:8000）
- `--iterations, -i`: 迭代次数（默认: 5）
- `--agent-id`: 代理ID（可选）
- `--team-name`: 团队名称（可选，主要用于deep-research模型）

#### interactive命令
- `--model, -m`: 默认AI模型类型
- `--url, -u`: 服务器地址
- `--iterations, -i`: 默认迭代次数

### 使用示例

#### 1. 基础对话
```bash
python cli_tool.py chat "今天天气怎么样？"
```

#### 2. 深度研究模式
```bash
python cli_tool.py chat "请深入研究人工智能在医疗领域的应用" --model deep-research --iterations 10
```

#### 3. 工作流模式
```bash
python cli_tool.py chat "帮我创建一个数据清洗和分析的工作流" --model workflow
```

#### 4. 指定团队进行深度研究
```bash
python cli_tool.py chat "研究量子计算的发展趋势" --model deep-research --team-name research_team
```

#### 5. 连接远程服务器
```bash
python cli_tool.py chat "你好" --url http://192.168.1.100:8000
```

### 响应事件类型

工具会智能解析不同类型的流式响应：

- 📋 **状态事件**: 显示当前处理状态
- 🔧 **工作流事件**: 显示生成的工作流信息
- ✅/❌ **结果事件**: 显示节点执行结果
- 💬 **回答事件**: 显示AI的实时回答
- ✅ **完成事件**: 表示任务完成
- ❌ **错误事件**: 显示错误信息

### 配置文件

配置文件位置: `~/.proteus_cli_config.json`

默认配置内容：
```json
{
  "base_url": "http://localhost:8000",
  "default_model": "home", 
  "default_iterations": 5
}
```

可以通过 `python cli_tool.py configure` 命令交互式修改配置。

## 故障排除

### 1. 连接失败

```
❌ 无法连接到服务器 http://localhost:8000
💡 请检查服务器是否正在运行，或使用 --url 指定正确的地址
```

**解决方案**：
- 确认Proteus AI服务器正在运行
- 检查服务器地址和端口是否正确
- 使用 `--url` 参数指定正确的服务器地址

### 2. 依赖包缺失

```
ModuleNotFoundError: No module named 'aiohttp'
```

**解决方案**：
```bash
pip install -r requirements_cli.txt
```

### 3. SSE连接异常

如果SSE连接出现问题，通常是网络或服务器配置问题。可以：
- 检查防火墙设置
- 确认服务器CORS配置正确
- 尝试重新启动服务器

### 4. JSON解析错误

```
⚠️ 收到无效的JSON数据
```

这通常表示服务器返回了非JSON格式的数据，可能是：
- 服务器错误
- 网络传输问题
- 服务器版本不兼容

## 高级用法

### 1. 批处理脚本

创建批处理脚本来处理多个问题：

```bash
#!/bin/bash
# batch_process.sh

questions=(
    "介绍一下量子计算"
    "分析人工智能发展趋势" 
    "解释区块链技术原理"
)

for question in "${questions[@]}"; do
    echo "处理问题: $question"
    python cli_tool.py chat "$question" --model deep-research
    echo "---"
done
```

### 2. 结果输出到文件

```bash
# 将结果保存到文件
python cli_tool.py chat "生成项目报告" --model deep-research > report.txt 2>&1
```

### 3. 与其他工具集成

```bash
# 从文件读取问题
cat questions.txt | xargs -I {} python cli_tool.py chat "{}" 

# 结合管道使用
echo "分析这段代码" | python cli_tool.py chat --model mcp-agent
```

## API接口对应关系

CLI工具与Proteus AI的API接口对应关系：

| CLI功能 | API接口 | 说明 |
|---------|---------|------|
| 创建聊天 | `POST /chat` | 发送问题并创建会话 |
| 流式响应 | `GET /stream/{chat_id}` | 建立SSE连接获取响应 |
| 健康检查 | `GET /health` | 检查服务器状态 |

## 许可证

本CLI工具遵循与Proteus AI项目相同的许可证。

## 贡献

欢迎提交Issue和Pull Request来改进这个工具！