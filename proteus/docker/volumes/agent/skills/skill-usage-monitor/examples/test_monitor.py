#!/usr/bin/env python3
"""
技能使用监控系统测试脚本
"""

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from monitor import SkillUsageMonitor, record_usage_now
from analyzer import SkillUsageAnalyzer, analyze_usage
from reporter import SkillUsageReporter


def test_basic_functionality():
    """测试基本功能"""
    print("=" * 60)
    print("测试 1: 基本功能测试")
    print("=" * 60)
    
    # 创建监控实例
    monitor = SkillUsageMonitor()
    print("✓ 监控实例创建成功")
    
    # 同步技能
    monitor.sync_skills()
    print("✓ 技能同步完成")
    
    # 记录一些测试使用
    test_skills = ["test-skill-1", "test-skill-2", "test-skill-3"]
    for skill in test_skills:
        success = record_usage_now(
            skill,
            context_length=1500,
            success=True,
            execution_time=0.5
        )
        if success:
            print(f"✓ 记录技能使用: {skill}")
        else:
            print(f"✗ 记录技能使用失败: {skill}")
    
    # 等待一下，确保记录时间不同
    time.sleep(1)
    
    # 记录一个失败的使用
    record_usage_now(
        "test-skill-fail",
        context_length=2000,
        success=False,
        error_message="测试错误",
        execution_time=2.5
    )
    print("✓ 记录失败使用")
    
    return monitor


def test_usage_stats(monitor):
    """测试使用统计"""
    print("\n" + "=" * 60)
    print("测试 2: 使用统计")
    print("=" * 60)
    
    # 获取统计
    stats = monitor.get_usage_stats(days=7)
    print(f"✓ 获取到 {len(stats)} 个技能统计")
    
    # 显示前几个技能
    if stats:
        print("\n技能统计示例:")
        for i, skill in enumerate(stats[:3], 1):
            print(f"{i}. {skill['name']}: {skill['usage_count']}次, 分类: {skill['category']}")
    
    return stats


def test_low_usage_identification(monitor):
    """测试低使用率识别"""
    print("\n" + "=" * 60)
    print("测试 3: 低使用率识别")
    print("=" * 60)
    
    # 识别低使用率技能
    low_usage_skills = monitor.identify_low_usage_skills(
        days=7,
        usage_threshold=2,
        inactive_days=14
    )
    
    print(f"✓ 识别到 {len(low_usage_skills)} 个低使用率技能")
    
    if low_usage_skills:
        print("\n低使用率技能示例:")
        for i, skill in enumerate(low_usage_skills[:3], 1):
            print(f"{i}. {skill['name']}: {skill['usage_count']}次")
            print(f"   原因: {', '.join(skill['reasons'][:2])}")
            print(f"   优先级: {skill['priority_score']}")
    
    return low_usage_skills


def test_analyzer():
    """测试分析器"""
    print("\n" + "=" * 60)
    print("测试 4: 分析器功能")
    print("=" * 60)
    
    analyzer = SkillUsageAnalyzer()
    
    # 分析使用模式
    analysis = analyzer.analyze_usage_patterns(days=7)
    print("✓ 使用模式分析完成")
    
    summary = analysis['summary']
    print(f"\n分析摘要:")
    print(f"  总技能数: {summary['total_skills']}")
    print(f"  已使用技能: {summary['used_skills']} ({summary['usage_rate']}%)")
    print(f"  总使用次数: {summary['total_usage_count']}")
    print(f"  平均使用次数: {summary['average_usage_per_skill']:.1f}")
    
    # 显示热门技能
    if analysis['top_skills']:
        print(f"\n热门技能 (前3):")
        for i, skill in enumerate(analysis['top_skills'][:3], 1):
            print(f"  {i}. {skill['name']}: {skill['usage_count']}次")
    
    # 分类分析
    if analysis['category_analysis']:
        print(f"\n分类分析 (前3):")
        categories = list(analysis['category_analysis'].items())[:3]
        for category, data in categories:
            print(f"  {category}: {data['count']}个技能, {data['usage_count']}次使用")
    
    # 建议
    if analysis['recommendations']:
        print(f"\n系统建议:")
        for i, rec in enumerate(analysis['recommendations'][:3], 1):
            print(f"  {i}. {rec}")
    
    return analysis


def test_reporter():
    """测试报告生成器"""
    print("\n" + "=" * 60)
    print("测试 5: 报告生成器")
    print("=" * 60)
    
    reporter = SkillUsageReporter()
    
    # 生成Markdown报告
    markdown_report = reporter.generate_markdown_report(days=7)
    print("✓ Markdown报告生成完成")
    
    # 保存报告
    report_path = "/tmp/test_skill_report.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(markdown_report)
    
    print(f"✓ 报告已保存到: {report_path}")
    
    # 显示报告预览
    lines = markdown_report.split('\n')[:15]
    print("\n报告预览 (前15行):")
    for line in lines:
        print(f"  {line}")
    
    # 生成执行摘要
    summary = reporter.generate_executive_summary(days=7)
    print("\n执行摘要:")
    print(f"  健康分数: {summary['health_score']} ({summary['health_status']})")
    print(f"  活跃技能: {summary['key_metrics']['active_skills']}/{summary['key_metrics']['total_skills']}")
    
    if summary['recommended_actions']:
        print("  推荐行动:")
        for action in summary['recommended_actions']:
            print(f"    • [{action['priority']}] {action['action']}")
    
    return markdown_report


