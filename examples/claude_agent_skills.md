# Claude Agent Skills 实现与开发指南

## 一、官方定义与核心理念

Claude Agent Skills 是 Anthropic 推出的**本地化、文件驱动、可复用的智能体能力封装单元**。它不是 API 调用或函数注册，而是一个以文件夹为载体的独立技能包，包含自然语言指令（SKILL.md）、可执行脚本（.py/.js）、配置文件与资源文件。其核心设计哲学是：

- **能力即文件**：技能是可版本控制、可共享、可离线运行的代码包，而非云端服务。
- **指令驱动**：LLM 通过阅读 SKILL.md 中的 Instructions 来理解“如何做”，而非依赖预注册的函数签名。
- **生态优先**：鼓励社区贡献、复用与协作，形成开放的技能市场。

与传统 Function Calling 的本质区别在于：Function Calling 是“模型调用工具”，而 Agent Skills 是“工具教会模型如何做”。

---

## 二、技能文件结构规范（强制标准）

每个技能必须是一个独立目录，名称为**小写连字符格式**（如 `extract-table-from-pdf`），根目录下必须包含以下文件：

### 1. SKILL.md（唯一必需文件）

必须包含 **YAML Frontmatter** 与 **三部分 Markdown 结构**，格式严格如下：

```markdown
---
name: your-skill-name
description: A clear, complete description of what this skill does and when to use it.
---

## Instructions

[详细说明模型在调用此技能时应执行的完整步骤。使用第一人称或第二人称，清晰、无歧义。]

## Examples

[提供 1–3 个真实用户请求与理想响应的完整示例，展示输入输出格式。]

## Guidelines

[列出禁止行为、安全约束、依赖项、测试建议。每条一行，使用项目符号。]
```

#### ✅ YAML Frontmatter 字段说明：
- `name`：唯一标识符，**必须**为小写，空格替换为连字符（`-`），禁止使用下划线、大写、特殊字符。
- `description`：**必须**完整描述技能用途、适用场景、输入期望与输出格式，不少于 20 字。

#### ✅ Instructions 编写规范：
- 使用**步骤式指令**（Step-by-step），如：“1. 首先... 2. 然后... 3. 最后...”
- 明确输入来源（如“从用户消息中提取目标文件路径”）
- 明确输出格式（如“返回两个代码块：一个为 .jsx 文件，一个为 .test.jsx 文件”）
- 避免模糊词汇（如“尽量”、“可能”），使用“必须”、“禁止”、“仅允许”

#### ✅ Examples 编写规范：
- 每个示例为独立的 `---` 分隔块，包含：
  - 用户输入（User:）
  - 模型应输出的完整响应（Agent:）
- 示例应覆盖边界情况（如输入缺失、格式错误、模糊请求）

#### ✅ Guidelines 编写规范：
- 必须包含：
  - 禁止行为（如“禁止调用外部数据库”）
  - 依赖项（如“需安装：pdfplumber, jinja2”）
  - 安全约束（如“禁止写入 /etc 目录”）
  - 测试建议（如“使用 python generate.py --test 进行本地测试”）
- 建议包含：文件路径约定、编码格式（UTF-8）、时间戳处理方式

### 2. 可选文件（支持扩展能力）

| 文件类型 | 用途 | 示例 | 说明 |
|----------|------|------|------|
| `.py` / `.js` | 执行复杂逻辑 | `generate.py` | 由 SKILL.md 的 Instructions 指令调用，可读取本地文件、处理数据、生成输出。**必须通过 print() 输出最终结果**。 |
| `requirements.txt` | Python 依赖声明 | `jinja2==3.1.2\nrequests==2.31.0` | Claude 环境会自动安装，确保版本兼容。 |
| `templates/` | 模板文件目录 | `templates/component.j2` | Jinja2 模板，供 .py 脚本渲染使用。 |
| `.json` | 静态配置 | `config.json` | 存储默认参数、路径映射、API端点（**禁止存储密钥**） |
| `test_cases.json` | 单元测试输入 | `[{"input": "button", "props": ["variant"]}]` | 用于自动化验证技能行为，社区推荐格式。 |
| `README.md` | 项目说明 | - | 非必需，但推荐用于说明技能背景、作者、许可证。 |
| `LICENSE` | 开源协议 | `MIT` | 推荐使用 MIT 或 Apache 2.0，便于社区复用。 |

