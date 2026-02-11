"""
技能使用监控系统 - Python包
支持相对和绝对导入
"""

# 动态导入模块
import sys
import os

# 添加当前目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 导出所有公开的API
# 这些会在首次导入时动态加载
__all__ = [
    'SkillUsageMonitor',
    'create_monitor_instance',
    'SkillUsageAnalyzer',
    'SkillUsageReporter',
    'record_skill_usage',
    'auto_record_skill_usage',
    'track_skill_usage',
    'record_usage_now',
    'record_successful_usage',
    'record_failed_usage',
    'get_monitor',
    'analyze_usage',
    'find_low_usage_skills',
    'find_candidate_merges',
    'get_skill_health',
    'generate_markdown_report',
    'generate_json_report',
    'generate_executive_summary'
]

# 版本信息
__version__ = "1.0.0"
__author__ = "Skills Monitoring Team"

# 延迟导入函数
def __getattr__(name):
    """动态导入模块属性"""
    if name in __all__:
        # 根据名称导入相应的模块
        if name in ['SkillUsageMonitor', 'create_monitor_instance', 'record_usage_now']:
            from monitor import SkillUsageMonitor, create_monitor_instance, record_usage_now
            if name == 'SkillUsageMonitor':
                return SkillUsageMonitor
            elif name == 'create_monitor_instance':
                return create_monitor_instance
            elif name == 'record_usage_now':
                return record_usage_now
        elif name in ['record_skill_usage', 'auto_record_skill_usage', 'track_skill_usage', 
                      'record_successful_usage', 'record_failed_usage', 'get_monitor']:
            from recorder import (record_skill_usage, auto_record_skill_usage, 
                                track_skill_usage, record_successful_usage, 
                                record_failed_usage, get_monitor)
            return locals()[name]
        elif name in ['SkillUsageAnalyzer', 'analyze_usage', 'find_low_usage_skills',
                     'find_candidate_merges', 'get_skill_health']:
            from analyzer import (SkillUsageAnalyzer, analyze_usage, find_low_usage_skills,
                                find_candidate_merges, get_skill_health)
            return locals()[name]
        elif name in ['SkillUsageReporter', 'generate_markdown_report', 
                     'generate_json_report', 'generate_executive_summary']:
            from reporter import (SkillUsageReporter, generate_markdown_report,
                                generate_json_report, generate_executive_summary)
            return locals()[name]
    
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

# 预导入一些常用模块以便直接访问
try:
    from monitor import SkillUsageMonitor, create_monitor_instance, record_usage_now
    from recorder import (record_skill_usage, track_skill_usage, get_monitor)
    from analyzer import SkillUsageAnalyzer, analyze_usage, find_low_usage_skills
    from reporter import SkillUsageReporter, generate_markdown_report
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import monitor
    import recorder
    import analyzer
    import reporter
    
    SkillUsageMonitor = monitor.SkillUsageMonitor
    create_monitor_instance = monitor.create_monitor_instance
    record_usage_now = monitor.record_usage_now
    
    record_skill_usage = recorder.record_skill_usage
    track_skill_usage = recorder.track_skill_usage
    get_monitor = recorder.get_monitor
    
    SkillUsageAnalyzer = analyzer.SkillUsageAnalyzer
    analyze_usage = analyzer.analyze_usage
    find_low_usage_skills = analyzer.find_low_usage_skills
    
    SkillUsageReporter = reporter.SkillUsageReporter
    generate_markdown_report = reporter.generate_markdown_report
