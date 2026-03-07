#!/usr/bin/env python3
"""
多任务深度研究基础功能 - 快速开始示例
"""

import sys
import os

# 添加技能目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import (
    init_workspace,
    add_subtasks,
    log_finding,
    update_status,
    check_status,
    generate_summary
)

def quick_demo():
    """快速演示所有功能"""
    
    print("=" * 50)
    print("多任务深度研究基础功能演示")
    print("=" * 50)
    
    # 1. 初始化工作区
    print("\n1. 初始化工作区...")
    result = init_workspace(
        workspace_path="/app/data/workspace/demo_research",
        plan_content="# 演示研究项目\n\n## 目标: 演示基础功能使用",
        overwrite=True  # 允许覆盖
    )
    
    if not result["ok"]:
        print(f"❌ 失败: {result['error']}")
        return
    
    workspace_path = result["data"]["workspace_path"]
    print(f"✅ 工作区创建成功: {workspace_path}")
    
    # 2. 添加子任务
    print("\n2. 添加子任务...")
    result = add_subtasks(workspace_path, [
        {"id": "analysis", "name": "分析任务", "description": "数据分析"},
        {"id": "research", "name": "研究任务", "description": "文献研究"}
    ])
    
    if result["ok"]:
        print(f"✅ 添加 {result['data']['total_created']} 个子任务")
        for task_id in result["data"]["subtasks_created"]:
            print(f"   - {task_id}")
    else:
        print(f"❌ 失败: {result['error']}")
    
    # 3. 记录研究发现
    print("\n3. 记录研究发现...")
    result = log_finding(
        workspace_path=workspace_path,
        target="subtasks/analysis",
        title="初步分析结果",
        content="数据分析显示，主要趋势是...",
        metadata={
            "category": "数据分析",
            "confidence": "medium",
            "tags": ["趋势", "分析"]
        }
    )
    
    if result["ok"]:
        print(f"✅ 发现记录成功: {result['data']['finding_id']}")
        print(f"   文件: {result['data']['file_path']}")
    else:
        print(f"❌ 失败: {result['error']}")
    
    # 4. 更新状态
    print("\n4. 更新子任务状态...")
    result = update_status(
        workspace_path=workspace_path,
        subtask_id="analysis",
        status="working",
        progress=50,
        note="已完成初步分析"
    )
    
    if result["ok"]:
        print(f"✅ 状态更新: {result['data']['status']} ({result['data']['progress']}%)")
    else:
        print(f"❌ 失败: {result['error']}")
    
    # 5. 检查状态
    print("\n5. 检查工作区状态...")
    result = check_status(workspace_path, detailed=True)
    
    if result["ok"]:
        data = result["data"]
        print(f"✅ 状态检查完成")
        print(f"   总体进度: {data['overall_progress']}%")
        print(f"   子任务数: {data['subtask_count']}")
        print(f"   全部完成: {data['all_completed']}")
        
        if "subtask_status" in data:
            print("   子任务详情:")
            for task_id, info in data["subtask_status"].items():
                print(f"     - {task_id}: {info['status']} ({info['progress']}%)")
    else:
        print(f"❌ 失败: {result['error']}")
    
    # 6. 生成总结报告
    print("\n6. 生成总结报告...")
    result = generate_summary(workspace_path)
    
    if result["ok"]:
        print(f"✅ 报告生成成功")
        print(f"   报告路径: {result['data']['report_path']}")
        print(f"   便捷链接: {result['data']['summary_link']}")
        print(f"   发现数量: {result['data']['findings_count']}")
    else:
        print(f"❌ 失败: {result['error']}")
    
    print("\n" + "=" * 50)
    print("演示完成!")
    print(f"工作区位置: {workspace_path}")
    print(f"查看报告: {workspace_path}/latest_summary.md")
    print("=" * 50)

def minimal_example():
    """最简使用示例"""
    
    # 只使用核心功能
    result = init_workspace("/app/data/workspace/minimal", "# 最简项目")
    if result["ok"]:
        workspace = result["data"]["workspace_path"]
        
        # 添加一个子任务
        add_subtasks(workspace, [{"id": "task1"}])
        
        # 记录一个发现
        log_finding(workspace, "subtasks/task1", "发现标题", "发现内容")
        
        print(f"✅ 最简示例完成: {workspace}")
    else:
        print(f"❌ 失败: {result['error']}")

if __name__ == "__main__":
    # 运行快速演示
    quick_demo()
    
    print("\n\n运行最简示例...")
    minimal_example()
