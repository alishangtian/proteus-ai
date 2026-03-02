---
name: skill-usage-monitor
description: Skills usage frequency monitoring and analytics system. Tracks skill
  usage, identifies low-usage skills, and generates usage reports. Use when you want
  to monitor skill usage patterns, identify underutilized skills, or generate skill
  usage analytics.
allowed-tools:
- python_execute
version: 1.0.0
---
# Skill Usage Monitor

## 🎯 Overview

A comprehensive skills usage monitoring and analytics system that tracks skill usage frequency, identifies low-usage skills, and generates detailed usage reports.

## 📊 Features

1. **Usage Tracking**: Records skill usage with timestamps and context metadata
2. **Analytics Dashboard**: Provides usage statistics and trends
3. **Low-Usage Detection**: Identifies skills with low usage frequency
4. **Report Generation**: Exports usage reports in JSON format
5. **Historical Analysis**: Tracks usage patterns over time

## 🚀 Quick Start

### Record Skill Usage
```python
from scripts.monitor import SkillUsageMonitor

monitor = SkillUsageMonitor()
monitor.record_usage("skill-name", context_length=1500, success=True)
```

### Generate Usage Report
```bash
python scripts/generate_report.py --days 30 --output report.json
```

### Identify Low-Usage Skills
```bash
python scripts/identify_low_usage.py --threshold 3 --days 30
```

## 🔧 Components

### Core Monitoring System
- `scripts/monitor.py`: Main monitoring class with database operations
- `scripts/recorder.py`: Skill usage recorder with automatic tracking
- `scripts/analyzer.py`: Usage analytics and low-usage detection
- `scripts/reporter.py`: Report generation and export

### Database Schema
The system uses SQLite database (`skill_usage.db`) with two main tables:
- `skills`: Stores skill metadata (name, description)
- `usage_records`: Stores usage events with timestamps and context

### Integration Methods

#### Method 1: Manual Recording
Manually record skill usage in your code:
```python
# In your skill execution script
from scripts.monitor import record_skill_usage

record_skill_usage("your-skill-name")
```

#### Method 2: Automatic Wrapper (Recommended)
Use the skill wrapper to automatically record usage:
```python
from scripts.recorder import record_skill_usage

@record_skill_usage
def execute_skill():
    # Your skill execution logic
    pass
```

## 📈 Usage Analysis

### Metrics Tracked
- **Usage Frequency**: Number of times each skill is used
- **Context Length**: Average context/token usage
- **Success Rate**: Percentage of successful executions
- **Time Patterns**: Usage patterns by time of day, day of week
- **Skill Relationships**: Which skills are often used together

### Low-Usage Skill Criteria
A skill is considered low-usage if:
1. Usage count ≤ 3 in the last 30 days
2. No usage in the last 60 days (inactive)
3. Usage frequency significantly below average

## 📋 Reports

### Standard Report Includes:
1. **Executive Summary**: High-level usage statistics
2. **Top Skills**: Most frequently used skills
3. **Low-Usage Skills**: Skills with minimal usage
4. **Usage Distribution**: Distribution across usage categories
5. **Trend Analysis**: Usage trends over time
6. **Recommendations**: Actions for low-usage skills

### Export Formats
- JSON (machine-readable)
- Markdown (human-readable)
- CSV (spreadsheet compatible)

## 🛠️ Configuration

### Database Location
Default: `/app/data/skill_usage.db`
Override with environment variable: `SKILL_USAGE_DB_PATH`

### Analysis Periods
- Short-term: 7 days (weekly analysis)
- Medium-term: 30 days (monthly analysis)  
- Long-term: 90 days (quarterly analysis)

### Thresholds
- Low-usage threshold: 3 uses per period (configurable)
- Inactive threshold: 60 days without use

## 🔍 Low-Usage Skill Actions

### For Identified Low-Usage Skills:

1. **Review Documentation**: Ensure skill documentation is clear and up-to-date
2. **Check Dependencies**: Verify all dependencies are properly installed
3. **Test Functionality**: Run tests to ensure skill works correctly
4. **Consider Merging**: If similar functionality exists in other skills
5. **Archive Consideration**: If skill is truly obsolete
6. **Promotion**: If skill is valuable but underutilized

### Archive Criteria
Consider archiving a skill if:
- No usage for 90+ days
- Functionality duplicated in other skills
- Obsolete technology or approach
- Better alternatives available



## 🔌 Integration with Existing Skills

