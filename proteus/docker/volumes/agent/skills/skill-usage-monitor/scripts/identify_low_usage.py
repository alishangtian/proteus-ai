#!/usr/bin/env python3
"""
识别低使用率技能工具
"""

import argparse
import json
from datetime import datetime
try:
    from .monitor import
except ImportError:
    from monitor import
try:
    from .analyzer import
except ImportError:
    from analyzer import


def main():
    parser = argparse.ArgumentParser(description='识别低使用率技能')
    
    parser.add_argument('--days', type=int, default=30,
                       help='分析天数 (默认: 30)')
    parser.add_argument('--threshold', type=int, default=3,
                       help='使用次数阈值 (默认: 3)')
    parser.add_argument('--inactive-days', type=int, default=60,
                       help='不活跃天数阈值 (默认: 60)')
    parser.add_argument('--output', type=str,
                       help='输出文件路径 (默认: /app/data/low_usage_skills.json)')
    parser.add_argument('--format', choices=['json', 'markdown', 'csv', 'table'],
                       default='table',
                       help='输出格式 (默认: table)')
    parser.add_argument('--include-recommendations', action='store_true',
                       help='包含改进建议')
    parser.add_argument('--export-all', action='store_true',
                       help='导出所有技能统计')
    parser.add_argument('--min-usage', type=int, default=0,
                       help='最小使用次数筛选')
    parser.add_argument('--max-usage', type=int, default=9999,
                       help='最大使用次数筛选')
    parser.add_argument('--category', type=str,
                       help='按分类筛选')
    
    args = parser.parse_args()
    
    # 初始化监控系统
    monitor = SkillUsageMonitor()
    analyzer = SkillUsageAnalyzer(monitor)
    
    print(f"分析技能使用情况 (周期: {args.days}天)...")
    print(f"低使用率阈值: ≤{args.threshold}次")
    print(f"不活跃阈值: ≥{args.inactive_days}天")
    print("")
    
    # 获取低使用率技能
    low_usage_skills = monitor.identify_low_usage_skills(
        days=args.days,
        usage_threshold=args.threshold,
        inactive_days=args.inactive_days
    )
    
    # 获取所有技能统计用于筛选
    all_stats = monitor.get_usage_stats(args.days)
    
    # 应用筛选
    filtered_skills = []
    for skill in all_stats:
        # 使用次数筛选
        if skill['usage_count'] < args.min_usage or skill['usage_count'] > args.max_usage:
            continue
        
        # 分类筛选
        if args.category and skill.get('category') != args.category:
            continue
        
        # 检查是否为低使用率
        is_low_usage = any(
            low_skill['name'] == skill['name'] 
            for low_skill in low_usage_skills
        )
        
        skill_data = {
            'name': skill['name'],
            'category': skill.get('category', 'uncategorized'),
            'usage_count': skill['usage_count'],
            'last_used': skill.get('last_used'),
            'days_since_last_use': skill.get('days_since_last_use'),
            'success_rate': skill.get('success_rate'),
            'is_low_usage': is_low_usage,
            'avg_context_length': skill.get('avg_context_length'),
            'avg_execution_time': skill.get('avg_execution_time')
        }
        
        filtered_skills.append(skill_data)
    
    # 排序
    filtered_skills.sort(key=lambda x: x['usage_count'])
    
    if args.export_all:
        skills_to_export = filtered_skills
        print(f"导出所有技能统计: {len(skills_to_export)} 个技能")
    else:
        skills_to_export = [s for s in filtered_skills if s['is_low_usage']]
        print(f"发现低使用率技能: {len(skills_to_export)} 个")
        print("")
    
    # 输出结果
    if args.format == 'table':
        _print_table(skills_to_export, args.export_all)
    elif args.format == 'markdown':
        _print_markdown(skills_to_export, args.export_all, args.days)
    elif args.format == 'csv':
        _print_csv(skills_to_export, args.output)
    
    # 保存到文件
    if args.output:
        output_data = {
            'generated_at': datetime.now().isoformat(),
            'analysis_period_days': args.days,
            'threshold': args.threshold,
            'inactive_days': args.inactive_days,
            'skills': skills_to_export
        }
        
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n结果已保存到: {args.output}")
    
    # 生成建议
    if args.include_recommendations and skills_to_export:
        print("\n" + "="*60)
        print("💡 低使用率技能处理建议")
        print("="*60)
        
        categories = {}
        for skill in skills_to_export:
            category = skill['category']
            if category not in categories:
                categories[category] = []
            categories[category].append(skill)
        
        for category, skills in categories.items():
            print(f"\n📁 {category} 分类 ({len(skills)} 个技能):")
            
            # 按使用次数分组
            never_used = [s for s in skills if s['usage_count'] == 0]
            rarely_used = [s for s in skills if 1 <= s['usage_count'] <= 3]
            inactive = [s for s in skills if s['days_since_last_use'] and s['days_since_last_use'] >= 60]
            
            if never_used:
                print(f"  • 从未使用: {len(never_used)} 个")
                print(f"     建议: 检查文档、依赖、或考虑删除")
                if len(never_used) <= 5:
                    for skill in never_used[:3]:
                        print(f"       - {skill['name']}")
                    if len(never_used) > 3:
                        print(f"       ... 还有 {len(never_used)-3} 个")
            
            if rarely_used:
                print(f"  • 极少使用(≤3次): {len(rarely_used)} 个")
                print(f"     建议: 优化功能、增加示例、考虑合并")
            
            if inactive:
                print(f"  • 长期不活跃(≥60天): {len(inactive)} 个")
                print(f"     建议: 评估是否仍然需要、更新或归档")
        
        print("\n🛠️  处理优先级:")
        print("  1. 从未使用且功能重复的技能 → 删除")
        print("  2. 长期不活跃且功能过时的技能 → 归档")
        print("  3. 极少使用但有价值的技能 → 优化推广")
        print("  4. 分类不平衡的技能 → 重组分类")


