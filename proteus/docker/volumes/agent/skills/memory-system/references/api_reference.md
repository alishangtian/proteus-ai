# 记忆系统CLI参考手册

## 概述

记忆系统提供纯命令行接口(CLI)，所有操作均可通过`memory_cli.py`脚本完成，无需编写Python代码或初始化类。CLI接口设计简洁，支持记忆存储、检索、统计等核心功能。

## 命令行基础

### 脚本位置
```bash
/app/.proteus/skills/memory-system/scripts/memory_cli.py
```

### 通用参数
所有命令都支持以下通用参数：
- `--config <path>`: 指定配置文件路径（可选，默认自动发现）

### 配置自动发现机制
CLI脚本会自动查找配置文件，优先级如下：
1. 通过`--config`参数指定
2. 环境变量`MEMORY_CONFIG_PATH`
3. `/app/data/memory/config.yaml`
4. 默认模板配置

### 环境变量
```bash
# 指定配置文件路径
export MEMORY_CONFIG_PATH="/path/to/your/config.yaml"

# OpenAI API密钥（如果使用OpenAI）
export OPENAI_API_KEY="sk-..."
```

## 核心命令

### 1. `store` - 存储记忆

存储新的记忆内容。

**语法：**
```bash
python memory_cli.py store [参数]
```

**参数：**
| 参数 | 缩写 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--content` |  | 是 | - | 记忆内容文本 |
| `--memory-type` |  | 否 | `auto` | 记忆类型：`auto`, `short_term`, `medium_term`, `long_term` |
| `--importance` |  | 否 | `0.5` | 重要性评分 (0.0-1.0) |
| `--tags` |  | 否 | - | 标签列表，用逗号分隔 |
| `--metadata` |  | 否 | - | 元数据，JSON格式 |

**示例：**
```bash
# 基本存储
python memory_cli.py store --content "用户喜欢黑咖啡，每天早上一杯"

# 存储带标签和重要性的记忆
python memory_cli.py store \
  --content "用户是软件工程师，擅长Python" \
  --importance 0.8 \
  --tags "职业,技能,编程" \
  --memory-type long_term

# 存储带元数据的记忆
python memory_cli.py store \
  --content "项目会议纪要" \
  --metadata '{"project": "AI助手", "participants": ["Alice", "Bob"]}'
```

### 2. `retrieve` - 检索记忆

检索相关的记忆内容。

**语法：**
```bash
python memory_cli.py retrieve [参数]
```

**参数：**
| 参数 | 缩写 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--query` |  | 否 | - | 搜索查询文本 |
| `--memory-types` |  | 否 | - | 记忆类型列表，用逗号分隔 |
| `--limit` |  | 否 | `10` | 返回结果数量限制 |
| `--no-semantic` |  | 否 | - | 禁用语义搜索（默认启用） |

**示例：**
```bash
# 基本检索
python memory_cli.py retrieve --query "咖啡"

# 检索特定类型的记忆
python memory_cli.py retrieve \
  --query "编程" \
  --memory-types "long_term,medium_term" \
  --limit 5

# 仅关键词检索（禁用语义搜索）
python memory_cli.py retrieve \
  --query "会议" \
  --no-semantic

# 获取所有记忆（不指定查询）
python memory_cli.py retrieve --limit 20
```

### 3. `stats` - 获取统计信息

获取记忆系统的统计信息。

**语法：**
```bash
python memory_cli.py stats
```

**输出示例：**
```
📊 记忆系统统计:
   短期记忆: 15 条
   中期记忆: 42 条
   长期记忆: 128 条
   总计: 185 条
```

## 使用场景示例

### 场景1：记录用户偏好
```bash
# 记录饮食偏好
python memory_cli.py store \
  --content "用户不喜欢甜食，偏爱咸味零食" \
  --importance 0.7 \
  --tags "饮食,偏好,零食"

# 记录工作习惯
python memory_cli.py store \
  --content "用户习惯在早上处理重要工作，下午开会" \
  --importance 0.6 \
  --tags "工作习惯,日程"
```

