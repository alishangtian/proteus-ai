# TeamRole 动态创建优化说明

## 问题描述

在原有的 `TeamRunnerNode.execute()` 方法中，当配置文件包含不在 `TeamRole` 预定义范围内的角色名称时，代码会因为 `getattr(TeamRole, role_name)` 抛出 `AttributeError` 而失败。

## 优化方案

### 1. 新增辅助函数

在 `team_runner.py` 中新增了 `get_or_create_team_role(role_name: str) -> TeamRole` 函数：

```python
def get_or_create_team_role(role_name: str) -> TeamRole:
    """获取或创建团队角色
    
    Args:
        role_name (str): 角色名称
        
    Returns:
        TeamRole: 团队角色枚举实例
    """
    try:
        # 首先尝试获取预定义的角色
        return getattr(TeamRole, role_name)
    except AttributeError:
        # 如果角色不存在，动态创建
        logger.warning(f"角色 {role_name} 不在预定义的TeamRole中，动态创建新角色")
        role_value = role_name.lower()
        
        # 检查值是否已存在，避免重复创建
        for existing_role in TeamRole:
            if existing_role.value == role_value:
                logger.info(f"角色值 {role_value} 已存在，使用现有角色: {existing_role.name}")
                return existing_role
        
        # 使用正确的方式创建新的枚举成员
        new_role = object.__new__(TeamRole)
        new_role._name_ = role_name
        new_role._value_ = role_value
        
        # 将新角色添加到TeamRole枚举中
        setattr(TeamRole, role_name, new_role)
        # 更新TeamRole内部映射
        TeamRole._member_map_[role_name] = new_role
        TeamRole._value2member_map_[role_value] = new_role
        # 更新_member_names_列表
        if hasattr(TeamRole, '_member_names_'):
            TeamRole._member_names_.append(role_name)
        
        logger.info(f"成功创建新角色: {role_name} = {role_value}")
        return new_role
```

### 2. 优化execute方法

在 `TeamRunnerNode.execute()` 方法中：

**原始代码 (第107行):**
```python
tools_config[getattr(TeamRole, role_name)] = AgentConfiguration(...)
```

**优化后:**
```python
# 获取或创建角色枚举
role_enum = get_or_create_team_role(role_name)
tools_config[role_enum] = AgentConfiguration(...)
```

**原始代码 (第122行):**
```python
start_role=getattr(TeamRole, team_config["start_role"])
```

**优化后:**
```python
# 获取或创建起始角色
start_role_name = team_config["start_role"]
start_role_enum = get_or_create_team_role(start_role_name)
```

## 功能特性

### 1. 兼容性保持
- 所有预定义的 `TeamRole` 角色继续正常工作
- 不改变现有配置文件的行为

### 2. 动态扩展
- 支持在配置文件中定义任意角色名称
- 自动创建不存在的角色枚举项
- 避免重复创建相同角色

### 3. 日志支持
- 记录角色创建过程
- 区分预定义角色和动态创建角色

## 测试验证

创建了完整的测试套件 `test_custom_roles.py`，验证：

1. **预定义角色访问**: 确保现有角色正常工作
2. **自定义角色创建**: 验证动态创建功能
3. **重复创建处理**: 确保不会重复创建相同角色
4. **配置解析逻辑**: 验证完整的配置文件解析流程
5. **枚举完整性**: 确保枚举结构保持完整

## 使用示例

### 配置文件示例 (test_custom_roles.yaml)

```yaml
# 可以混合使用预定义角色和自定义角色
team_rules: "这是一个测试团队，包含自定义角色"
start_role: "CUSTOM_COORDINATOR"  # 自定义起始角色

roles:
  CUSTOM_COORDINATOR:  # 自定义角色
    tools: ["handoff"]
    prompt_template: "COORDINATOR_PROMPT_TEMPLATES"
    agent_description: "你是一个自定义的协调者角色"
    role_description: "自定义协调者"
    termination_conditions:
      - type: "ToolTerminationCondition"
        tool_names: ["final_answer"]
    model_name: "deepseek-chat"
    max_iterations: 3

  RESEARCHER:  # 预定义角色
    tools: ["web_crawler", "serper_search"]
    prompt_template: "RESEARCHER_PROMPT_TEMPLATES"
    agent_description: "你是一位专业的深度研究员"
    role_description: "研究员"
    termination_conditions:
      - type: "ToolTerminationCondition"
        tool_names: ["final_answer"]
    model_name: "deepseek-chat"
    max_iterations: 3
```

## 技术细节

### 枚举动态扩展机制

1. **安全检查**: 先尝试获取预定义角色，避免不必要的创建
2. **值冲突检测**: 检查角色值是否已存在，防止冲突
3. **正确的枚举创建**: 使用 `object.__new__()` 和正确的属性设置
4. **内部映射更新**: 更新枚举的所有内部映射表

### 日志级别

- `INFO`: 成功创建角色、使用预定义角色
- `WARNING`: 检测到自定义角色需要创建

## 向后兼容性

该优化完全向后兼容：
- 所有现有配置文件继续工作
- 预定义角色的行为不变
- 不影响现有的API接口

## 测试运行

```bash
cd proteus-ai/proteus
python test_custom_roles.py
```

测试结果应显示所有测试通过：
```
🎊 所有测试全部通过！