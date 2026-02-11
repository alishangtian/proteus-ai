# Skill Usage Monitor

## 📊 Overview

A comprehensive skills usage monitoring and analytics system for Proteus Agent. Tracks skill usage frequency, identifies low-usage skills, and generates detailed usage reports.

## 🚀 Quick Start

### Installation
The skill is already installed in `/app/.proteus/skills/skill-usage-monitor/`

### First Run
```bash
# Navigate to skill directory
cd /app/.proteus/skills/skill-usage-monitor

# Run initial sync
python scripts/generate_report.py --sync

# Generate your first report
python scripts/generate_report.py --days 30 --format markdown
```

### Identify Low-Usage Skills
```bash
python scripts/identify_low_usage.py --threshold 3 --days 30
```

## 🛠️ Core Components

| Component | Description | Location |
|-----------|-------------|----------|
| `monitor.py` | Main monitoring class | `scripts/monitor.py` |
| `recorder.py` | Skill usage recorder | `scripts/recorder.py` |
| `analyzer.py` | Usage analytics | `scripts/analyzer.py` |
| `reporter.py` | Report generation | `scripts/reporter.py` |

## 📈 Key Features

### 1. **Usage Tracking**
- Records skill usage with timestamps
- Tracks success/failure rates
- Measures context length and execution time

### 2. **Low-Usage Detection**
- Identifies skills with ≤3 uses in 30 days
- Detects inactive skills (>60 days)
- Calculates priority scores for review

### 3. **Analytics & Reporting**
- Generates Markdown, JSON, CSV reports
- Provides executive summaries
- Offers improvement recommendations

### 4. **Skill Health Assessment**
- Scores skills 0-100 based on usage
- Generates improvement suggestions
- Identifies merge candidates

## 🔧 Integration Methods

### Option A: Decorator (Simplest)
```python
from scripts.recorder import record_skill_usage

@record_skill_usage("your-skill-name")
def your_skill_function():
    # Your skill logic
    pass
```

### Option B: Context Manager
```python
from scripts.recorder import track_skill_usage

with track_skill_usage("your-skill-name") as tracker:
    # Your skill logic
    result = process_data()
```

### Option C: Manual Recording
```python
from scripts import record_usage_now

record_usage_now("your-skill-name", success=True, context_length=1500)
```

## 📊 Sample Reports

### Executive Summary
```
📊 Executive Summary:
  Health Score: 75 (Good)
  Total Skills: 56
  Active Skills: 42 (75.0%)
  Low-Usage Skills: 14 (25.0%)
  
🏆 Top Skills:
  1. web-scraper: 245 uses (92% success)
  2. pdf-processor: 189 uses (88% success)
  3. data-analyzer: 156 uses (85% success)
```

### Low-Usage Skills Report
```
⚠️ Low-Usage Skills (14 found):
  1. legacy-api-client: 0 uses (Never used)
  2. image-resizer-old: 1 use (90 days ago)
  3. xml-parser-deprecated: 2 uses (120 days ago)
```

## 🗂️ File Structure

```
skill-usage-monitor/
├── SKILL.md                    # Skill documentation
├── README.md                   # This file
├── requirements.txt           # Python dependencies
├── LICENSE.txt               # MIT License
├── scripts/                  # Core Python code
│   ├── __init__.py
│   ├── monitor.py           # Main monitoring class
│   ├── recorder.py         # Usage recording utilities
│   ├── analyzer.py         # Analytics and detection
│   ├── reporter.py         # Report generation
│   ├── generate_report.py  # CLI tool for reports
│   └── identify_low_usage.py # CLI tool for detection
├── examples/                # Example code
│   ├── basic_usage.py      # Basic usage examples
│   └── test_monitor.py     # Test script
└── references/             # Reference materials
    └── troubleshooting.md  # Troubleshooting guide
```

## 📝 Usage Examples

### 1. Basic Monitoring
```python
from scripts.monitor import SkillUsageMonitor

monitor = SkillUsageMonitor()
monitor.record_usage("my-skill", context_length=2000, success=True)
```

### 2. Generate Report
```python
from scripts.reporter import SkillUsageReporter

reporter = SkillUsageReporter()
report = reporter.generate_markdown_report(days=30)
```

### 3. Analyze Usage
```python
from scripts.analyzer import SkillUsageAnalyzer

analyzer = SkillUsageAnalyzer()
analysis = analyzer.analyze_usage_patterns(days=30)
low_usage = analyzer.identify_low_usage_skills(days=30)
```

## 🔍 Database Schema

The system uses SQLite (`/app/data/skill_usage.db`):

### `skills` Table
```sql
CREATE TABLE skills (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    category TEXT,
    description TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    deleted BOOLEAN DEFAULT 0
)
```

### `skill_usage` Table
```sql
CREATE TABLE skill_usage (
    id INTEGER PRIMARY KEY,
    skill_name TEXT,
    skill_id INTEGER,
    context_length INTEGER,
    success BOOLEAN,
    error_message TEXT,
    execution_time REAL,
    metadata TEXT,
    created_at TIMESTAMP
)
```

## 🔄 Maintenance Schedule

| Frequency | Task | Command |
|-----------|------|---------|
| Daily | Check system health | `python scripts/monitor.py --health` |
| Weekly | Generate usage report | `python scripts/generate_report.py --days 7` |
| Monthly | Identify low-usage skills | `python scripts/identify_low_usage.py --days 30` |
| Quarterly | Archive obsolete skills | Manual review |
| Annually | Comprehensive analysis | `python scripts/generate_report.py --days 365 --format all` |

## ⚠️ Troubleshooting

### Common Issues:

1. **"No database found"**
   ```bash
   python scripts/generate_report.py --sync
   ```

2. **"Skill not found in database"**
   ```bash
   python scripts/generate_report.py --sync
   ```

3. **"Permission denied"**
   ```bash
   chmod +x scripts/*.py
   ```

### Database Backup:
```bash
python scripts/monitor.py --backup
```

## 📞 Support

- **Documentation**: See `SKILL.md` for detailed documentation
- **Examples**: Check `examples/` directory for code samples
- **Testing**: Run `python examples/test_monitor.py` for system test

## 📄 License

MIT License - See `LICENSE.txt` for details.

---

**Last Updated**: 2026-02-10  
**Version**: 1.0.0  
**Maintainer**: Skills Monitoring Team