### 场景2：会话摘要存储
```bash
# 存储会话摘要
python memory_cli.py store \
  --content "会话摘要：讨论了AI记忆系统的设计，用户提出了简化配置的需求" \
  --memory-type medium_term \
  --importance 0.5 \
  --tags "session_summary,AI讨论"
```

### 场景3：跨脚本记忆共享
```bash
#!/bin/bash
# 在Shell脚本中使用记忆系统

# 存储当前任务状态
python memory_cli.py store \
  --content "数据处理任务完成，生成了100条记录" \
  --tags "任务状态,数据处理"

# 检索相关配置
python memory_cli.py retrieve \
  --query "数据处理配置" \
  --limit 3
```

### 场景4：通过子进程调用
```python
# 在Python中通过子进程调用CLI
import subprocess
import json

# 存储记忆
result = subprocess.run([
    "python", "/app/.proteus/skills/memory-system/scripts/memory_cli.py",
    "store",
    "--content", "通过子进程存储的记忆",
    "--importance", "0.6",
    "--tags", "自动化,子进程"
], capture_output=True, text=True)

print(result.stdout)
```

## 输出格式

### 存储操作输出
```
✅ 记忆存储成功！
   记忆ID: ltm_abc123def456
   内容: 用户喜欢黑咖啡，每天早上一杯...
   类型: long_term
   重要性: 0.8
```

### 检索操作输出
```
🔍 检索到 5 条记忆:

1. ============================================================
   ID: ltm_abc123def456
   内容: 用户喜欢黑咖啡，每天早上一杯
   类型: long_term
   重要性: 0.85
   相关度: 0.92
   标签: 饮食, 偏好, 咖啡
   时间: 2025-01-30 10:30:00
```

### JSON输出（用于脚本处理）
```bash
# 可以通过重定向输出到文件
python memory_cli.py retrieve --query "咖啡" --limit 1 > result.json

# 或者使用管道处理
python memory_cli.py retrieve --query "会议" | jq '.'  # 需要jq工具
```

## 高级用法

### 批量操作
```bash
# 批量存储记忆
for item in "早餐习惯" "运动频率" "阅读偏好"; do
    python memory_cli.py store \
        --content "用户有规律的${item}" \
        --importance 0.6 \
        --tags "习惯,${item}"
done

# 批量导出记忆
python memory_cli.py retrieve --limit 100 > all_memories.txt
```

### 结合环境变量
```bash
# 使用自定义配置
export MEMORY_CONFIG_PATH="/app/data/custom_memory_config.yaml"
python memory_cli.py stats

# 临时覆盖配置
MEMORY_CONFIG_PATH="/tmp/test_config.yaml" python memory_cli.py store --content "测试记忆"
```

### 定时任务
```bash
# 每天清理任务
0 2 * * * python /app/.proteus/skills/memory-system/scripts/memory_cli.py stats >> /var/log/memory_system.log

# 每小时备份重要记忆
0 * * * * python /app/.proteus/skills/memory-system/scripts/memory_cli.py retrieve --importance 0.7 --limit 50 > /backups/memory_$(date +\%Y\%m\%d\%H).json
```

## 错误处理

### 常见错误及解决方案

| 错误信息 | 可能原因 | 解决方案 |
|----------|----------|----------|
| `配置文件不存在` | 配置文件路径错误 | 使用`--config`指定正确路径或运行初始化脚本 |
| `记忆存储失败` | 存储目录不可写 | 检查目录权限，确保有写入权限 |
| `检索超时` | 记忆数量过多或查询复杂 | 增加`--limit`限制，或添加更具体的过滤条件 |
| `语义搜索不可用` | Chroma向量数据库未初始化 | 运行初始化脚本创建向量数据库 |
| `LLM调用失败` | API密钥错误或网络问题 | 检查LLM配置和网络连接 |