### Method 1: Decorator Pattern (Recommended)

The easiest way to integrate monitoring is to use the decorator:

```python
from scripts.recorder import record_skill_usage

@record_skill_usage("your-skill-name", track_context=True)
def execute_skill(input_data, context_length=None):
    # Your skill logic here
    try:
        result = process_input(input_data)
        return {
            "success": True,
            "result": result,
            "context_length": context_length or len(str(input_data))
        }
    except Exception as e:
        raise e
```

### Method 2: Context Manager

```python
from scripts.recorder import track_skill_usage

def execute_skill_with_monitoring():
    with track_skill_usage("your-skill-name", context_length=1500) as tracker:
        result = do_work()
        tracker.add_metadata({"custom_field": "value"})
        return result
```

### Method 3: Manual Recording

```python
from scripts import record_usage_now

def execute_skill():
    try:
        start_time = time.time()
        result = complex_operation()
        
        record_usage_now(
            "your-skill-name",
            context_length=calculate_context(),
            execution_time=time.time() - start_time,
            success=True,
            metadata={"result_type": type(result).__name__}
        )
        
        return result
    except Exception as e:
        record_usage_now(
            "your-skill-name",
            error_message=str(e),
            execution_time=time.time() - start_time,
            success=False
        )
        raise
```

## 📊 Quick Start Examples

### Example 1: Web Scraper with Monitoring

```python
from scripts.recorder import record_skill_usage
import requests

@record_skill_usage("web-scraper")
def scrape_website(url, selector=None):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Parse and return content
        return {"success": True, "content": response.text[:500]}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

### Example 2: Document Processor

```python
from scripts import track_skill_usage
from pathlib import Path

def process_document(file_path):
    with track_skill_usage("document-processor") as tracker:
        if not Path(file_path).exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Process document
        results = {"processed": True, "file": file_path}
        tracker.add_metadata({"file_size": Path(file_path).stat().st_size})
        
        return results
```

## 🚀 Getting Started Checklist

### Step 1: Installation Check
```bash
cd /app/.proteus/skills
ls -la skill-usage-monitor/
```

### Step 2: Initial Setup
```bash
# Run initial sync
python skill-usage-monitor/scripts/generate_report.py --sync

# Generate initial report
python skill-usage-monitor/scripts/generate_report.py --days 7 --format markdown
```

### Step 3: Integrate Monitoring
1. Choose a simple skill
2. Add the decorator pattern
3. Test the skill
4. Verify recording works

### Step 4: First Analysis
```bash
# Identify low-usage skills
python skill-usage-monitor/scripts/identify_low_usage.py --threshold 3 --days 30

# Generate report
python skill-usage-monitor/scripts/generate_report.py --days 30 --format all
```

## 🛡️ Data Privacy

### What's Collected
- Skill names and timestamps
- Success/failure status
- Error messages (for debugging)
- Context length and execution time
- Custom metadata (optional)

### What's NOT Collected
- User personal information
- Input/output data content
- System credentials or secrets

### Data Retention
- Active records: 365 days
- Local storage only (SQLite)
- No external transmission
## 📝 Best Practices

### Recording Usage
- Record both successful and failed executions
- Include context length for resource analysis
- Add metadata for advanced analytics
- Ensure privacy and data protection

### Regular Maintenance
- Run weekly usage reports
- Monthly low-usage skill review
- Quarterly comprehensive analysis
- Annual skill portfolio review

### Integration Guidelines
- Integrate recording in skill entry points
- Use consistent skill naming
- Include error handling for recording failures
- Keep recording overhead minimal

## ⚠️ Troubleshooting

### Common Issues
1. **Database errors**: Check file permissions and disk space
2. **Recording failures**: Ensure database connection is valid
3. **Missing skills**: Run skill synchronization manually
4. **Performance issues**: Consider database optimization

### Recovery Procedures
- Database backup: `/app/data/skill_usage.db.bak`
- Manual sync: `python scripts/monitor.py --sync`
- Report regeneration: `python scripts/reporter.py --regenerate`

## 📞 Support

### Getting Help
1. Check `references/troubleshooting.md` for common issues
2. Review example usage in `examples/` directory
3. Contact system administrator for persistent issues

### Contributing
- Report bugs via GitHub issues
- Submit improvements via pull requests
- Share usage patterns and insights

---

**Last Updated**: 2026-02-10
**Version**: 1.0.0
**Maintainer**: Skills Monitoring Team
**License**: MIT
