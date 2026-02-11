"""
技能使用报告生成器 - 生成各种格式的报告
"""

import json
import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List
try:
    from .analyzer import SkillUsageAnalyzer
except ImportError:
    from analyzer import SkillUsageAnalyzer
try:
    from .monitor import SkillUsageMonitor
except ImportError:
    from monitor import SkillUsageMonitor


class SkillUsageReporter:
    """技能使用报告生成器"""
    
    def __init__(self, analyzer: SkillUsageAnalyzer = None):
        self.analyzer = analyzer or SkillUsageAnalyzer()
        self.monitor = self.analyzer.monitor
    
    def generate_markdown_report(self, days: int = 30) -> str:
        """
        生成Markdown格式的报告
        
        Returns:
            Markdown报告内容
        """
        analysis = self.analyzer.analyze_usage_patterns(days)
        
        report_lines = []
        
        # 标题
        report_lines.append(f"# 技能使用监控报告")
        report_lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"**分析周期**: 最近 {days} 天")
        report_lines.append("")
        
        # 执行摘要
        summary = analysis['summary']
        report_lines.append("## 📊 执行摘要")
        report_lines.append("")
        report_lines.append(f"- **总技能数**: {summary['total_skills']}")
        report_lines.append(f"- **已使用技能**: {summary['used_skills']} ({summary['usage_rate']}%)")
        report_lines.append(f"- **未使用技能**: {summary['unused_skills']}")
        report_lines.append(f"- **总使用次数**: {summary['total_usage_count']}")
        report_lines.append(f"- **平均使用次数**: {summary['average_usage_per_skill']}")
        report_lines.append("")
        
        # 热门技能
        if analysis['top_skills']:
            report_lines.append("## 🏆 热门技能 (前10)")
            report_lines.append("")
            report_lines.append("| 排名 | 技能名称 | 使用次数 | 最后使用 | 成功率 |")
            report_lines.append("|------|----------|----------|----------|--------|")
            
            for i, skill in enumerate(analysis['top_skills'][:10], 1):
                last_used = skill.get('last_used', '从未')
                if last_used != '从未':
                    last_used_dt = datetime.fromisoformat(last_used.replace('Z', '+00:00'))
                    last_used = last_used_dt.strftime('%Y-%m-%d')
                
                success_rate = skill.get('success_rate', 'N/A')
                if isinstance(success_rate, (int, float)):
                    success_rate = f"{success_rate}%"
                
                report_lines.append(
                    f"| {i} | {skill['name']} | {skill['usage_count']} | {last_used} | {success_rate} |"
                )
            report_lines.append("")
        
        # 低使用率技能
        if analysis['low_usage_skills']:
            report_lines.append("## ⚠️ 低使用率技能")
            report_lines.append("")
            report_lines.append(f"发现 {len(analysis['low_usage_skills'])} 个低使用率技能")
            report_lines.append("")
            
            report_lines.append("| 技能名称 | 分类 | 使用次数 | 最后使用 | 天数 | 原因 |")
            report_lines.append("|----------|------|----------|----------|------|------|")
            
            for skill in analysis['low_usage_skills'][:20]:  # 显示前20个
                last_used = skill.get('last_used', '从未')
                if last_used != '从未':
                    last_used_dt = datetime.fromisoformat(last_used.replace('Z', '+00:00'))
                    last_used = last_used_dt.strftime('%Y-%m-%d')
                    days_since = skill.get('days_since_last_use', 'N/A')
                else:
                    days_since = 'N/A'
                
                reasons = ', '.join(skill['reasons'][:2])  # 显示前两个原因
                if len(skill['reasons']) > 2:
                    reasons += f" (+{len(skill['reasons'])-2}更多)"
                
                report_lines.append(
                    f"| {skill['name']} | {skill.get('category', 'N/A')} | "
                    f"{skill['usage_count']} | {last_used} | {days_since} | {reasons} |"
                )
            report_lines.append("")
        
        # 分类分析
        if analysis['category_analysis']:
            report_lines.append("## 📈 分类分析")
            report_lines.append("")
            report_lines.append("| 分类 | 技能数 | 使用次数 | 平均上下文 | 平均成功率 |")
            report_lines.append("|------|--------|----------|------------|------------|")
            
            for category, stats in analysis['category_analysis'].items():
                avg_context = stats.get('avg_context_length', 0)
                success_rate = stats.get('success_rate', 0)
                
                if isinstance(avg_context, (int, float)):
                    avg_context = f"{avg_context:.0f}"
                if isinstance(success_rate, (int, float)):
                    success_rate = f"{success_rate:.1f}%"
                
                report_lines.append(
                    f"| {category} | {stats['count']} | {stats['usage_count']} | "
                    f"{avg_context} | {success_rate} |"
                )
            report_lines.append("")
        
        # 合并建议
        candidates = self.analyzer.identify_candidate_skills_for_merge(0.7)
        if candidates:
            report_lines.append("## 🔄 合并建议")
            report_lines.append("")
            report_lines.append("以下技能可能可以合并（名称相似且使用率低）：")
            report_lines.append("")
            
            for i, (skill_a, skill_b, similarity, reason, priority) in enumerate(candidates[:10], 1):
                report_lines.append(f"{i}. **{skill_a}** + **{skill_b}**")
                report_lines.append(f"   - 相似度: {similarity:.2f}")
                report_lines.append(f"   - 优先级: {priority}")
                report_lines.append(f"   - 理由: {reason}")
                report_lines.append("")
        
        # 系统建议
        if analysis['recommendations']:
            report_lines.append("## 💡 系统建议")
            report_lines.append("")
            for i, recommendation in enumerate(analysis['recommendations'], 1):
                report_lines.append(f"{i}. {recommendation}")
            report_lines.append("")
        
        # 维护计划
        report_lines.append("## 🛠️ 维护计划")
        report_lines.append("")
        report_lines.append("### 立即行动")
        report_lines.append("- [ ] 审查低使用率技能的前5个")
        report_lines.append("- [ ] 检查高失败率技能")
        report_lines.append("- [ ] 验证热门技能的文档完整性")
        report_lines.append("")
        
        report_lines.append("### 短期计划 (1-4周)")
        report_lines.append("- [ ] 归档长期未使用的技能")
        report_lines.append("- [ ] 优化低成功率技能")
        report_lines.append("- [ ] 更新技能分类系统")
        report_lines.append("")
        
        report_lines.append("### 长期计划 (1-3月)")
        report_lines.append("- [ ] 实施技能质量评分系统")
        report_lines.append("- [ ] 建立技能淘汰机制")
        report_lines.append("- [ ] 优化技能发现和推荐")
        report_lines.append("")
        
        # 脚注
        report_lines.append("---")
        report_lines.append("")
        report_lines.append("*报告由技能使用监控系统自动生成*")
        report_lines.append("*数据库位置: /app/data/skill_usage.db*")
        
        return "\n".join(report_lines)
    
    def generate_json_report(self, 
                           output_path: str = None,
                           days: int = 30) -> str:
        """
        生成JSON格式的报告
        
        Returns:
            输出文件路径
        """
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"/app/data/skill_report_{timestamp}.json"
        
        analysis = self.analyzer.analyze_usage_patterns(days)
        
        # 添加报告元数据
        report = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'analysis_period_days': days,
                'report_version': '1.0',
                'skill_count': analysis['summary']['total_skills']
            },
            'data': analysis
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        return output_path
    
    def generate_csv_report(self, 
                          output_path: str = None,
                          days: int = 30) -> str:
        """
        生成CSV格式的报告
        
        Returns:
            输出文件路径
        """
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"/app/data/skill_report_{timestamp}.csv"
        
        stats = self.monitor.get_usage_stats(days)
        
        if not stats:
            raise ValueError("没有使用数据可用")
        
        # 写入CSV
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            if stats:
                fieldnames = list(stats[0].keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(stats)
        
        return output_path
    
    def generate_executive_summary(self, days: int = 30) -> Dict[str, Any]:
        """
        生成执行摘要
        
        Returns:
            执行摘要数据
        """
        analysis = self.analyzer.analyze_usage_patterns(days)
        
        # 提取关键指标
        summary = analysis['summary']
        low_usage_count = len(analysis['low_usage_skills'])
        top_skills = analysis['top_skills'][:5]
        
        # 计算健康度
        total_skills = summary['total_skills']
        used_skills = summary['used_skills']
        health_score = min(100, int((used_skills / total_skills * 100) * 0.7 + 30)) if total_skills > 0 else 0
        
        # 生成行动项
        actions = []
        if low_usage_count > total_skills * 0.3:
            actions.append({
                'priority': 'high',
                'action': f'清理低使用率技能 ({low_usage_count}/{total_skills})',
                'effort': 'medium'
            })
        
        if summary['usage_rate'] < 50:
            actions.append({
                'priority': 'medium',
                'action': f'提高技能使用率 (当前: {summary["usage_rate"]}%)',
                'effort': 'high'
            })
        
        # 检查分类不平衡
        category_stats = analysis['category_analysis']
        if len(category_stats) >= 3:
            category_counts = [stat['count'] for stat in category_stats.values()]
            imbalance = max(category_counts) / min(category_counts) if min(category_counts) > 0 else 0
            if imbalance > 5:
                actions.append({
                    'priority': 'low',
                    'action': '优化技能分类平衡',
                    'effort': 'medium'
                })
        
        return {
            'health_score': health_score,
            'health_status': self._get_health_status(health_score),
            'key_metrics': {
                'total_skills': total_skills,
                'active_skills': used_skills,
                'inactive_skills': total_skills - used_skills,
                'usage_rate': summary['usage_rate'],
                'total_usage': summary['total_usage_count'],
                'avg_usage': summary['average_usage_per_skill']
            },
            'top_performers': [
                {
                    'name': skill['name'],
                    'usage_count': skill['usage_count'],
                    'success_rate': skill.get('success_rate', 0)
                }
                for skill in top_skills
            ],
            'concerns': [
                {
                    'type': 'low_usage',
                    'count': low_usage_count,
                    'percentage': round(low_usage_count / total_skills * 100, 1) if total_skills > 0 else 0
                }
            ],
            'recommended_actions': actions,
            'next_review_date': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        }
    
    def _get_health_status(self, score: float) -> str:
        """获取健康状态"""
        if score >= 80:
            return "健康"
        elif score >= 60:
            return "良好"
        elif score >= 40:
            return "一般"
        elif score >= 20:
            return "需关注"
        else:
            return "危险"
    
    def generate_dashboard_data(self, days: int = 30) -> Dict[str, Any]:
        """
        生成仪表板数据
        
        Returns:
            仪表板数据
        """
        analysis = self.analyzer.analyze_usage_patterns(days)
        trends = self.monitor.get_usage_trends(days, interval='week')
        
        # 处理趋势数据用于图表
        chart_data = {
            'weekly_trends': trends.get('overall_trends', []),
            'category_distribution': [
                {'name': category, 'value': stats['count']}
                for category, stats in analysis['category_analysis'].items()
            ],
            'usage_distribution': self._calculate_usage_distribution(analysis['top_skills'])
        }
        
        return {
            'summary': analysis['summary'],
            'charts': chart_data,
            'top_skills': analysis['top_skills'][:10],
            'low_usage_skills': analysis['low_usage_skills'][:10],
            'updated_at': datetime.now().isoformat()
        }
    
    def _calculate_usage_distribution(self, skills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """计算使用分布"""
        if not skills:
            return []
        
        total_usage = sum(s['usage_count'] for s in skills)
        if total_usage == 0:
            return []
        
        distribution = []
        for skill in skills[:10]:  # 前10个技能
            percentage = (skill['usage_count'] / total_usage * 100) if total_usage > 0 else 0
            distribution.append({
                'name': skill['name'],
                'value': skill['usage_count'],
                'percentage': round(percentage, 1)
            })
        
        return distribution


# 便捷函数
def generate_markdown_report(days: int = 30) -> str:
    """生成Markdown报告"""
    reporter = SkillUsageReporter()
    return reporter.generate_markdown_report(days)

def generate_json_report(output_path: str = None, days: int = 30) -> str:
    """生成JSON报告"""
    reporter = SkillUsageReporter()
    return reporter.generate_json_report(output_path, days)

def generate_executive_summary(days: int = 30) -> Dict[str, Any]:
    """生成执行摘要"""
    reporter = SkillUsageReporter()
    return reporter.generate_executive_summary(days)