### 调试模式
```bash
# 启用详细日志
export MEMORY_DEBUG=1
python memory_cli.py store --content "测试记忆"

# 查看完整错误信息
python memory_cli.py retrieve --query "测试" 2>&1
```

## 性能优化建议

### 1. 合理使用标签
- 为记忆添加3-5个相关标签，提高检索精度
- 使用一致的标签命名规范
- 避免过多标签导致索引膨胀

### 2. 重要性评分策略
- 关键信息：0.8-1.0
- 重要信息：0.6-0.8  
- 一般信息：0.4-0.6
- 临时信息：0.0-0.4

### 3. 检索优化
- 指定`--memory-types`缩小搜索范围
- 合理设置`--limit`避免返回过多结果
- 对于精确匹配，使用`--no-semantic`禁用语义搜索

## 与其他工具集成

### 与cron集成
```bash
# 每日统计报告
0 9 * * * python /app/.proteus/skills/memory-system/scripts/memory_cli.py stats | mail -s "记忆系统日报" admin@example.com
```

### 与监控系统集成
```bash
# Nagios检查脚本
#!/bin/bash
count=$(python memory_cli.py stats 2>/dev/null | grep "总计" | awk '{print $2}')
if [ "$count" -lt 1 ]; then
    echo "CRITICAL: 记忆系统无数据"
    exit 2
else
    echo "OK: 记忆系统有 ${count} 条记忆"
    exit 0
fi
```

### 与日志系统集成
```bash
# 将所有CLI操作记录到syslog
python memory_cli.py "$@" | logger -t "memory_system"
```

## 迁移说明

### 从API调用迁移到CLI

**旧的Python代码：**
```python
from memory_manager import MemoryManager

mm = MemoryManager()
memory_id = mm.store(content="用户偏好", importance=0.8)
```

**新的CLI方式：**
```bash
# 直接在命令行执行
python memory_cli.py store --content "用户偏好" --importance 0.8

# 或在Python中通过子进程调用
subprocess.run(["python", "memory_cli.py", "store", "--content", "用户偏好", "--importance", "0.8"])
```

### 优势对比
| 特性 | API方式 | CLI方式 |
|------|---------|---------|
| **易用性** | 需要编写Python代码 | 直接命令行操作 |
| **部署** | 需要导入模块和初始化 | 无需初始化，开箱即用 |
| **调试** | 需要Python调试工具 | 标准输出，易于查看 |
| **集成** | 仅限Python环境 | 支持任何能调用Shell的环境 |
| **维护** | 需要管理Python依赖 | 依赖已封装在脚本中 |

## 常见问题解答

### Q: CLI方式支持所有功能吗？
A: 是的，CLI方式支持记忆系统的所有核心功能，包括存储、检索、统计等。高级功能如记忆压缩、批量导入等也可以通过CLI参数或组合命令实现。

### Q: 如何查看帮助信息？
A: 运行`python memory_cli.py --help`查看全局帮助，或`python memory_cli.py <command> --help`查看具体命令帮助。

### Q: 可以同时处理多个用户吗？
A: 可以，通过在记忆内容或元数据中添加用户标识来区分不同用户的记忆。例如：`--metadata '{"user_id": "user_123"}'`

### Q: 支持增量备份吗？
A: 是的，可以通过定期运行检索命令导出新增记忆实现增量备份。

### Q: CLI工具可以远程调用吗？
A: 可以，只要目标服务器可以访问脚本和配置文件，就可以通过SSH远程调用。

---

## 更新日志

### v2.2 (当前版本)
- ✅ **纯CLI接口**：移除Python API，所有操作通过命令行完成
- ✅ **配置自动发现**：智能查找配置文件，简化部署
- ✅ **精简配置**：默认只包含LLM和Ollama必要配置
- ✅ **完善错误处理**：友好的错误提示和调试信息

### v2.1
- ✅ 基础CLI接口
- ✅ 支持存储、检索、统计命令
- ✅ 基本错误处理

---

**提示**：更多技术细节请参考 `architecture.md`，最佳实践请参考 `best_practices.md`。