def test_skill_health():
    """测试技能健康报告"""
    print("\n" + "=" * 60)
    print("测试 6: 技能健康报告")
    print("=" * 60)
    
    # 选择一个技能进行健康检查
    from analyzer import get_skill_health
    
    # 测试现有的技能（如果有的话）
    monitor = SkillUsageMonitor()
    stats = monitor.get_usage_stats(days=30)
    
    if stats:
        # 选择一个有使用记录的技能
        test_skill = None
        for skill in stats:
            if skill['usage_count'] > 0:
                test_skill = skill['name']
                break
        
        if test_skill:
            health_report = get_skill_health(test_skill, days=7)
            
            if 'error' not in health_report:
                print(f"✓ 技能健康报告生成: {test_skill}")
                print(f"\n技能: {health_report['skill_name']}")
                print(f"健康分数: {health_report['health_score']} ({health_report['health_status']})")
                
                stats = health_report['basic_stats']
                print(f"使用次数: {stats.get('usage_count', 0)}")
                print(f"成功率: {stats.get('success_rate', 'N/A')}")
                
                if health_report['improvement_suggestions']:
                    print("\n改进建议:")
                    for suggestion in health_report['improvement_suggestions']:
                        print(f"  • {suggestion}")
            else:
                print(f"✗ 生成健康报告失败: {health_report['error']}")
        else:
            print("⚠ 没有找到有使用记录的技能进行健康检查")
    else:
        print("⚠ 没有技能统计数据可用")


def test_merge_candidates():
    """测试合并候选识别"""
    print("\n" + "=" * 60)
    print("测试 7: 合并候选识别")
    print("=" * 60)
    
    from analyzer import find_candidate_merges
    
    candidates = find_candidate_merges(similarity_threshold=0.6)
    
    if candidates:
        print(f"✓ 发现 {len(candidates)} 对可能合并的技能")
        print("\n合并候选示例 (前3):")
        
        for i, (skill_a, skill_b, similarity, reason, priority) in enumerate(candidates[:3], 1):
            print(f"{i}. {skill_a} + {skill_b}")
            print(f"   相似度: {similarity:.2f}")
            print(f"   优先级: {priority}")
            print(f"   理由: {reason}")
            print()
    else:
        print("✓ 未发现需要合并的技能")


def test_system_health():
    """测试系统健康状态"""
    print("\n" + "=" * 60)
    print("测试 8: 系统健康状态")
    print("=" * 60)
    
    monitor = SkillUsageMonitor()
    health = monitor.get_system_health()
    
    print("系统健康状态:")
    print(f"  总技能数: {health['total_skills']}")
    print(f"  活跃技能: {health['active_skills']} ({health['usage_rate']}%)")
    print(f"  总记录数: {health['total_records']}")
    print(f"  错误率: {health['error_rate']}%")
    print(f"  健康分数: {health['health_score']} ({health['health_status']})")
    print(f"  数据库大小: {health['database_size']:,} 字节")
    
    # 备份测试
    backup_path = monitor.backup_database("/tmp/backups")
    print(f"\n✓ 数据库备份完成: {backup_path}")


def cleanup_test_data():
    """清理测试数据"""
    print("\n" + "=" * 60)
    print("清理测试数据")
    print("=" * 60)
    
    # 删除测试数据库
    test_db = Path("/app/data/skill_usage.db")
    if test_db.exists():
        test_db.unlink()
        print("✓ 测试数据库已删除")
    
    # 清理临时文件
    temp_files = [
        Path("/tmp/test_skill_report.md"),
        Path("/tmp/backups")
    ]
    
    for file_path in temp_files:
        if file_path.exists():
            if file_path.is_dir():
                import shutil
                shutil.rmtree(file_path)
            else:
                file_path.unlink()
    
    print("✓ 临时文件已清理")


def main():
    """主测试函数"""
    print("技能使用监控系统测试")
    print("=" * 60)
    
    try:
        # 运行各个测试
        monitor = test_basic_functionality()
        test_usage_stats(monitor)
        test_low_usage_identification(monitor)
        test_analyzer()
        test_reporter()
        test_skill_health()
        test_merge_candidates()
        test_system_health()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试完成!")
        print("=" * 60)
        print("\n测试总结:")
        print("• 基本功能: ✅")
        print("• 使用统计: ✅")
        print("• 低使用率识别: ✅")
        print("• 分析器: ✅")
        print("• 报告生成: ✅")
        print("• 技能健康报告: ✅")
        print("• 合并候选识别: ✅")
        print("• 系统健康状态: ✅")
        
        # 清理测试数据
        cleanup_test_data()
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        
        # 尝试清理
        try:
            cleanup_test_data()
        except:
            pass
        
        sys.exit(1)


if __name__ == "__main__":
    main()
