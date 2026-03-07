#!/usr/bin/env python3
"""
Multi-task deep research initialization script
支持依赖关系的子任务管理，支持英文文件夹名称
"""

import os
import json
import shutil
import re
from datetime import datetime

def validate_folder_name(folder_name):
    """
    验证文件夹名称是否为有效的英文名称
    
    Args:
        folder_name: 文件夹名称
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not folder_name:
        return False, "文件夹名称不能为空"
    
    # 允许的字符: 字母、数字、下划线、连字符、点
    if not re.match(r'^[a-zA-Z0-9_.-]+$', folder_name):
        return False, f"文件夹名称 '{folder_name}' 包含无效字符。只能使用英文、数字、下划线(_)、连字符(-)和点(.)"
    
    # 不能以点开头或结尾
    if folder_name.startswith('.') or folder_name.endswith('.'):
        return False, "文件夹名称不能以点开头或结尾"
    
    # 不能包含连续的点
    if '..' in folder_name:
        return False, "文件夹名称不能包含连续的点"
    
    # 长度限制
    if len(folder_name) > 100:
        return False, "文件夹名称过长，最多100个字符"
    
    # 保留名称检查
    reserved_names = ['con', 'prn', 'aux', 'nul', 'com1', 'com2', 'com3', 'com4', 
                     'com5', 'com6', 'com7', 'com8', 'com9', 'lpt1', 'lpt2', 
                     'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9']
    if folder_name.lower() in reserved_names:
        return False, f"文件夹名称 '{folder_name}' 是系统保留名称"
    
    return True, ""



def generate_english_folder_name(text, prefix="task"):
    """
    从文本生成英文文件夹名称
    
    Args:
        text: 输入文本（可能是中文）
        prefix: 名称前缀
    
    Returns:
        str: 英文文件夹名称
    """
    import re
    from datetime import datetime
    
    # 首先尝试提取英文部分
    english_parts = []
    for char in text:
        if 'a' <= char <= 'z' or 'A' <= char <= 'Z' or '0' <= char <= '9':
            english_parts.append(char)
        elif char in ' _-.':
            english_parts.append('_')
    
    if english_parts:
        # 有英文字符，使用它们
        name = ''.join(english_parts)
        # 清理连续下划线
        name = re.sub(r'_+', '_', name)
        name = name.strip('_')
        if name and len(name) >= 2:
            return name
    
    # 如果没有足够的英文字符，使用前缀+时间戳
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}"
def create_subtask_structure(task_dir, subtask_name, subtask_description, dependencies=None, subtask_query=None, subtask_folder_name=None):
    # 初始化变量
    clean_subtask_name = ""

    """
    Create directory structure and files for a subtask with dependencies support
    
    Args:
        task_dir: Main task directory
        subtask_name: Name of the subtask (显示名称，可以是中文)
        subtask_description: Description of the subtask
        dependencies: List of subtask names this task depends on (default: empty list)
        subtask_query: Research query for this subtask
        subtask_folder_name: 子任务文件夹名称 (英文，如未提供则基于subtask_name生成)
    """
    # 生成或验证子任务文件夹名称
    # 生成或验证子任务文件夹名称
    if subtask_folder_name:
        is_valid, error_msg = validate_folder_name(subtask_folder_name)
        if is_valid:
            clean_subtask_name = subtask_folder_name  # 使用用户提供的有效名称
        else:
            print(f"警告: 子任务文件夹名称 '{subtask_folder_name}' 无效: {error_msg}")
            # 回退到基于名称生成
            # 使用辅助函数生成英文文件夹名称
            clean_subtask_name = generate_english_folder_name(subtask_name, "subtask")
            clean_subtask_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', clean_subtask_name)
            # 确保不以点开头或结尾
            clean_subtask_name = clean_subtask_name.strip('.')
            if not clean_subtask_name:
                clean_subtask_name = f"subtask_{len(os.listdir(os.path.join(task_dir, 'sub_tasks'))) + 1}"
    else:
        # 基于名称生成英文文件夹名称
        clean_subtask_name = subtask_name.replace(" ", "_").replace("/", "_")
        # 移除非英文数字字符
        clean_subtask_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', clean_subtask_name)
        # 确保不以点开头或结尾
        clean_subtask_name = clean_subtask_name.strip('.')
        if not clean_subtask_name:
            clean_subtask_name = f"subtask_{len(os.listdir(os.path.join(task_dir, 'sub_tasks'))) + 1}"
    
    # 最终验证
    is_valid, error_msg = validate_folder_name(clean_subtask_name)
    if not is_valid:
        # 如果仍然无效，使用安全名称
        clean_subtask_name = f"subtask_{len(os.listdir(os.path.join(task_dir, 'sub_tasks'))) + 1}"
        print(f"警告: 生成的子任务文件夹名称无效，使用安全名称: {clean_subtask_name}")
    
    subtask_dir = os.path.join(task_dir, "sub_tasks", clean_subtask_name)
    os.makedirs(subtask_dir, exist_ok=True)
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Default dependencies to empty list
    if dependencies is None:
        dependencies = []
    
    # Format dependencies for display
    if dependencies:
        deps_display = "\n".join([f"- {dep}" for dep in dependencies])
    else:
        deps_display = "无"
    
    # Create subtask plan from template
    template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                 "templates", "sub_task_template.md")
    subtask_plan_path = os.path.join(subtask_dir, "task_plan.md")
    
    if os.path.exists(template_path):
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()
            
            # Replace template variables
            filled = template.replace("[子任务名称]", subtask_name)
            filled = filled.replace("[在此描述子任务的具体目标和研究问题]", subtask_description)
            filled = filled.replace("[YYYY-MM-DD HH:MM:SS]", current_time)
            filled = filled.replace("[主任务名称]", os.path.basename(task_dir))
            filled = filled.replace("[依赖的子任务名称，如无则写\"无\"]", deps_display)
            
            with open(subtask_plan_path, 'w', encoding='utf-8') as f:
                f.write(filled)
        except Exception as e:
            print(f"Warning: Could not use template: {e}")
            # Create simple plan
            with open(subtask_plan_path, 'w', encoding='utf-8') as f:
                f.write(f"# 子任务规划: {subtask_name}\n\n")
                f.write(f"## 子任务目标\n{subtask_description}\n\n")
                f.write(f"## 依赖任务\n{deps_display}\n\n")
                f.write(f"## 当前状态\n**状态:** pending\n**开始时间:** {current_time}\n")
    else:
        # Create simple plan
        with open(subtask_plan_path, 'w', encoding='utf-8') as f:
            f.write(f"# 子任务规划: {subtask_name}\n\n")
            f.write(f"## 子任务目标\n{subtask_description}\n\n")
            f.write(f"## 依赖任务\n{deps_display}\n\n")
            f.write(f"## 当前状态\n**状态:** pending\n**开始时间:** {current_time}\n")
    
    # Create empty findings.md
    findings_path = os.path.join(subtask_dir, "findings.md")
    with open(findings_path, 'w', encoding='utf-8') as f:
        f.write(f"# 研究发现: {subtask_name}\n\n")
        f.write(f"**子任务:** {subtask_name}\n**状态:** 进行中\n**开始时间:** {current_time}\n")
        f.write(f"**依赖任务:** {', '.join(dependencies) if dependencies else '无'}\n\n")
        f.write("## 关键发现\n[等待研究完成]\n\n")
        f.write("## 数据来源\n[等待研究完成]\n")
    
    # Create empty progress.md
    progress_path = os.path.join(subtask_dir, "progress.md")
    with open(progress_path, 'w', encoding='utf-8') as f:
        f.write(f"# 进度跟踪: {subtask_name}\n\n")
        f.write(f"**子任务:** {subtask_name}\n**状态:** 未开始\n**进度:** 0%\n")
        f.write(f"**依赖任务:** {', '.join(dependencies) if dependencies else '无'}\n\n")
        f.write("## 活动日志\n")
        f.write(f"- {current_time}: 子任务创建\n")
    
    return clean_subtask_name

def init_multi_task_research(task_name, task_description, subtasks=None, base_dir="/app/data/tasks", auth_token=None,
                             auto_start_subtasks=False, api_config=None, task_folder_name=None):
    """
    Initialize multi-task research project with dependency support
    
    Args:
        task_name: Name of the main task (显示名称，可以是中文)
        task_description: Description of the main task
        subtasks: List of subtask dictionaries with 'name', 'description',
                 and optionally 'dependencies', 'query', and 'folder_name'
        base_dir: Base directory for tasks
        auth_token: task下发的鉴权token (新增参数)
        auto_start_subtasks: Whether to automatically start subtasks after creation
        api_config: API configuration for starting subtasks
        task_folder_name: 任务文件夹名称 (英文，如未提供则基于task_name生成)
    """
    
    # 鉴权token处理 - 强制性追问
    if not auth_token:
        # 尝试从环境变量获取
        auth_token = os.environ.get("TASK_AUTH_TOKEN")
    
    if not auth_token:
        # 检查是否在交互模式下运行
        if __name__ == "__main__":
            # 交互式提示用户输入
            auth_token = input("请提供task下发的鉴权token: ").strip()
            if not auth_token:
                print("错误: 鉴权token是必需的")
                return None
        else:
            # 非交互模式，抛出异常
            raise ValueError("鉴权token是必需的。请通过auth_token参数或TASK_AUTH_TOKEN环境变量提供。")
    
    # 将token合并到api_config中
    if api_config is None:
        api_config = {}
    
    # 优先使用直接提供的auth_token参数
    api_config["auth_token"] = auth_token
    
    # 生成或验证任务文件夹名称
    if task_folder_name:
        is_valid, error_msg = validate_folder_name(task_folder_name)
        if not is_valid:
            print(f"错误: 任务文件夹名称 '{task_folder_name}' 无效: {error_msg}")
            return None
    else:
        # 基于任务名称生成英文文件夹名称
        # 使用辅助函数生成英文文件夹名称
        task_folder_name = generate_english_folder_name(task_name, "task")
        # 移除非英文数字字符
        task_folder_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', task_folder_name)
        # 确保不以点开头或结尾
        task_folder_name = task_folder_name.strip('.')
        if not task_folder_name:
            task_folder_name = "multi_task_research"
        print(f"注意: 未指定任务文件夹名称，使用生成的名称: {task_folder_name}")
    
    task_dir = os.path.join(base_dir, task_folder_name)
    
    print(f"初始化多任务研究: {task_name}")
    print(f"任务文件夹: {task_folder_name}")
    
    try:
        # Create directories
        os.makedirs(task_dir, exist_ok=True)
        os.makedirs(os.path.join(task_dir, "sub_tasks"), exist_ok=True)
        os.makedirs(os.path.join(task_dir, "reports"), exist_ok=True)
        os.makedirs(os.path.join(task_dir, "data", "sources"), exist_ok=True)
        os.makedirs(os.path.join(task_dir, "data", "analysis"), exist_ok=True)
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create master files from templates if available
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
        
        # master_task_plan.md
        master_plan_path = os.path.join(task_dir, "master_task_plan.md")
        master_plan_template = os.path.join(template_dir, "master_task_plan.md")
        
        if os.path.exists(master_plan_template):
            with open(master_plan_template, 'r', encoding='utf-8') as f:
                template = f.read()
            filled = template.replace("[任务名称]", task_name)
            filled = filled.replace("[任务描述]", task_description)
            filled = filled.replace("[YYYY-MM-DD HH:MM:SS]", current_time)
            with open(master_plan_path, 'w', encoding='utf-8') as f:
                f.write(filled)
        else:
            with open(master_plan_path, 'w', encoding='utf-8') as f:
                f.write(f"# 主任务规划: {task_name}")
                f.write(f"## 总体目标{task_description}")
                f.write(f"# 当前状态**状态:** planning**开始时间:** {current_time}")
        
        # master_findings.md
        master_findings_path = os.path.join(task_dir, "master_findings.md")
        master_findings_template = os.path.join(template_dir, "master_findings.md")
        
        if os.path.exists(master_findings_template):
            shutil.copy(master_findings_template, master_findings_path)
        else:
            with open(master_findings_path, 'w', encoding='utf-8') as f:
                f.write(f"# 主研究发现: {task_name}## 执行摘要[等待研究完成]")
        
        # master_progress.md
        master_progress_path = os.path.join(task_dir, "master_progress.md")
        master_progress_template = os.path.join(template_dir, "master_progress.md")
        
        if os.path.exists(master_progress_template):
            shutil.copy(master_progress_template, master_progress_path)
        else:
            with open(master_progress_path, 'w', encoding='utf-8') as f:
                f.write(f"# 主任务进度: {task_name}## 总体进度**总体进度:** 0%")
        
        # Prepare subtasks list
        if subtasks is None:
            subtasks = []
        
        subtask_configs = []
        subtask_name_map = {}  # Map subtask names to their configs for dependency validation
        
        print(f"创建 {len(subtasks)} 个子任务...")
        for subtask in subtasks:
            subtask_name = subtask.get("name", f"子任务 {len(subtask_configs)+1}")
            subtask_desc = subtask.get("description", "")
            subtask_deps = subtask.get("dependencies", [])  # List of subtask names
            subtask_query = subtask.get("query", subtask_desc)
            subtask_folder = subtask.get("folder_name")  # 可选的子任务文件夹名称
            
            print(f"  创建子任务: {subtask_name}")
            if subtask_deps:
                print(f"    依赖: {', '.join(subtask_deps)}")
            
            clean_subtask_name = create_subtask_structure(
                task_dir, subtask_name, subtask_desc, subtask_deps, subtask_query, subtask_folder
            )
            
            subtask_config = {
                "name": subtask_name,
                "clean_name": clean_subtask_name,
                "description": subtask_desc,
                "query": subtask_query,
                "directory": clean_subtask_name,
                "dependencies": subtask_deps,  # Store dependencies
                "status": "pending",
                "progress": 0.0,
                "created_at": current_time,
                "started_at": None,
                "completed_at": None,
                "last_activity": current_time,
                "error_count": 0,
                "api_calls": 0
            }
            subtask_configs.append(subtask_config)
            subtask_name_map[subtask_name] = subtask_config
        
        # Validate dependencies
        print("验证依赖关系...")
        valid = True
        for subtask_config in subtask_configs:
            for dep_name in subtask_config["dependencies"]:
                if dep_name not in subtask_name_map:
                    print(f"  ⚠ 警告: 子任务 '{subtask_config['name']}' 依赖不存在的子任务 '{dep_name}'")
                    valid = False
                else:
                    print(f"  ✓ 子任务 '{subtask_config['name']}' -> '{dep_name}' (依赖存在)")
        
        if not valid:
            print("⚠ 警告: 存在无效依赖关系，可能会影响任务执行顺序")
        
        # Default API configuration
        default_api_config = {
            "endpoint": "https://nginx/task",
            "auth_token": auth_token,  # 使用用户提供的token
            "model_name": "deepseek-reasoner",
            "itecount": 200,
            "conversation_round": 5,
            "tool_choices": ["serper_search", "web_crawler", "python_execute"],
            "selected_skills": ["planning-with-files"],
        }
        
        # Merge with provided API config
        final_api_config = default_api_config.copy()
        if api_config:
            final_api_config.update(api_config)
        
        # Create task config
        task_config = {
            "task_name": task_name,
            "task_folder_name": task_folder_name,  # 存储使用的文件夹名称
            "task_description": task_description,
            "created_at": current_time,
            "updated_at": current_time,
            "status": "planning",
            "base_dir": task_dir,
            "subtasks": subtask_configs,
            "monitoring": {
                "enabled": True,
                "interval_seconds": 300,
                "last_check": current_time,
                "next_check": current_time
            },
            "api_config": final_api_config,
            "metadata": {
                "version": "1.4.0",  # 更新版本
                "created_by": "multi-task-deep-research skill",
                "skill_version": "v1.4.0"
            },
            "overall_progress": 0.0
        }
        
        config_path = os.path.join(task_dir, "task_config.json")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(task_config, f, indent=2, ensure_ascii=False)
        
        print(f"✓ 项目创建成功: {task_dir}")
        print(f"  - 任务文件夹: {task_folder_name}")
        print(f"  - 创建 {len(subtask_configs)} 个子任务")
        print(f"  - 配置保存到: {config_path}")
        
        # Calculate dependency order for display
        try:
            from scripts.start_subtasks import topological_sort
            sorted_tasks = topological_sort(subtask_configs)
            print(f"  - 依赖执行顺序: {', '.join([t['name'] for t in sorted_tasks])}")
        except:
            # If topological_sort not available, just show warning
            print(f"  - 注意: 子任务有依赖关系，将按依赖顺序启动")
        
        # Auto-start subtasks if requested
        if auto_start_subtasks and subtask_configs:
            print("尝试自动启动子任务...")
            try:
                # Import and call start_subtasks function
                start_module_path = os.path.join(os.path.dirname(__file__), "start_subtasks.py")
                if os.path.exists(start_module_path):
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("start_subtasks", start_module_path)
                    start_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(start_module)
                    # Start tasks one by one considering dependencies
                    success = start_module.start_subtasks_sequential(task_dir, wait_for_completion=False)
                    if success:
                        print("✓ 所有子任务按依赖顺序启动成功")
                    else:
                        print("⚠ 部分子任务启动失败")
                else:
                    print("⚠ start_subtasks.py 未找到，跳过自动启动")
            except Exception as e:
                print(f"⚠ 自动启动失败: {e}")
        
        return task_dir
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return None