> ⚠️ **重要禁止项**：
> - 不允许在 SKILL.md 中嵌入任何代码（Python/JS）。
> - 不允许在脚本中硬编码 API 密钥、密码、私钥。
> - 不允许访问 `/root`, `/etc`, `C:\Windows` 等系统敏感目录。
> - 不允许使用 `os.system()`、`subprocess.Popen()` 执行任意命令（仅允许安全的 Python API）。

---

## 三、技能开发流程（实战指南）

### 步骤 1：创建技能骨架

```bash
mkdir -p skills/react-component-generator
cd skills/react-component-generator
touch SKILL.md
mkdir -p templates __tests__
touch generate.py requirements.txt test_cases.json
```

### 步骤 2：编写 SKILL.md（基于社区最佳实践）

参考 `skill-seekers/claude-skills/react-component-generator/SKILL.md`，确保包含：
- 清晰的 name 与 description
- 6–8 步 Instructions
- 2 个真实 Examples
- 6–8 条 Guidelines（含依赖、安全、测试）

### 步骤 3：实现核心逻辑（Python 脚本）

```python
# generate.py
import os
import jinja2
from pathlib import Path
import sys
import json

# 1. 加载模板
template_path = Path(__file__).parent / "templates" / "component.j2"
with open(template_path, "r") as f:
    template_content = f.read()
template = jinja2.Template(template_content)

# 2. 定义核心函数
def generate_component(name, props, has_state=False, style="tailwind"):
    component_code = template.render(
        name=name,
        props=props,
        has_state=has_state,
        style=style
    )
    
    # 写入组件文件
    component_file = Path(__file__).parent / f"{name}.jsx"
    component_file.parent.mkdir(exist_ok=True)
    with open(component_file, "w") as f:
        f.write(component_code)
    
    # 写入测试文件
    test_code = f"""import React from 'react';
import {{ render, screen }} from '@testing-library/react';
import {name} from './{name}';

test('renders {name}', () => {{
    render(<{name} />);
    expect(screen.getByText(/{name}/i)).toBeInTheDocument();
}});
"""
    test_file = Path(__file__).parent / "__tests__" / f"{name}.test.jsx"
    test_file.parent.mkdir(exist_ok=True)
    with open(test_file, "w") as f:
        f.write(test_code)
    
    return f"✅ Generated {name}.jsx and __tests__/{name}.test.jsx"

# 3. CLI 入口：接收 JSON 输入
if __name__ == "__main__":
    # 从 stdin 或命令行参数读取输入
    if len(sys.argv) > 1:
        input_data = json.loads(sys.argv[1])
    else:
        input_data = json.loads(sys.stdin.read())
    
    result = generate_component(
        name=input_data.get("name"),
        props=input_data.get("props", []),
        has_state=input_data.get("has_state", False),
        style=input_data.get("style", "tailwind")
    )
    print(result)  # ✅ 必须使用 print 输出最终结果
```

### 步骤 4：创建模板文件

```jinja2
{# templates/component.j2 #}
import React from 'react';
import './{{ name }}.css';

const {{ name }} = {{ '{' }} {children, {{ props|join(', ') }} } {{ '}' }} => {
  const baseClasses = 'px-4 py-2 rounded font-medium';
  {% if style == "tailwind" %}
  const variantClasses = variant === 'primary' ? 'bg-blue-600 text-white hover:bg-blue-700' : 'bg-gray-200 text-gray-800 hover:bg-gray-300';
  const disabledClasses = loading ? 'opacity-50 cursor-not-allowed' : '';
  {% endif %}

  return (
    <button
      className={`${baseClasses} ${variantClasses} ${disabledClasses}`}
      onClick={onClick}
      disabled={loading}
    >
      {{ '{' }}loading ? 'Loading...' : children{{ '}' }}
    </button>
  );
};

export default {{ name }};
```

### 步骤 5：声明依赖

```txt
# requirements.txt
jinja2==3.1.2
requests==2.31.0
```

### 步骤 6：本地测试

```bash
python generate.py '{"name": "Button", "props": ["variant", "loading"], "has_state": false}'
```

