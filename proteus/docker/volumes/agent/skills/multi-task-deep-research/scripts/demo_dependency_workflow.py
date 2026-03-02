#!/usr/bin/env python3
"""
多任务深度研究技能演示脚本
展示依赖关系管理和顺序启动的完整工作流程
"""

import os
import sys
import json
from datetime import datetime

def demo_dependency_workflow():
    """
    演示完整的工作流程：
    1. 创建带有依赖关系的任务
    2. 按依赖顺序启动任务
    3. 监控任务状态
    4. 整合结果
    """
    
    print("=" * 60)
    print("多任务深度研究技能演示")
    print("依赖关系管理 + 顺序启动工作流")
    print("=" * 60)
    
    # 导入必要的模块
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, script_dir)
    
    try:
        # 1. 导入初始化模块
        from init_multi_task import init_multi_task_research
        
        # 2. 定义带有依赖关系的子任务
        print("\n1. 创建带有依赖关系的任务...")
        
        subtasks = [
            {
                "name": "市场调研",
                "description": "分析目标市场的基本情况",
                "dependencies": [],  # 无依赖
                "query": "2025年人工智能教育市场规模、增长率、主要玩家分析"
            },
            {
                "name": "竞品分析",
                "description": "分析主要竞争对手",
                "dependencies": ["市场调研"],  # 依赖市场调研
                "query": "人工智能教育领域主要竞争对手：产品特点、定价、市场份额"
            },
            {
                "name": "用户研究",
                "description": "研究目标用户需求",
                "dependencies": ["市场调研"],  # 依赖市场调研
                "query": "人工智能教育产品目标用户：用户画像、需求痛点、购买行为"
            },
            {
                "name": "战略规划",
                "description": "制定市场进入战略",
                "dependencies": ["市场调研", "竞品分析", "用户研究"],  # 依赖所有前期研究
                "query": "基于市场、竞品和用户研究，制定AI教育产品市场进入战略"
            }
        ]
        
        # 3. 初始化任务
        print("   创建任务: 'AI教育产品市场研究'")
        task_dir = init_multi_task_research(
            task_name="AI教育产品市场研究",
            task_description="通过多任务研究为AI教育产品上市提供全面市场分析",
            subtasks=subtasks,
            auto_start_subtasks=False,  # 手动控制启动
            api_config={
                "auth_token": "9921ff12-6ff6-4756-bc1a-37e22e04ae70",
                "model_name": "deepseek-reasoner"
            }
        )
        
        if not task_dir:
            print("   任务创建失败")
            return False
        
        print(f"   任务目录: {task_dir}")
        
        # 4. 检查任务配置
        config_path = os.path.join(task_dir, "task_config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            print(f"   创建了 {len(config['subtasks'])} 个子任务")
            print("   依赖关系:")
            for subtask in config['subtasks']:
                deps = subtask.get('dependencies', [])
                deps_str = f" -> {', '.join(deps)}" if deps else " (无依赖)"
                print(f"     - {subtask['name']}{deps_str}")
        
        print("\n2. 演示启动模式...")
        print("   a) 顺序启动模式 (默认): 按依赖顺序启动，一次一个任务")
        print("      命令: python start_subtasks.py <任务目录>")
        print("   b) 顺序等待模式: 每个任务完成后才启动下一个")
        print("      命令: python start_subtasks.py <任务目录> --wait")
        print("   c) 特定任务模式: 启动指定的任务")
        print("      命令: python start_subtasks.py <任务目录> --specific \"任务A\" \"任务B\"")
        
        print("\n3. 演示监控命令...")
        print("   命令: python monitor_tasks.py <任务目录>")
        print("   功能: 显示任务状态、依赖关系、进度信息")
        
        print("\n4. 演示结果整合命令...")
        print("   命令: python integrate_results.py <任务目录>")
        print("   功能: 整合所有子任务的研究发现")
        
        print("\n5. 实际执行示例...")
        print("   # 创建任务")
        print("   python init_multi_task.py \"AI教育市场研究\"")
        print("   ")
        print("   # 顺序启动（推荐用于有依赖的任务）")
        print("   python start_subtasks.py /app/data/tasks/AI教育市场研究")
        print("   ")
        print("   # 监控状态")
        print("   python monitor_tasks.py /app/data/tasks/AI教育市场研究")
        print("   ")
        print("   # 整合结果")
        print("   python integrate_results.py /app/data/tasks/AI教育市场研究")
        
        print("\n6. 依赖关系执行顺序:")
        print("   1. 市场调研 (无依赖)")
        print("   2. 竞品分析 (依赖市场调研)")
        print("   3. 用户研究 (依赖市场调研)")
        print("   4. 战略规划 (依赖所有前三项)")
        
        print("\n7. 关键特性总结:")
        print("   - ✅ 依赖关系自动排序 (拓扑排序)")
        print("   - ✅ 循环依赖检测和警告")
        print("   - ✅ 顺序启动 (一次只启动一个任务)")
        print("   - ✅ 等待模式 (任务完成后才启动下一个)")
        print("   - ✅ 详细状态监控 (包括waiting状态)")
        print("   - ✅ 与提供的API接口完全兼容")
        print("   - ✅ 重试机制和错误处理")
        
        print("\n8. API参数兼容性:")
        print("   所有API参数严格匹配用户提供的curl示例:")
        print("   - selected_skills: [\"planning-with-file\"]")
        print("   - tool_choices: [\"serper_search\", \"web_crawler\", \"python_execute\"]")
        print("   - model_name: \"deepseek-reasoner\"")
        print("   - itecount: 200")
        print("   - conversation_round: 5")
        print("   - tool_memory_enabled: false")
        print("   - enable_tools: true")
        print("   - stream: true")
        
        print("\n\" + \"=" * 60)
        print("演示完成")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"演示出错: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    demo_dependency_workflow()
