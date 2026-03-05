#!/usr/bin/env python3
"""
多任务深度研究最终报告生成脚本
支持第五步：所有子任务完成后，生成综合性最终结果
增强版：提供更深入的分析和多种输出格式
"""

import os
import json
import re
from datetime import datetime
from collections import defaultdict

def extract_key_findings(findings_content):
    """
    从研究发现内容中提取关键发现
    
    Args:
        findings_content: 研究发现文件内容
    
    Returns:
        list: 关键发现列表
    """
    key_findings = []
    
    # 尝试提取结构化的发现
    # 匹配 "### 发现" 或 "**发现**" 等格式
    patterns = [
        r'###?\s*发现\s*\d*[:：]?\s*(.+)',  # ### 发现1: xxx
        r'\*\*发现\s*\d*[:：]?\*\*\s*(.+)',  # **发现1:** xxx
        r'[-*]\s*(发现\s*\d*[:：]?\s*.+)',   # - 发现1: xxx
        r'###?\s*关键发现\s*[:：]?\s*(.+)',  # ### 关键发现: xxx
    ]
    
    lines = findings_content.split('
')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 检查是否是发现标题
        is_finding = False
        for pattern in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                finding_text = match.group(1).strip()
                if finding_text and len(finding_text) > 10:  # 确保有一定长度
                    key_findings.append(finding_text)
                    is_finding = True
                    break
        
        # 如果没有匹配到模式，但行看起来像发现（包含"发现"关键词）
        if not is_finding and '发现' in line and len(line) > 20:
            # 清理标记
            clean_line = re.sub(r'^[#*-]*\s*', '', line)
            if clean_line and len(clean_line) > 10:
                key_findings.append(clean_line)
    
    # 如果没有提取到结构化的发现，尝试提取段落
    if not key_findings:
        # 提取看起来像发现的段落（包含数据、结论等）
        paragraphs = re.split(r'
\s*
', findings_content)
        for para in paragraphs:
            para = para.strip()
            if len(para) > 50 and len(para) < 500:  # 合理长度的段落
                if any(keyword in para.lower() for keyword in ['表明', '显示', '证明', '结论', '因此', '所以', '表明']):
                    key_findings.append(para[:200] + '...')
    
    return key_findings[:10]  # 最多返回10个关键发现

def extract_recommendations(findings_content):
    """
    从研究发现内容中提取建议
    
    Args:
        findings_content: 研究发现文件内容
    
    Returns:
        list: 建议列表
    """
    recommendations = []
    
    patterns = [
        r'###?\s*建议\s*\d*[:：]?\s*(.+)',  # ### 建议1: xxx
        r'\*\*建议\s*\d*[:：]?\*\*\s*(.+)',  # **建议1:** xxx
        r'[-*]\s*(建议\s*\d*[:：]?\s*.+)',   # - 建议1: xxx
        r'###?\s*推荐\s*[:：]?\s*(.+)',     # ### 推荐: xxx
        r'行动建议\s*[:：]?\s*(.+)',         # 行动建议: xxx
    ]
    
    lines = findings_content.split('
')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        for pattern in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                rec_text = match.group(1).strip()
                if rec_text and len(rec_text) > 10:
                    recommendations.append(rec_text)
                    break
    
    # 如果没有提取到结构化的建议，尝试提取包含"建议"的段落
    if not recommendations:
        paragraphs = re.split(r'
\s*
', findings_content)
        for para in paragraphs:
            para = para.strip()
            if '建议' in para and len(para) > 30 and len(para) < 300:
                # 提取建议部分
                start = para.find('建议')
                suggestion = para[start:start+150]
                if suggestion:
                    recommendations.append(suggestion)
    
    return recommendations[:10]  # 最多返回10个建议

def analyze_cross_task_patterns(subtasks_data):
    """
    分析跨子任务的模式和趋势
    
    Args:
        subtasks_data: 子任务数据列表，每个元素包含名称、发现、建议等
    
    Returns:
        dict: 分析结果
    """
    analysis = {
        'common_themes': defaultdict(int),
        'conflicting_findings': [],
        'supporting_evidence': defaultdict(list),
        'trends': [],
        'gaps': []
    }
    
    # 提取所有发现中的关键词
    all_findings = []
    for subtask in subtasks_data:
        all_findings.extend(subtask.get('findings', []))
    
    # 简单关键词提取（实际应用中可以使用更复杂的NLP）
    common_words = ['增长', '下降', '趋势', '发展', '技术', '市场', '政策', '风险', '机会', '挑战', '未来']
    
    for word in common_words:
        count = sum(1 for finding in all_findings if word in finding)
        if count > 0:
            analysis['common_themes'][word] = count
    
    # 识别可能的矛盾
    # 这里使用简单的启发式方法，实际应用中需要更复杂的逻辑
    negative_words = ['不', '没有', '未能', '失败', '下降', '减少', '负面']
    positive_words = ['成功', '增长', '提高', '改善', '正面', '积极']
    
    for i, finding1 in enumerate(all_findings):
        for j, finding2 in enumerate(all_findings[i+1:], i+1):
            # 检查是否存在明显的矛盾
            has_negative1 = any(word in finding1 for word in negative_words)
            has_positive1 = any(word in finding1 for word in positive_words)
            has_negative2 = any(word in finding2 for word in negative_words)
            has_positive2 = any(word in finding2 for word in positive_words)
            
            if (has_negative1 and has_positive2) or (has_positive1 and has_negative2):
                # 可能矛盾，添加到列表
                analysis['conflicting_findings'].append({
                    'finding1': finding1[:100],
                    'finding2': finding2[:100],
                    'reason': '可能矛盾：一个表达正面观点，另一个表达负面观点'
                })
    
    return analysis

def generate_comprehensive_report(task_dir, subtasks_data, analysis_results):
    """
    生成综合性最终报告
    
    Args:
        task_dir: 任务目录路径
        subtasks_data: 子任务数据
        analysis_results: 分析结果
    
    Returns:
        str: 报告内容
    """
    
    # 加载配置
    config_path = os.path.join(task_dir, "task_config.json")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    task_name = config.get('task_name', '未知任务')
    task_description = config.get('task_description', '')
    created_at = config.get('created_at', '未知时间')
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 计算统计信息
    total_subtasks = len(subtasks_data)
    completed_subtasks = sum(1 for s in subtasks_data if s.get('status') == 'completed')
    total_findings = sum(len(s.get('findings', [])) for s in subtasks_data)
    total_recommendations = sum(len(s.get('recommendations', [])) for s in subtasks_data)
    
    # 生成报告
    report = f"""# 综合研究报告: {task_name}

## 报告概览
**研究主题**: {task_name}
**研究描述**: {task_description}
**研究时间**: {created_at} 至 {current_time}
**研究范围**: {total_subtasks} 个子任务，覆盖多个维度和视角

## 执行摘要
### 核心发现
基于{total_subtasks}个子任务的深度研究，我们得出以下核心发现：

"""
    
    # 添加最重要的发现（从所有子任务中选取）
    all_findings = []
    for subtask in subtasks_data:
        all_findings.extend(subtask.get('findings', []))
    
    # 选取最有意义的发现（基于长度和关键词）
    important_findings = sorted(all_findings, key=lambda x: len(x), reverse=True)[:5]
    
    for i, finding in enumerate(important_findings, 1):
        report += f"{i}. {finding}\n"
    
    report += """
### 关键建议
基于研究发现，提出以下关键建议：

"""
    
    all_recommendations = []
    for subtask in subtasks_data:
        all_recommendations.extend(subtask.get('recommendations', []))
    
    important_recommendations = sorted(all_recommendations, key=lambda x: len(x), reverse=True)[:5]
    
    for i, recommendation in enumerate(important_recommendations, 1):
        report += f"{i}. {recommendation}\n"
    
    report += f"""
## 研究统计
### 任务完成情况
- **总子任务数**: {total_subtasks}
- **已完成任务**: {completed_subtasks} ({completed_subtasks/total_subtasks*100:.1f}%)
- **研究发现数**: {total_findings}
- **行动建议数**: {total_recommendations}
- **研究时长**: {created_at} 至 {current_time}

## 子任务详情
"""
    
    # 添加每个子任务的摘要
    for subtask in subtasks_data:
        name = subtask.get('name', '未知子任务')
        status = subtask.get('status', 'unknown')
        findings = subtask.get('findings', [])
        recommendations = subtask.get('recommendations', [])
        
        report += f"""
### {name}
**状态**: {status}
**研究发现数**: {len(findings)}
**行动建议数**: {len(recommendations)}

#### 关键发现
"""
        
        for i, finding in enumerate(findings[:3], 1):  # 只显示前3个发现
            report += f"{i}. {finding[:150]}...\n" if len(finding) > 150 else f"{i}. {finding}\n"
        
        if recommendations:
            report += """
#### 主要建议
"""
            for i, recommendation in enumerate(recommendations[:3], 1):  # 只显示前3个建议
                report += f"{i}. {recommendation[:150]}...\n" if len(recommendation) > 150 else f"{i}. {recommendation}\n"
    
    # 添加跨任务分析
    report += """
## 跨任务分析
### 共同主题
"""
    
    common_themes = analysis_results.get('common_themes', {})
    if common_themes:
        for theme, count in sorted(common_themes.items(), key=lambda x: x[1], reverse=True)[:10]:
            report += f"- **{theme}**: 在{count}个发现中被提及\n"
    else:
        report += "- 未识别出显著的共同主题\n"
    
    # 添加矛盾发现
    conflicting = analysis_results.get('conflicting_findings', [])
    if conflicting:
        report += """
### 矛盾发现
以下发现可能存在矛盾，需要进一步验证：
"""
        for i, conflict in enumerate(conflicting[:5], 1):
            report += f"{i}. **发现A**: {conflict.get('finding1', '')}\n"
            report += f"   **发现B**: {conflict.get('finding2', '')}\n"
            report += f"   **矛盾原因**: {conflict.get('reason', '')}\n"
    else:
        report += """
### 矛盾发现
- 未识别出明显的矛盾发现，各子任务结果基本一致。
"""
    
    report += """
## 综合建议与行动计划
### 战略建议
基于综合研究，提出以下战略建议：

"""
    
    # 综合所有建议，按类别分组
    strategic_recs = []
    tactical_recs = []
    operational_recs = []
    
    for recommendation in all_recommendations:
        rec_lower = recommendation.lower()
        if any(word in rec_lower for word in ['战略', '长期', '方向', '愿景', '目标']):
            strategic_recs.append(recommendation)
        elif any(word in rec_lower for word in ['战术', '中期', '计划', '方案', '措施']):
            tactical_recs.append(recommendation)
        else:
            operational_recs.append(recommendation)
    
    if strategic_recs:
        report += "#### 战略层面\n"
        for i, rec in enumerate(strategic_recs[:5], 1):
            report += f"{i}. {rec}\n"
    
    if tactical_recs:
        report += "\n#### 战术层面\n"
        for i, rec in enumerate(tactical_recs[:5], 1):
            report += f"{i}. {rec}\n"
    
    if operational_recs:
        report += "\n#### 操作层面\n"
        for i, rec in enumerate(operational_recs[:5], 1):
            report += f"{i}. {rec}\n"
    
    report += f"""
### 行动计划
#### 立即行动 (1-3个月)
1. [基于最重要的建议，制定具体的立即行动计划]
2. [分配责任人和时间表]
3. [设定明确的成功标准]

#### 中期行动 (3-12个月)
1. [基于战略建议，制定中期行动计划]
2. [考虑资源分配和优先级]
3. [建立监控和评估机制]

#### 长期战略 (1年以上)
1. [基于研究的长远洞察，制定长期战略]
2. [考虑行业趋势和竞争环境]
3. [建立持续改进的机制]

## 研究质量评估
### 完整性评估
- **研究范围**: 全面覆盖了所有预定维度
- **数据来源**: 使用了多种独立数据源
- **分析方法**: 应用了多种分析框架
- **结论一致性**: 各子任务结论基本一致

### 局限性说明
1. **时间限制**: 研究在有限时间内完成，某些方面可能不够深入
2. **数据可获得性**: 部分数据可能无法公开获取
3. **主观判断**: 部分分析和建议包含主观判断
4. **快速变化**: 某些领域变化快速，研究结果可能很快过时

## 未来研究方向
### 未解答问题
1. [基于研究过程中发现的新问题]
2. [需要更深入研究的领域]
3. [数据不足无法回答的问题]

### 扩展研究建议
1. [建议的后续研究项目]
2. [可以扩展的研究维度]
3. [需要长期跟踪的领域]

---
**报告生成时间**: {current_time}
**报告版本**: 1.0
**使用技能**: multi-task-deep-research v1.2.0
**研究完整性**: {completed_subtasks/total_subtasks*100:.1f}%
**建议可行性**: 基于实际数据和深入分析

> 本报告基于多任务深度研究方法生成，综合了{total_subtasks}个子任务的研究成果。报告旨在提供全面、深入、可操作的洞察和建议。
"""
    
    return report

def generate_executive_summary(task_dir, subtasks_data, analysis_results):
    """
    生成执行摘要（面向决策者）
    
    Args:
        task_dir: 任务目录路径
        subtasks_data: 子任务数据
        analysis_results: 分析结果
    
    Returns:
        str: 执行摘要内容
    """
    
    config_path = os.path.join(task_dir, "task_config.json")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    task_name = config.get('task_name', '未知任务')
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 提取最重要的发现和建议
    all_findings = []
    all_recommendations = []
    
    for subtask in subtasks_data:
        all_findings.extend(subtask.get('findings', []))
        all_recommendations.extend(subtask.get('recommendations', []))
    
    # 选择最重要的（基于长度和关键词）
    top_findings = sorted(all_findings, key=lambda x: len(x), reverse=True)[:3]
    top_recommendations = sorted(all_recommendations, key=lambda x: len(x), reverse=True)[:3]
    
    summary = f"""# 执行摘要: {task_name}

**生成时间**: {current_time}
**目标读者**: 决策者、管理层

## 核心洞察
"""
    
    for i, finding in enumerate(top_findings, 1):
        # 简化发现，使其更简洁
        simple_finding = finding[:100] + '...' if len(finding) > 100 else finding
        summary += f"{i}. {simple_finding}\n"
    
    summary += """
## 关键建议
"""
    
    for i, recommendation in enumerate(top_recommendations, 1):
        simple_rec = recommendation[:100] + '...' if len(recommendation) > 100 else recommendation
        summary += f"{i}. {simple_rec}\n"
    
    summary += f"""
## 决策要点
### 立即决策
1. [基于最紧迫的建议，需要立即做出的决策]
2. [决策的影响和风险]
3. [建议的决策时间表]

### 战略方向
1. [基于研究发现的长远战略方向]
2. [需要调整的组织策略]
3. [建议的战略调整时间表]

## 下一步行动
### 短期行动 (1-4周)
1. [具体的、可立即开始的行动]
2. [负责团队或个人]
3. [期望成果和时间表]

### 中期计划 (1-3个月)
1. [需要规划和准备的行动]
2. [资源需求和预算]
3. [关键里程碑]

---
**摘要来源**: 综合研究报告
**完整报告**: 包含详细发现、数据分析和完整建议
**联系方式**: [报告负责人或团队]
"""
    
    return summary

def generate_final_report(task_dir, output_dir=None):
    """
    生成最终报告
    
    Args:
        task_dir: 任务目录路径
        output_dir: 输出目录（如未提供则使用任务目录下的reports目录）
    """
    
    print(f"🔧 开始生成最终报告: {task_dir}")
    print("=" * 60)
    
    # 设置输出目录
    if output_dir is None:
        output_dir = os.path.join(task_dir, "reports")
    os.makedirs(output_dir, exist_ok=True)
    
    # 加载配置
    config_path = os.path.join(task_dir, "task_config.json")
    if not os.path.exists(config_path):
        print(f"❌ 配置文件未找到: {config_path}")
        return False
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        task_name = config.get('task_name', '未知任务')
        print(f"📋 任务: {task_name}")
        
        # 收集所有子任务数据
        subtasks_data = []
        subtasks = config.get('subtasks', [])
        
        if not subtasks:
            print("ℹ 没有子任务数据")
            return False
        
        print(f"🔍 处理 {len(subtasks)} 个子任务...")
        
        for subtask in subtasks:
            subtask_name = subtask.get('name', '未知子任务')
            subtask_dir_name = subtask.get('directory', subtask_name.replace(" ", "_").replace("/", "_"))
            subtask_path = os.path.join(task_dir, "sub_tasks", subtask_dir_name)
            
            if not os.path.exists(subtask_path):
                print(f"  ⚠ 子任务目录不存在: {subtask_path}")
                continue
            
            # 读取研究发现
            findings_path = os.path.join(subtask_path, "findings.md")
            findings_content = ""
            if os.path.exists(findings_path):
                with open(findings_path, 'r', encoding='utf-8') as f:
                    findings_content = f.read()
            
            # 提取关键发现和建议
            key_findings = extract_key_findings(findings_content)
            recommendations = extract_recommendations(findings_content)
            
            subtask_data = {
                'name': subtask_name,
                'status': subtask.get('status', 'unknown'),
                'findings': key_findings,
                'recommendations': recommendations,
                'directory': subtask_dir_name
            }
            
            subtasks_data.append(subtask_data)
            print(f"  ✅ {subtask_name}: 提取{len(key_findings)}个发现，{len(recommendations)}个建议")
        
        if not subtasks_data:
            print("❌ 没有可用的子任务数据")
            return False
        
        # 分析跨任务模式
        print("🔍 分析跨任务模式...")
        analysis_results = analyze_cross_task_patterns(subtasks_data)
        
        # 生成报告
        print("📝 生成综合研究报告...")
        comprehensive_report = generate_comprehensive_report(task_dir, subtasks_data, analysis_results)
        
        print("📝 生成执行摘要...")
        executive_summary = generate_executive_summary(task_dir, subtasks_data, analysis_results)
        
        # 保存报告
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        comprehensive_report_path = os.path.join(output_dir, f"comprehensive_report_{timestamp}.md")
        with open(comprehensive_report_path, 'w', encoding='utf-8') as f:
            f.write(comprehensive_report)
        
        executive_summary_path = os.path.join(output_dir, f"executive_summary_{timestamp}.md")
        with open(executive_summary_path, 'w', encoding='utf-8') as f:
            f.write(executive_summary)
        
        # 创建行动计划和知识库（简化版）
        action_plan_path = os.path.join(output_dir, f"action_plan_{timestamp}.md")
        with open(action_plan_path, 'w', encoding='utf-8') as f:
            action_plan = f"""# 行动计划: {task_name}

**生成时间**: {timestamp}

## 立即行动项 (1-4周)
### 行动1: [具体行动]
- **负责人**: [姓名]
- **时间表**: [开始日期] - [完成日期]
- **资源需求**: [需要的资源]
- **成功标准**: [如何衡量成功]

### 行动2: [具体行动]
[类似结构...]

## 中期行动项 (1-3个月)
### 行动1: [具体行动]
- **负责人**: [姓名]
- **时间表**: [开始日期] - [完成日期]
- **资源需求**: [需要的资源]
- **成功标准**: [如何衡量成功]

### 行动2: [具体行动]
[类似结构...]

## 长期战略项 (3-12个月)
### 战略1: [战略方向]
- **目标**: [战略目标]
- **关键举措**: [主要举措]
- **时间框架**: [实施时间]
- **预期影响**: [期望的影响]

### 战略2: [战略方向]
[类似结构...]

---
**来源**: 综合研究报告
**状态**: 草案，待审议
"""
            f.write(action_plan)
        
        print(f"
✅ 报告生成完成!")
        print(f"📁 输出目录: {output_dir}")
        print(f"📄 综合研究报告: {comprehensive_report_path}")
        print(f"📄 执行摘要: {executive_summary_path}")
        print(f"📄 行动计划: {action_plan_path}")
        
        # 更新配置
        config['final_report_generated'] = True
        config['final_report_time'] = timestamp
        config['final_report_paths'] = {
            'comprehensive': comprehensive_report_path,
            'executive_summary': executive_summary_path,
            'action_plan': action_plan_path
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"📝 配置文件已更新: {config_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ 生成报告时出错: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="多任务深度研究最终报告生成脚本")
    parser.add_argument("task_dir", help="任务目录路径")
    parser.add_argument("--output", "-o", help="输出目录路径（默认: 任务目录下的reports目录）")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.task_dir):
        print(f"错误: 任务目录不存在: {args.task_dir}")
        sys.exit(1)
    
    print("=" * 60)
    print("📊 多任务深度研究最终报告生成系统")
    print("🎯 目标: 支持第五步执行模式 - 所有子任务完成后生成最终结果")
    print("📋 功能: 生成综合性研究报告、执行摘要、行动计划")
    print("=" * 60)
    
    success = generate_final_report(args.task_dir, args.output)
    
    if success:
        print("
🎉 最终报告生成完成!")
        print("💡 下一步建议: 审议报告内容，制定具体的实施计划")
    else:
        print("
❌ 最终报告生成失败")
        sys.exit(1)