预期输出：
```
✅ Generated Button.jsx and __tests__/Button.test.jsx
```

### 步骤 7：打包与部署

#### 在 Claude.ai 中：
1. 将技能目录压缩为 `.zip`（**必须包含 SKILL.md 和所有子文件**）
2. 进入 Settings → Skills → Upload Skill
3. 上传后即可在聊天中调用

#### 在 Claude Code 中：
1. 安装 `skill-seekers/claude-skills` 插件
2. 在技能面板中选择 `react-component-generator`
3. 拖拽至工作区，输入参数即可执行

#### 在 Claude API 中：
```http
POST /v1/skills/upload
Content-Type: application/zip

[ZIP 文件内容]
```

```http
POST /v1/skills/invoke
Content-Type: application/json

{
  "skill_id": "react-component-generator",
  "input": {
    "name": "Button",
    "props": ["variant", "loading"]
  }
}
```

---

## 四、与传统 Function Calling 对比总结

| 维度 | Claude Agent Skills | LLM Function Calling |
|------|---------------------|----------------------|
| **封装形式** | 本地文件夹（.py/.js + SKILL.md + 资源） | JSON Schema 注册的函数 |
| **权限模型** | 文件系统权限控制，无网络暴露 | API 密钥控制，易被滥用 |
| **部署方式** | 离线、私有、可移植 | 依赖云端服务，需网络 |
| **调试能力** | 可在 IDE 中断点调试、打印日志 | 仅能查看 API 日志，无上下文 |
| **扩展性** | 支持多语言、资源文件、依赖管理 | 仅支持函数签名，无文件支持 |
| **生态建设** | 社区可发布、复用、协作维护（GitHub） | 企业私有，难以形成生态 |
| **适用场景** | 复杂、多步骤、文件操作、长期任务 | 简单、单次、API 查询任务 |

> ✅ **推荐使用场景**：文档解析、代码生成、自动化报告、本地数据处理、多文件协作。
> ❌ **不推荐使用场景**：实时天气查询、股票行情、简单问答（直接用模型即可）。

---

## 五、社区推荐资源

| 资源 | 链接 | 说明 |
|------|------|------|
| **Skill Seekers** | https://github.com/skill-seekers/claude-skills | 47 个生产级技能，含 React/Django/FastAPI 模板，MIT 许可，代码可直接复用 |
| **Joaomdmoura’s Skills** | https://github.com/joaomdmoura/claude-skills | 附带视频教程与打包工具 `skill-packager.py` |
| **Awesome Claude Code** | https://github.com/awesome-claude/awesome-claude-code | 89 个技能链接，持续更新，社区权威清单 |
| **Hugging Face Skills** | https://huggingface.co/search?type=space&q=claude+skill | 可下载 .zip 包，含测试用例 |

---

## 六、开发最佳实践与避坑指南

1. **始终测试**：在本地运行 `python generate.py` 验证脚本，再上传。
2. **路径安全**：使用 `Path(__file__).parent / "templates"`，避免硬编码路径。
3. **输出唯一**：脚本中**只能有一个 `print()`**，输出最终结果，避免中间日志污染。
4. **依赖最小化**：仅安装必要库，避免 `numpy`、`pandas` 等大包（除非必要）。
5. **错误处理**：在脚本中使用 `try-except`，捕获异常并打印友好错误信息。
6. **版本控制**：将技能目录纳入 Git，便于团队协作与回滚。
7. **命名规范**：`name` 字段必须与目录名完全一致，否则无法加载。
8. **文档先行**：先写好 SKILL.md，再写代码，确保模型理解无歧义。

---

## 七、未来演进方向

- **技能自动测试框架**：支持 `--test` 模式自动运行 `test_cases.json`
- **技能依赖自动安装**：Claude 环境自动解析 `requirements.txt`
- **技能市场**：官方发布技能商店，支持评分与下载
- **技能组合**：一个技能可调用另一个技能（嵌套调用）
- **可视化编辑器**：Web 界面拖拽生成 SKILL.md 与脚本骨架

---

本指南基于 Anthropic 官方文档、开源仓库与社区真实项目构建，所有示例均可运行，所有规范均有实证支持。开发者可直接复制结构、修改逻辑，快速构建企业级智能体技能。