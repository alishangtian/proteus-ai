# Proteus AI 命令行工具

一个强大而易用的命令行工具，用于与Proteus AI系统进行交互。支持实时聊天、流式响应和多种AI模型。

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install -r requirements_cli.txt
```

### 2. 基本使用
```bash
# 发送问题
python cli_tool.py chat "你好，请介绍一下自己"

# 交互式模式
python cli_tool.py interactive
```

### 3. 使用启动脚本（推荐）
```bash
# Linux/macOS
chmod +x proteus-cli.sh
./proteus-cli.sh chat "你好"

# Windows  
proteus-cli.bat chat "你好"
```

## 📋 功能特性

- ✅ **多模型支持**: workflow、super-agent、home、mcp-agent、multi-agent、browser-agent、deep-research
- ✅ **实时流式响应**: 通过SSE连接实时接收AI处理结果
- ✅ **交互式模式**: 类似聊天的连续对话体验
- ✅ **配置管理**: 保存和管理常用设置
- ✅ **彩色终端输出**: 美观的用户界面
- ✅ **跨平台支持**: Windows、Linux、macOS
- ✅ **健康检查**: 自动检测服务器连接状态

## 🎯 支持的AI模型

| 模型名称 | 说明 | 适用场景 |
|----------|------|----------|
| `home` | 默认通用模型 | 日常对话、一般问答 |
| `workflow` | 工作流模型 | 创建和执行复杂工作流 |
| `super-agent` | 超级智能体 | 智能组建团队完成复杂任务 |
| `deep-research` | 深度研究模型 | 深入分析和研究 |
| `multi-agent` | 多智能体协作 | 需要多个AI协作的任务 |
| `browser-agent` | 浏览器智能体 | 网页操作和信息获取 |
| `mcp-agent` | MCP智能体 | 特定协议和工具调用 |

## 💻 命令示例

### 基础对话
```bash
python cli_tool.py chat "今天天气怎么样？"
```

### 深度研究
```bash
python cli_tool.py chat "请深入分析人工智能在医疗领域的应用前景" --model deep-research --iterations 10
```

### 工作流创建
```bash
python cli_tool.py chat "帮我创建一个数据清洗和分析的工作流" --model workflow
```

### 指定服务器
```bash
python cli_tool.py chat "你好" --url http://192.168.1.100:8000
```

### 团队协作研究
```bash
python cli_tool.py chat "研究量子计算的发展趋势" --model deep-research --team-name research_team
```

## ⚙️ 配置管理

### 查看和修改配置
```bash
python cli_tool.py configure
```

### 配置文件位置
- Windows: `%USERPROFILE%\.proteus_cli_config.json`
- Linux/macOS: `~/.proteus_cli_config.json`

### 默认配置
```json
{
  "base_url": "http://localhost:8000",
  "default_model": "home", 
  "default_iterations": 5
}
```

## 🔧 高级用法

### 交互式模式命令
```bash
python cli_tool.py interactive

# 进入交互模式后：
> 你好，请介绍一下自己              # 发送问题
> model deep-research              # 切换模型
> url http://localhost:8000        # 更改服务器
> iterations 8                     # 设置迭代次数
> help                             # 显示帮助
> exit                             # 退出
```

### 批处理示例
```bash
# 从文件读取问题列表
cat questions.txt | while read line; do
    python cli_tool.py chat "$line" --model deep-research
done
```

### 结果保存
```bash
# 保存到文件
python cli_tool.py chat "生成项目报告" > report.txt 2>&1
```

## 🛠️ 文件说明

| 文件 | 说明 |
|------|------|
| `cli_tool.py` | 主要的CLI工具实现 |
| `proteus-cli.py` | Python启动脚本 |
| `proteus-cli.sh` | Linux/macOS启动脚本 |
| `proteus-cli.bat` | Windows启动脚本 |
| `requirements_cli.txt` | Python依赖包列表 |
| `demo.py` | 功能演示脚本 |
| `CLI_USAGE.md` | 详细使用指南 |

## 🐛 故障排除

### 连接失败
```
❌ 无法连接到服务器
```
- 检查Proteus AI服务器是否运行
- 验证服务器地址和端口
- 检查防火墙设置

### 依赖包缺失
```
ModuleNotFoundError: No module named 'xxx'
```
- 运行: `pip install -r requirements_cli.txt`

### SSE连接问题
- 检查网络连接
- 确认服务器CORS配置
- 尝试重启服务器

## 📊 API接口对应

| CLI功能 | API接口 | 方法 |
|---------|---------|------|
| 创建聊天 | `/chat` | POST |
| 流式响应 | `/stream/{chat_id}` | GET (SSE) |
| 健康检查 | `/health` | GET |

## 🎬 演示

运行演示脚本查看所有功能：
```bash
python demo.py
```

## 📝 开发说明

### 项目结构
```
proteus-ai/
├── cli_tool.py           # 主CLI工具
├── proteus-cli.py        # Python启动器
├── proteus-cli.sh        # Unix启动脚本
├── proteus-cli.bat       # Windows启动脚本
├── requirements_cli.txt  # 依赖包
├── demo.py              # 演示脚本
├── CLI_USAGE.md         # 详细文档
└── CLI_README.md        # 本文档
```

### 技术栈
- **HTTP客户端**: aiohttp, requests
- **SSE客户端**: sseclient-py
- **终端颜色**: colorama
- **异步处理**: asyncio
- **命令行解析**: argparse

### 扩展开发
工具采用模块化设计，易于扩展新功能：
- 添加新的响应事件类型
- 支持更多配置选项
- 集成更多AI模型
- 添加插件系统

## 📄 许可证

遵循Proteus AI项目许可证。

---

**💡 提示**: 首次使用建议运行 `python demo.py` 来熟悉工具功能！