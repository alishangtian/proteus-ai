"""
基本使用示例
"""

import sys
import os

# 添加父目录到路径，以便导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import (
    SkillUsageMonitor,
    record_skill_usage,
    track_skill_usage,
    analyze_usage,
    generate_markdown_report
)


def example_record_usage():
    """示例：记录技能使用"""
    print("示例1: 记录技能使用")
    print("-" * 40)
    
    # 方法1: 使用函数记录
    from scripts import record_usage_now
    record_usage_now("example-skill", context_length=1500, success=True)
    print("✓ 记录了一次技能使用")
    
    # 方法2: 使用装饰器
    @record_skill_usage("decorated-skill")
    def execute_skill():
        print("  执行技能逻辑...")
        return "技能执行完成"
    
    result = execute_skill()
    print(f"✓ 使用装饰器记录: {result}")
    
    # 方法3: 使用上下文管理器
    with track_skill_usage("context-skill", context_length=2000) as tracker:
        print("  在上下文中执行技能...")
        # 模拟技能执行
        import time
        time.sleep(0.1)
    
    print("✓ 使用上下文管理器记录")
    print()


def example_analyze_usage():
    """示例：分析使用情况"""
    print("示例2: 分析技能使用")
    print("-" * 40)
    
    # 获取30天内的使用统计
    analysis = analyze_usage(days=30)
    
    print(f"总技能数: {analysis['summary']['total_skills']}")
    print(f"已使用技能: {analysis['summary']['used_skills']}")
    print(f"使用率: {analysis['summary']['usage_rate']}%")
    print(f"总使用次数: {analysis['summary']['total_usage_count']}")
    
    # 显示热门技能
    if analysis['top_skills']:
        print("\n热门技能 (前3):")
        for i, skill in enumerate(analysis['top_skills'][:3], 1):
            print(f"  {i}. {skill['name']}: {skill['usage_count']}次")
    
    # 显示低使用率技能
    if analysis['low_usage_skills']:
        print(f"\n低使用率技能: {len(analysis['low_usage_skills'])}个")
        for i, skill in enumerate(analysis['low_usage_skills'][:3], 1):
            print(f"  {i}. {skill['name']}: {skill['usage_count']}次 ({', '.join(skill['reasons'][:2])})")
    print()


def example_generate_report():
    """示例：生成报告"""
    print("示例3: 生成报告")
    print("-" * 40)
    
    # 生成Markdown报告
    report = generate_markdown_report(days=30)
    
    # 保存报告
    report_path = "/tmp/skill_usage_report.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"✓ 报告已生成: {report_path}")
    
    # 显示报告预览
    lines = report.split('\n')
    print("\n报告预览 (前10行):")
    for line in lines[:10]:
        print(f"  {line}")
    print()


def example_low_usage_detection():
    """示例：低使用率检测"""
    print("示例4: 低使用率检测")
    print("-" * 40)
    
    from scripts import find_low_usage_skills
    
    # 查找低使用率技能
    low_usage_skills = find_low_usage_skills(days=30, threshold=3)
    
    if low_usage_skills:
        print(f"发现 {len(low_usage_skills)} 个低使用率技能:")
        print()
        print("技能名称".ljust(30) + "使用次数".ljust(10) + "最后使用".ljust(15) + "原因")
        print("-" * 80)
        
        for skill in low_usage_skills[:5]:  # 显示前5个
            name = skill['name'][:28].ljust(30)
            count = str(skill['usage_count']).ljust(10)
            last_used = skill.get('last_used', '从未')[:13].ljust(15)
            reasons = ', '.join(skill['reasons'][:2])
            
            print(f"{name}{count}{last_used}{reasons}")
    else:
        print("未发现低使用率技能")
    print()


def example_skill_health():
    """示例：技能健康报告"""
    print("示例5: 技能健康报告")
    print("-" * 40)
    
    from scripts import get_skill_health
    
    # 选择一个技能进行检查（这里用 memory-system 作为示例）
    skill_name = "memory-system"
    health_report = get_skill_health(skill_name)
    
    if 'error' in health_report:
        print(f"错误: {health_report['error']}")
        return
    
    print(f"技能: {health_report['skill_name']}")
    print(f"健康分数: {health_report['health_score']} ({health_report['health_status']})")
    print(f"使用次数: {health_report['basic_stats'].get('usage_count', 0)}")
    print(f"成功率: {health_report['basic_stats'].get('success_rate', 'N/A')}")
    
    if health_report['improvement_suggestions']:
        print("\n改进建议:")
        for suggestion in health_report['improvement_suggestions']:
            print(f"  • {suggestion}")
    print()


def main():
    """运行所有示例"""
    print("技能使用监控系统示例")
    print("=" * 60)
    print()
    
    example_record_usage()
    example_analyze_usage()
    example_generate_report()
    example_low_usage_detection()
    example_skill_health()
    
    print("=" * 60)
    print("示例执行完成！")
    print()
    print("接下来可以尝试:")
    print("1. 运行 'python generate_report.py --days 30 --format markdown'")
    print("2. 运行 'python identify_low_usage.py --threshold 3 --days 30'")
    print("3. 在代码中使用 @record_skill_usage 装饰器")


if __name__ == "__main__":
    main()
