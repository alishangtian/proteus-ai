#!/usr/bin/env python3
"""
技能使用报告生成命令行工具
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
try:
    from .reporter import
except ImportError:
    from reporter import
try:
    from .analyzer import
except ImportError:
    from analyzer import
try:
    from .monitor import
except ImportError:
    from monitor import


def main():
    parser = argparse.ArgumentParser(description='生成技能使用报告')
    
    parser.add_argument('--days', type=int, default=30,
                       help='分析天数 (默认: 30)')
    parser.add_argument('--format', choices=['markdown', 'json', 'csv', 'summary', 'all'],
                       default='markdown',
                       help='输出格式 (默认: markdown)')
    parser.add_argument('--output', type=str,
                       help='输出文件路径 (默认根据格式自动生成)')
    parser.add_argument('--threshold', type=int, default=3,
                       help='低使用率阈值 (默认: 3次)')
    parser.add_argument('--identify-low-usage', action='store_true',
                       help='识别低使用率技能')
    parser.add_argument('--find-merges', action='store_true',
                       help='查找可能合并的技能')
    parser.add_argument('--skill-health', type=str,
                       help='获取指定技能的健康报告')
    parser.add_argument('--sync', action='store_true',
                       help='同步技能数据库')
    parser.add_argument('--backup', action='store_true',
                       help='备份数据库')
    parser.add_argument('--cleanup', action='store_true',
                       help='清理旧记录')
    parser.add_argument('--days-to-keep', type=int, default=365,
                       help='保留天数 (默认: 365)')
    
    args = parser.parse_args()
    
    # 初始化监控系统
    monitor = SkillUsageMonitor()
    analyzer = SkillUsageAnalyzer(monitor)
    reporter = SkillUsageReporter(analyzer)
    
    # 处理各种命令
    if args.sync:
        print("正在同步技能数据库...")
        monitor._sync_skills()
        print("同步完成")
        return
    
    if args.backup:
        print("正在备份数据库...")
        backup_path = monitor.backup_database()
        print(f"备份完成: {backup_path}")
        return
    
    if args.cleanup:
        print(f"正在清理 {args.days_to_keep} 天前的记录...")
        deleted_count = monitor.cleanup_old_records(args.days_to_keep)
        print(f"清理完成，删除了 {deleted_count} 条记录")
        return
    
    if args.skill_health:
        print(f"生成技能健康报告: {args.skill_health}")
        health_report = analyzer.generate_skill_health_report(args.skill_health, args.days)
        
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
        
        # 保存报告
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(health_report, f, indent=2, ensure_ascii=False)
            print(f"\n报告已保存到: {args.output}")
        
        return
    
    if args.identify_low_usage:
        print(f"识别低使用率技能 (阈值: {args.threshold}次, 周期: {args.days}天)...")
        low_usage_skills = monitor.identify_low_usage_skills(args.days, args.threshold)
        
        if not low_usage_skills:
            print("未发现低使用率技能")
            return
        
        print(f"发现 {len(low_usage_skills)} 个低使用率技能:")
        print("")
        print("| 技能名称 | 分类 | 使用次数 | 最后使用 | 天数 | 原因 |")
        print("|----------|------|----------|----------|------|------|")
        
        for skill in low_usage_skills[:20]:  # 显示前20个
            last_used = skill.get('last_used', '从未')
            days_since = skill.get('days_since_last_use', 'N/A')
            reasons = ', '.join(skill['reasons'][:2])
            
            print(f"| {skill['name']} | {skill.get('category', 'N/A')} | "
                  f"{skill['usage_count']} | {last_used} | {days_since} | {reasons} |")
        
        # 保存结果
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(low_usage_skills, f, indent=2, ensure_ascii=False)
            print(f"\n结果已保存到: {args.output}")
        
        return
    
    if args.find_merges:
        print("查找可能合并的技能...")
        candidates = analyzer.identify_candidate_skills_for_merge(0.7)
        
        if not candidates:
            print("未发现可能合并的技能")
            return
        
        print(f"发现 {len(candidates)} 对可能合并的技能:")
        print("")
        
        for i, (skill_a, skill_b, similarity, reason, priority) in enumerate(candidates[:10], 1):
            print(f"{i}. {skill_a} + {skill_b}")
            print(f"   相似度: {similarity:.2f}, 优先级: {priority}")
            print(f"   理由: {reason}")
            print("")
        
        # 保存结果
        if args.output:
            result = [
                {
                    'skill_a': skill_a,
                    'skill_b': skill_b,
                    'similarity': similarity,
                    'reason': reason,
                    'priority': priority
                }
                for skill_a, skill_b, similarity, reason, priority in candidates
            ]
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"结果已保存到: {args.output}")
        
        return
    
    # 生成报告
    print(f"生成技能使用报告 (周期: {args.days}天, 格式: {args.format})...")
    
    if args.format == 'markdown' or args.format == 'all':
        if args.format == 'all' or not args.output:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            md_output = args.output or f"/app/data/skill_report_{timestamp}.md"
        else:
            md_output = args.output
        
        markdown_report = reporter.generate_markdown_report(args.days)
        
        with open(md_output, 'w', encoding='utf-8') as f:
            f.write(markdown_report)
        
        print(f"Markdown报告已生成: {md_output}")
    
    if args.format == 'json' or args.format == 'all':
        if args.format == 'all':
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_output = f"/app/data/skill_report_{timestamp}.json"
        else:
            json_output = args.output or f"/app/data/skill_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        json_path = reporter.generate_json_report(json_output, args.days)
        print(f"JSON报告已生成: {json_path}")
    
    if args.format == 'csv' or args.format == 'all':
        if args.format == 'all':
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_output = f"/app/data/skill_report_{timestamp}.csv"
        else:
            csv_output = args.output or f"/app/data/skill_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        csv_path = reporter.generate_csv_report(csv_output, args.days)
        print(f"CSV报告已生成: {csv_path}")
    
    if args.format == 'summary' or args.format == 'all':
        summary = reporter.generate_executive_summary(args.days)
        
        print("\n📊 执行摘要:")
        print(f"  健康分数: {summary['health_score']} ({summary['health_status']})")
        print(f"  总技能数: {summary['key_metrics']['total_skills']}")
        print(f"  活跃技能: {summary['key_metrics']['active_skills']} ({summary['key_metrics']['usage_rate']}%)")
        print(f"  总使用次数: {summary['key_metrics']['total_usage']}")
        print("")
        
        print("🏆 热门技能:")
        for i, skill in enumerate(summary['top_performers'][:5], 1):
            print(f"  {i}. {skill['name']}: {skill['usage_count']}次 ({skill['success_rate']}% 成功率)")
        
        if summary['concerns']:
            print("\n⚠️  关注点:")
            for concern in summary['concerns']:
                if concern['type'] == 'low_usage':
                    print(f"  • 低使用率技能: {concern['count']}个 ({concern['percentage']}%)")
        
        if summary['recommended_actions']:
            print("\n💡 推荐行动:")
            for action in summary['recommended_actions']:
                print(f"  • [{action['priority'].upper()}] {action['action']} (工作量: {action['effort']})")
        
        print(f"\n🔄 下次审查: {summary['next_review_date']}")
        
        if args.output and args.format == 'summary':
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            print(f"\n摘要已保存到: {args.output}")


if __name__ == "__main__":
    main()
