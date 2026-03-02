"""
技能使用数据分析器 - 分析使用模式、识别低使用率技能、生成建议
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
import difflib
try:
    from .monitor import SkillUsageMonitor
except ImportError:
    from monitor import SkillUsageMonitor

class SkillUsageAnalyzer:
    """技能使用数据分析器"""
    
    def __init__(self, monitor: SkillUsageMonitor = None):
        self.monitor = monitor or SkillUsageMonitor()
    
    def analyze_usage_patterns(self, days: int = 30) -> Dict[str, Any]:
        """
        分析技能使用模式
        
        Args:
            days: 分析天数
        
        Returns:
            分析结果，包括摘要、热门技能、低使用率技能等
        """
        stats = self.monitor.get_usage_stats(days)
        
        # 计算摘要
        total_skills = len(stats)
        used_skills = len([s for s in stats if s['usage_count'] > 0])
        unused_skills = total_skills - used_skills
        total_usage_count = sum(s['usage_count'] for s in stats)
        average_usage_per_skill = total_usage_count / total_skills if total_skills > 0 else 0
        
        # 获取热门技能（按使用次数排序）
        top_skills = sorted(
            [s for s in stats if s['usage_count'] > 0],
            key=lambda x: x['usage_count'],
            reverse=True
        )
        
        # 识别低使用率技能
        low_usage_skills = self.monitor.identify_low_usage_skills(days)
        
        # 分类分析
        category_analysis = self._analyze_categories(stats)
        
        # 生成建议
        recommendations = self._generate_recommendations(
            stats, top_skills, low_usage_skills, category_analysis
        )
        
        return {
            'summary': {
                'total_skills': total_skills,
                'used_skills': used_skills,
                'unused_skills': unused_skills,
                'usage_rate': round((used_skills / total_skills * 100) if total_skills > 0 else 0, 1),
                'total_usage_count': total_usage_count,
                'average_usage_per_skill': round(average_usage_per_skill, 1),
                'analysis_period_days': days
            },
            'top_skills': top_skills,
            'low_usage_skills': low_usage_skills,
            'category_analysis': category_analysis,
            'recommendations': recommendations,
            'generated_at': datetime.now().isoformat()
        }
    
    def _analyze_categories(self, stats: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """分析技能分类"""
        categories = {}
        
        for skill in stats:
            category = skill['category']
            if category not in categories:
                categories[category] = {
                    'count': 0,
                    'usage_count': 0,
                    'success_rate_sum': 0,
                    'context_length_sum': 0,
                    'skills': []
                }
            
            cat_data = categories[category]
            cat_data['count'] += 1
            cat_data['usage_count'] += skill['usage_count']
            cat_data['skills'].append(skill['name'])
            
            if skill['success_rate']:
                cat_data['success_rate_sum'] += skill['success_rate']
            
            if skill['avg_context_length']:
                cat_data['context_length_sum'] += skill['avg_context_length']
        
        # 计算平均值
        for category, data in categories.items():
            count = data['count']
            if count > 0:
                data['success_rate'] = round(data['success_rate_sum'] / count, 1) if data['success_rate_sum'] > 0 else 0
                data['avg_context_length'] = round(data['context_length_sum'] / count) if data['context_length_sum'] > 0 else 0
            else:
                data['success_rate'] = 0
                data['avg_context_length'] = 0
            
            # 清理临时数据
            del data['success_rate_sum']
            del data['context_length_sum']
        
        return categories
    
    def _generate_recommendations(self, stats: List[Dict[str, Any]], 
                                top_skills: List[Dict[str, Any]],
                                low_usage_skills: List[Dict[str, Any]],
                                category_analysis: Dict[str, Dict[str, Any]]) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        total_skills = len(stats)
        used_skills = len([s for s in stats if s['usage_count'] > 0])
        usage_rate = (used_skills / total_skills * 100) if total_skills > 0 else 0
        
        # 使用率建议
        if usage_rate < 30:
            recommendations.append(f"技能使用率较低（{usage_rate:.1f}%）。建议：推广常用技能、优化技能发现机制")
        elif usage_rate < 50:
            recommendations.append(f"技能使用率一般（{usage_rate:.1f}%）。建议：加强技能文档、提供使用示例")
        
        # 低使用率技能建议
        if low_usage_skills:
            low_count = len(low_usage_skills)
            percentage = (low_count / total_skills * 100) if total_skills > 0 else 0
            
            if percentage > 40:
                recommendations.append(f"低使用率技能过多（{low_count}/{total_skills}，{percentage:.1f}%）。建议：审查并可能删除/合并冗余技能")
            elif percentage > 20:
                recommendations.append(f"发现 {low_count} 个低使用率技能。建议：评估这些技能的价值，考虑优化或归档")
            
            # 检查从未使用的技能
            never_used = [s for s in low_usage_skills if s['usage_count'] == 0]
            if never_used:
                recommendations.append(f"发现 {len(never_used)} 个从未使用的技能。建议：检查文档、依赖、或考虑删除")
        
        # 分类平衡建议
        if len(category_analysis) >= 3:
            category_counts = [data['count'] for data in category_analysis.values()]
            max_count = max(category_counts)
            min_count = min(category_counts) if min(category_counts) > 0 else 1
            
            imbalance = max_count / min_count
            if imbalance > 5:
                max_category = [cat for cat, data in category_analysis.items() 
                              if data['count'] == max_count][0]
                min_category = [cat for cat, data in category_analysis.items() 
                              if data['count'] == min_count][0]
                
                recommendations.append(f"分类不平衡：{max_category}({max_count}) vs {min_category}({min_count})。建议：优化技能分类或开发新技能填补空缺")
        
        # 成功率建议
        low_success_skills = [s for s in stats if s['success_rate'] and s['success_rate'] < 60]
        if low_success_skills:
            recommendations.append(f"发现 {len(low_success_skills)} 个低成功率技能（<60%）。建议：检查错误原因、优化实现")
        
        # 热门技能建议
        if len(top_skills) >= 3:
            top_usage = top_skills[0]['usage_count']
            third_usage = top_skills[2]['usage_count'] if len(top_skills) > 2 else 0
            
            if top_usage > third_usage * 3:
                recommendations.append(f"技能使用集中：最热门技能使用次数是第三名的{top_usage/third_usage:.1f}倍。建议：分散功能依赖、推广其他技能")
        
        # 如果建议太少，添加通用建议
        if len(recommendations) < 3:
            recommendations.extend([
                "定期审查技能使用报告，识别优化机会",
                "建立技能质量评分系统，基于使用数据评估技能价值",
                "优化技能文档和示例，提高技能可发现性"
            ])
        
        return recommendations[:10]  # 最多返回10个建议
    
    def identify_candidate_skills_for_merge(self, similarity_threshold: float = 0.7) -> List[Tuple[str, str, float, str, str]]:
        """
        识别可能合并的技能对
        
        Args:
            similarity_threshold: 相似度阈值（0-1）
        
        Returns:
            技能对列表：(技能A, 技能B, 相似度, 合并理由, 优先级)
        """
        stats = self.monitor.get_usage_stats(90)  # 最近90天
        
        # 只考虑低使用率或未使用的技能
        low_usage_names = {skill['name'] for skill in stats 
                          if skill['usage_count'] <= 3 or 
                          (skill['days_since_last_use'] and skill['days_since_last_use'] >= 60)}
        
        if not low_usage_names:
            return []
        
        # 将技能名称转换为列表以便计算相似度
        skill_names = list(low_usage_names)
        
        candidates = []
        
        # 比较每对技能
        for i in range(len(skill_names)):
            for j in range(i + 1, len(skill_names)):
                skill_a = skill_names[i]
                skill_b = skill_names[j]
                
                # 计算名称相似度
                similarity = difflib.SequenceMatcher(None, skill_a, skill_b).ratio()
                
                # 检查分类是否相同
                cat_a = next((s['category'] for s in stats if s['name'] == skill_a), 'uncategorized')
                cat_b = next((s['category'] for s in stats if s['name'] == skill_b), 'uncategorized')
                same_category = cat_a == cat_b
                
                # 检查使用模式是否相似（都很少用）
                stats_a = next((s for s in stats if s['name'] == skill_a), None)
                stats_b = next((s for s in stats if s['name'] == skill_b), None)
                
                if not stats_a or not stats_b:
                    continue
                
                # 计算综合相似度
                final_similarity = similarity
                if same_category:
                    final_similarity += 0.1
                
                if final_similarity >= similarity_threshold:
                    # 生成合并理由
                    reasons = []
                    if similarity > 0.8:
                        reasons.append("名称高度相似")
                    elif similarity > 0.6:
                        reasons.append("名称相似")
                    
                    if same_category:
                        reasons.append("相同分类")
                    
                    if stats_a['usage_count'] <= 3 and stats_b['usage_count'] <= 3:
                        reasons.append("都很少使用")
                    
                    if stats_a['days_since_last_use'] and stats_b['days_since_last_use']:
                        if stats_a['days_since_last_use'] >= 60 and stats_b['days_since_last_use'] >= 60:
                            reasons.append("都长期不活跃")
                    
                    reason_text = ", ".join(reasons)
                    
                    # 计算优先级
                    priority = self._calculate_merge_priority(skill_a, skill_b, stats_a, stats_b, final_similarity)
                    
                    candidates.append((skill_a, skill_b, final_similarity, reason_text, priority))
        
        # 按优先级排序
        candidates.sort(key=lambda x: x[4], reverse=True)
        
        return candidates[:20]  # 最多返回20个候选
    
    def _calculate_merge_priority(self, skill_a: str, skill_b: str, 
                                stats_a: Dict[str, Any], stats_b: Dict[str, Any], 
                                similarity: float) -> str:
        """计算合并优先级"""
        # 基础优先级基于相似度
        priority_score = similarity * 100
        
        # 如果都从未使用，优先级更高
        if stats_a['usage_count'] == 0 and stats_b['usage_count'] == 0:
            priority_score += 30
        
        # 如果都长期不活跃，优先级更高
        if (stats_a['days_since_last_use'] and stats_a['days_since_last_use'] >= 90 and
            stats_b['days_since_last_use'] and stats_b['days_since_last_use'] >= 90):
            priority_score += 20
        
        # 如果成功率低，优先级更高
        if (stats_a['success_rate'] and stats_a['success_rate'] < 50 and
            stats_b['success_rate'] and stats_b['success_rate'] < 50):
            priority_score += 15
        
        # 转换为优先级标签
        if priority_score >= 110:
            return "high"
        elif priority_score >= 90:
            return "medium"
        else:
            return "low"
    
    def generate_skill_health_report(self, skill_name: str, days: int = 30) -> Dict[str, Any]:
        """
        生成单个技能的健康报告
        
        Args:
            skill_name: 技能名称
            days: 分析天数
        
        Returns:
            技能健康报告
        """
        stats = self.monitor.get_usage_stats(days)
        
        # 查找技能
        skill_data = next((s for s in stats if s['name'] == skill_name), None)
        
        if not skill_data:
            return {
                'error': f"未找到技能: {skill_name}",
                'skill_name': skill_name
            }
        
        # 计算健康分数（0-100）
        health_score = 0
        
        # 使用次数贡献（最多30分）
        usage_count = skill_data['usage_count']
        if usage_count >= 10:
            health_score += 30
        elif usage_count >= 5:
            health_score += 20
        elif usage_count >= 1:
            health_score += 10
        
        # 成功率贡献（最多30分）
        success_rate = skill_data['success_rate']
        if success_rate:
            if success_rate >= 90:
                health_score += 30
            elif success_rate >= 80:
                health_score += 20
            elif success_rate >= 70:
                health_score += 15
            elif success_rate >= 60:
                health_score += 10
        
        # 活跃度贡献（最多20分）
        days_since = skill_data['days_since_last_use']
        if days_since is not None:
            if days_since <= 7:
                health_score += 20
            elif days_since <= 30:
                health_score += 15
            elif days_since <= 90:
                health_score += 10
            elif days_since <= 180:
                health_score += 5
        
        # 上下文长度贡献（最多10分）- 适中的上下文长度更好
        context_length = skill_data['avg_context_length']
        if context_length:
            if 1000 <= context_length <= 3000:
                health_score += 10  # 适中的上下文长度
            elif 500 <= context_length <= 5000:
                health_score += 5  # 可接受的范围
            elif context_length > 10000:
                health_score -= 5  # 上下文太长可能有性能问题
        
        # 执行时间贡献（最多10分）
        exec_time = skill_data['avg_execution_time']
        if exec_time:
            if exec_time <= 1.0:
                health_score += 10  # 快速执行
            elif exec_time <= 5.0:
                health_score += 5  # 可接受的执行时间
            elif exec_time > 30.0:
                health_score -= 5  # 执行时间过长
        
        # 确保分数在0-100范围内
        health_score = max(0, min(100, health_score))
        
        # 确定健康状态
        if health_score >= 80:
            health_status = "健康"
        elif health_score >= 60:
            health_status = "良好"
        elif health_score >= 40:
            health_status = "一般"
        elif health_score >= 20:
            health_status = "需关注"
        else:
            health_status = "危险"
        
        # 生成改进建议
        improvement_suggestions = self._generate_skill_improvement_suggestions(skill_data)
        
        return {
            'skill_name': skill_name,
            'basic_stats': skill_data,
            'health_score': health_score,
            'health_status': health_status,
            'improvement_suggestions': improvement_suggestions,
            'analysis_period_days': days,
            'generated_at': datetime.now().isoformat()
        }
    
    def _generate_skill_improvement_suggestions(self, skill_data: Dict[str, Any]) -> List[str]:
        """生成技能改进建议"""
        suggestions = []
        
        usage_count = skill_data['usage_count']
        success_rate = skill_data['success_rate']
        days_since = skill_data['days_since_last_use']
        context_length = skill_data['avg_context_length']
        
        # 使用次数相关建议
        if usage_count == 0:
            suggestions.append("从未使用过。考虑：1) 完善文档和示例 2) 检查依赖是否完整 3) 推广或与其他技能整合")
        elif usage_count <= 3:
            suggestions.append("使用次数极少。考虑：1) 优化功能使其更实用 2) 添加更多使用示例 3) 改进技能描述")
        
        # 成功率相关建议
        if success_rate and success_rate < 70:
            suggestions.append(f"成功率较低 ({success_rate}%)。建议：1) 检查常见错误原因 2) 优化错误处理 3) 添加输入验证")
        
        # 活跃度相关建议
        if days_since and days_since >= 90:
            suggestions.append(f"长期未使用 ({days_since}天)。考虑：1) 评估是否仍然需要 2) 更新功能以适应当前需求 3) 或考虑归档")
        
        # 上下文长度相关建议
        if context_length and context_length > 5000:
            suggestions.append(f"上下文需求较高 ({context_length} tokens)。建议：1) 优化提示工程 2) 考虑分块处理 3) 简化技能逻辑")
        
        # 通用建议
        if len(suggestions) < 3:
            suggestions.extend([
                "确保技能文档完整且易于理解",
                "提供使用示例和最佳实践",
                "定期测试技能功能以确保稳定性"
            ])
        
        return suggestions[:5]  # 最多返回5个建议

# 便捷函数
def analyze_usage(days: int = 30) -> Dict[str, Any]:
    """分析技能使用情况"""
    analyzer = SkillUsageAnalyzer()
    return analyzer.analyze_usage_patterns(days)

def find_low_usage_skills(days: int = 30, threshold: int = 3) -> List[Dict[str, Any]]:
    """查找低使用率技能"""
    monitor = SkillUsageMonitor()
    return monitor.identify_low_usage_skills(days, threshold)

def find_candidate_merges(similarity_threshold: float = 0.7) -> List[Tuple[str, str, float, str, str]]:
    """查找可能合并的技能"""
    analyzer = SkillUsageAnalyzer()
    return analyzer.identify_candidate_skills_for_merge(similarity_threshold)

def get_skill_health(skill_name: str, days: int = 30) -> Dict[str, Any]:
    """获取技能健康报告"""
    analyzer = SkillUsageAnalyzer()
    return analyzer.generate_skill_health_report(skill_name, days)