def _print_table(skills, show_all=False):
    """以表格形式输出"""
    if show_all:
        print("所有技能使用统计:")
        print("")
        print("| 技能名称 | 分类 | 使用次数 | 最后使用 | 天数 | 成功率 | 状态 |")
        print("|----------|------|----------|----------|------|--------|------|")
        
        for skill in skills:
            last_used = skill.get('last_used', '从未')
            days_since = skill.get('days_since_last_use', 'N/A')
            success_rate = skill.get('success_rate', 'N/A')
            
            if isinstance(success_rate, (int, float)):
                success_rate = f"{success_rate:.1f}%"
            
            status = "⚠️ 低使用" if skill['is_low_usage'] else "✅ 正常"
            
            print(f"| {skill['name']} | {skill['category']} | {skill['usage_count']} | "
                  f"{last_used} | {days_since} | {success_rate} | {status} |")
    else:
        print("低使用率技能列表:")
        print("")
        print("| 技能名称 | 分类 | 使用次数 | 最后使用 | 天数 | 成功率 | 原因 |")
        print("|----------|------|----------|----------|------|--------|------|")
        
        for skill in skills:
            last_used = skill.get('last_used', '从未')
            days_since = skill.get('days_since_last_use', 'N/A')
            success_rate = skill.get('success_rate', 'N/A')
            
            if isinstance(success_rate, (int, float)):
                success_rate = f"{success_rate:.1f}%"
            
            # 判断原因
            reasons = []
            if skill['usage_count'] == 0:
                reasons.append("从未使用")
            elif skill['usage_count'] <= 3:
                reasons.append("极少使用")
            
            if days_since and days_since >= 60:
                reasons.append(f"不活跃({days_since}天)")
            
            if success_rate != 'N/A' and isinstance(skill.get('success_rate'), (int, float)):
                if skill['success_rate'] < 70:
                    reasons.append(f"低成功率({skill['success_rate']}%)")
            
            reason_text = ', '.join(reasons) if reasons else "N/A"
            
            print(f"| {skill['name']} | {skill['category']} | {skill['usage_count']} | "
                  f"{last_used} | {days_since} | {success_rate} | {reason_text} |")


def _print_markdown(skills, show_all, days):
    """以Markdown形式输出"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if show_all:
        title = f"# 技能使用统计报告"
    else:
        title = f"# 低使用率技能报告"
    
    print(title)
    print(f"**生成时间**: {timestamp}")
    print(f"**分析周期**: 最近 {days} 天")
    print("")
    
    if show_all:
        print("## 所有技能统计")
    else:
        print("## 低使用率技能列表")
    
    print("")
    print("| 技能名称 | 分类 | 使用次数 | 最后使用 | 天数 | 成功率 | 状态/原因 |")
    print("|----------|------|----------|----------|------|--------|------------|")
    
    for skill in skills:
        last_used = skill.get('last_used', '从未')
        days_since = skill.get('days_since_last_use', 'N/A')
        success_rate = skill.get('success_rate', 'N/A')
        
        if isinstance(success_rate, (int, float)):
            success_rate = f"{success_rate:.1f}%"
        
        if show_all:
            status = "⚠️" if skill['is_low_usage'] else "✅"
            print(f"| {skill['name']} | {skill['category']} | {skill['usage_count']} | "
                  f"{last_used} | {days_since} | {success_rate} | {status} |")
        else:
            # 判断原因
            reasons = []
            if skill['usage_count'] == 0:
                reasons.append("从未使用")
            elif skill['usage_count'] <= 3:
                reasons.append("极少使用")
            
            if days_since and days_since >= 60:
                reasons.append(f"不活跃")
            
            reason_text = ', '.join(reasons) if reasons else "N/A"
            print(f"| {skill['name']} | {skill['category']} | {skill['usage_count']} | "
                  f"{last_used} | {days_since} | {success_rate} | {reason_text} |")


def _print_csv(skills, output_path):
    """以CSV形式输出"""
    import csv
    
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"/app/data/low_usage_skills_{timestamp}.csv"
    
    fieldnames = ['name', 'category', 'usage_count', 'last_used', 
                  'days_since_last_use', 'success_rate', 'avg_context_length',
                  'avg_execution_time', 'is_low_usage']
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for skill in skills:
            row = {
                'name': skill['name'],
                'category': skill['category'],
                'usage_count': skill['usage_count'],
                'last_used': skill.get('last_used', ''),
                'days_since_last_use': skill.get('days_since_last_use', ''),
                'success_rate': skill.get('success_rate', ''),
                'avg_context_length': skill.get('avg_context_length', ''),
                'avg_execution_time': skill.get('avg_execution_time', ''),
                'is_low_usage': skill['is_low_usage']
            }
            writer.writerow(row)
    
    print(f"CSV文件已生成: {output_path}")


if __name__ == "__main__":
    main()
