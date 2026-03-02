#!/usr/bin/env python3
"""
深度研究引擎 - 提供核心研究功能
"""

import os
import json
import re
from datetime import datetime

class ResearchEngine:
    """深度研究核心引擎"""
    
    def __init__(self, research_topic, output_dir=None):
        """
        初始化研究引擎
        
        Args:
            research_topic: 研究主题
            output_dir: 输出目录（如为None则自动创建）
        """
        self.research_topic = research_topic
        self.output_dir = output_dir or f"/app/data/research_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.sources = []
        self.findings = []
        self.analysis = {}
        
        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(os.path.join(self.output_dir, "sources"), exist_ok=True)
        os.makedirs(os.path.join(self.output_dir, "analysis"), exist_ok=True)
    
    def add_source(self, source_type, content, url=None, credibility_score=5):
        """
        添加研究来源
        
        Args:
            source_type: 来源类型 (academic, industry_report, news, blog, etc.)
            content: 内容
            url: 来源URL（可选）
            credibility_score: 可信度评分 (1-10)
        """
        source = {
            "id": len(self.sources) + 1,
            "type": source_type,
            "content": content[:1000] + "..." if len(content) > 1000 else content,
            "url": url,
            "credibility_score": credibility_score,
            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.sources.append(source)
        
        # 保存来源文件
        source_file = os.path.join(self.output_dir, "sources", f"source_{source['id']}.json")
        with open(source_file, 'w', encoding='utf-8') as f:
            json.dump(source, f, indent=2, ensure_ascii=False)
        
        return source['id']
    
    def add_finding(self, category, finding, confidence=0.8, supporting_sources=None):
        """
        添加研究发现
        
        Args:
            category: 发现类别
            finding: 发现内容
            confidence: 置信度 (0-1)
            supporting_sources: 支持此发现的来源ID列表
        """
        if supporting_sources is None:
            supporting_sources = []
        
        finding_obj = {
            "id": len(self.findings) + 1,
            "category": category,
            "finding": finding,
            "confidence": confidence,
            "supporting_sources": supporting_sources,
            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.findings.append(finding_obj)
        
        return finding_obj['id']
    
    def analyze_patterns(self):
        """
        分析模式，识别趋势和关联
        """
        # 按类别分组发现
        categories = {}
        for finding in self.findings:
            cat = finding['category']
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(finding)
        
        # 计算置信度统计
        confidence_stats = {}
        for cat, finds in categories.items():
            if finds:
                avg_confidence = sum(f['confidence'] for f in finds) / len(finds)
                confidence_stats[cat] = {
                    'count': len(finds),
                    'avg_confidence': avg_confidence,
                    'high_confidence': len([f for f in finds if f['confidence'] > 0.8]),
                    'low_confidence': len([f for f in finds if f['confidence'] < 0.5])
                }
        
        # 分析来源可信度
        source_stats = {
            'total_sources': len(self.sources),
            'by_type': {},
            'avg_credibility': 0
        }
        
        if self.sources:
            source_stats['avg_credibility'] = sum(s['credibility_score'] for s in self.sources) / len(self.sources)
            
            # 按类型统计
            for source in self.sources:
                stype = source['type']
                if stype not in source_stats['by_type']:
                    source_stats['by_type'][stype] = 0
                source_stats['by_type'][stype] += 1
        
        self.analysis = {
            'categories': categories,
            'confidence_stats': confidence_stats,
            'source_stats': source_stats,
            'total_findings': len(self.findings),
            'analysis_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return self.analysis
    
    def generate_report(self, template_type="standard"):
        """
        生成研究报告
        
        Args:
            template_type: 模板类型 (standard, executive, technical, academic, quick, basic, architecture-design, architecture-design)
        """
        # 分析数据（如果尚未分析）
        if not self.analysis:
            self.analyze_patterns()
        
        # 读取模板
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
        template_file = os.path.join(template_dir, f"{template_type}.md")
        
        if os.path.exists(template_file):
            with open(template_file, 'r', encoding='utf-8') as f:
                template = f.read()
        else:
            # 使用基本模板
            template = """# 研究报告: {topic}

## 执行摘要
{summary}

## 关键发现
{findings_summary}

## 研究方法
{methodology}

## 数据来源
{sources_summary}

## 分析与洞察
{analysis}

## 结论与建议
{conclusions}

## 附录
{appendix}
"""
        
        # 准备报告内容
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 生成发现摘要
        findings_by_category = {}
        for finding in self.findings:
            cat = finding['category']
            if cat not in findings_by_category:
                findings_by_category[cat] = []
            findings_by_category[cat].append(finding)
        
        findings_summary = ""
        for cat, finds in findings_by_category.items():
            findings_summary += f"### {cat}\n"
            for f in finds:
                confidence_star = "★" * int(f['confidence'] * 5)
                findings_summary += f"- {f['finding']} ({confidence_star})\n"
            findings_summary += "\n"
        
        # 生成来源摘要
        sources_summary = f"共收集 {len(self.sources)} 个来源:\n\n"
        for source in self.sources[:10]:  # 最多显示10个
            sources_summary += f"{source['id']}. [{source['type']}] {source.get('url', '无URL')} (可信度: {source['credibility_score']}/10)\n"
        
        if len(self.sources) > 10:
            sources_summary += f"\n... 以及其他 {len(self.sources) - 10} 个来源\n"
        
        # 生成分析摘要
        analysis_summary = f"分析完成于: {self.analysis['analysis_time']}\n\n"
        analysis_summary += f"**发现统计:**\n"
        analysis_summary += f"- 总发现数: {self.analysis['total_findings']}\n"
        
        if 'confidence_stats' in self.analysis:
            for cat, stats in self.analysis['confidence_stats'].items():
                analysis_summary += f"- {cat}: {stats['count']} 个发现 (平均置信度: {stats['avg_confidence']:.2f})\n"
        
        # 填充模板
        report = template.replace('{topic}', self.research_topic)
        report = report.replace('{summary}', f"本研究对'{self.research_topic}'进行了深度分析，共收集{len(self.sources)}个来源，形成{len(self.findings)}个关键发现。")
        report = report.replace('{findings_summary}', findings_summary)
        report = report.replace('{methodology}', "本研究采用多源信息收集、交叉验证和系统性分析方法。")
        report = report.replace('{sources_summary}', sources_summary)
        report = report.replace('{analysis}', analysis_summary)
        report = report.replace('{conclusions}', "基于以上分析，提出以下建议...")
        report = report.replace('{appendix}', f"报告生成时间: {current_time}\n输出目录: {self.output_dir}")
        report = report.replace('{timestamp}', current_time)
        
        # 保存报告
        report_file = os.path.join(self.output_dir, f"research_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"研究报告已生成: {report_file}")
        return report_file
    
    def save_state(self):
        """保存研究状态"""
        state = {
            'research_topic': self.research_topic,
            'output_dir': self.output_dir,
            'sources': self.sources,
            'findings': self.findings,
            'analysis': self.analysis,
            'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        state_file = os.path.join(self.output_dir, "research_state.json")
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        
        return state_file

def create_research_plan(topic, research_questions, output_dir=None):
    """
    创建研究计划
    
    Args:
        topic: 研究主题
        research_questions: 研究问题列表
        output_dir: 输出目录
    """
    if output_dir is None:
        output_dir = f"/app/data/research_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    os.makedirs(output_dir, exist_ok=True)
    
    plan_content = f"""# 研究计划: {topic}

## 研究目标
深度分析{topic}，回答以下关键问题:

## 研究问题
"""
    
    for i, question in enumerate(research_questions, 1):
        plan_content += f"{i}. {question}\n"
    
    plan_content += f"""
## 研究方法
1. **信息收集阶段**
   - 多源信息收集（学术文献、行业报告、新闻、专家观点）
   - 来源可信度评估
   - 信息交叉验证

2. **分析阶段**
   - 关键模式识别
   - 趋势分析
   - 风险评估
   - 机会识别

3. **整合阶段**
   - 研究发现整合
   - 结论提炼
   - 建议制定

## 时间规划
- **阶段1: 信息收集** (预计: 2-3天)
- **阶段2: 深度分析** (预计: 1-2天)
- **阶段3: 报告生成** (预计: 1天)

## 质量标准
1. 每个关键发现必须有至少2个独立来源支持
2. 高可信度来源比例 ≥ 60%
3. 研究发现置信度平均值 ≥ 0.7
4. 研究报告结构完整，逻辑清晰

## 输出物
1. 完整研究报告 (Markdown格式)
2. 研究数据包 (包含所有来源和分析结果)
3. 执行摘要 (1页)
4. 演示文稿 (可选)

---
*计划创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
*使用技能: deep-research v8.0-enhanced*
"""
    
    plan_file = os.path.join(output_dir, "research_plan.md")
    with open(plan_file, 'w', encoding='utf-8') as f:
        f.write(plan_content)
    
    print(f"研究计划已创建: {plan_file}")
    return plan_file

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        topic = sys.argv[1]
        questions = sys.argv[2:] if len(sys.argv) > 2 else ["该主题的主要发展趋势是什么？", "面临的主要挑战有哪些？", "未来的机会在哪里？"]
        
        print(f"创建研究计划: {topic}")
        plan_file = create_research_plan(topic, questions)
        print(f"研究计划文件: {plan_file}")
    else:
        print("用法: python research_engine.py <研究主题> [研究问题1] [研究问题2] ...")
        print("\n示例:")
        print('  python research_engine.py "人工智能在医疗诊断中的应用" "技术现状如何？" "主要挑战是什么？" "未来发展趋势？"')
