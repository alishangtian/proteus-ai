# Troubleshooting Guide

## 🚨 Common Issues and Solutions

### Issue 1: Database Connection Errors

**Symptoms:**
- "Unable to open database file"
- "sqlite3.OperationalError: unable to open database file"
- Permission denied errors

**Solutions:**

1. **Check directory permissions:**
   ```bash
   ls -la /app/data/
   chmod 755 /app/data
   chmod 644 /app/data/skill_usage.db  # If exists
   ```

2. **Create data directory if missing:**
   ```bash
   mkdir -p /app/data
   chmod 755 /app/data
   ```

3. **Manual database initialization:**
   ```python
   import sqlite3
   conn = sqlite3.connect('/app/data/skill_usage.db')
   conn.close()
   ```

### Issue 2: Skill Synchronization Problems

**Symptoms:**
- Skills missing from reports
- "Skill not found" errors
- Outdated skill list

**Solutions:**

1. **Force skill sync:**
   ```bash
   python scripts/generate_report.py --sync
   ```

2. **Manual skill scanning:**
   ```python
   from scripts.monitor import SkillUsageMonitor
   monitor = SkillUsageMonitor()
   monitor.sync_skills()
   ```

3. **Check skill directory structure:**
   ```bash
   # Verify skills exist
   ls -la /app/.proteus/skills/
   
   # Check for SKILL.md files
   find /app/.proteus/skills -name "SKILL.md" | wc -l
   ```

### Issue 3: Recording Failures

**Symptoms:**
- Usage not recorded in database
- "Failed to record skill usage" messages
- Incomplete statistics

**Solutions:**

1. **Test basic recording:**
   ```python
   from scripts.monitor import record_usage_now
   success = record_usage_now("test-skill", context_length=100, success=True)
   print(f"Recording successful: {success}")
   ```

2. **Check database integrity:**
   ```bash
   python -c "import sqlite3; conn = sqlite3.connect('/app/data/skill_usage.db'); print('Database OK' if conn else 'Database error'); conn.close()"
   ```

3. **Enable debug logging:**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   from scripts.monitor import SkillUsageMonitor
   monitor = SkillUsageMonitor()
   ```

### Issue 4: Report Generation Errors

**Symptoms:**
- Empty or incomplete reports
- "No data available" messages
- Formatting errors in output

**Solutions:**

1. **Generate with verbose output:**
   ```bash
   python scripts/generate_report.py --days 30 --format markdown --output debug_report.md
   ```

2. **Check data availability:**
   ```python
   from scripts.monitor import SkillUsageMonitor
   monitor = SkillUsageMonitor()
   stats = monitor.get_usage_stats(days=30)
   print(f"Total skills with stats: {len(stats)}")
   ```

3. **Test individual components:**
   ```bash
   # Test analyzer
   python -c "from scripts.analyzer import analyze_usage; print(analyze_usage(days=7)['summary'])"
   
   # Test reporter
   python -c "from scripts.reporter import generate_markdown_report; report = generate_markdown_report(days=7); print(report[:500])"
   ```

### Issue 5: Performance Problems

**Symptoms:**
- Slow report generation
- High memory usage
- Database queries timing out

**Solutions:**

1. **Cleanup old records:**
   ```bash
   python scripts/generate_report.py --cleanup --days-to-keep 180
   ```

2. **Optimize database:**
   ```bash
   python -c "
   import sqlite3
   conn = sqlite3.connect('/app/data/skill_usage.db')
   conn.execute('VACUUM')
   conn.execute('ANALYZE')
   conn.close()
   print('Database optimized')
   "
   ```

3. **Enable caching:**
   ```python
   # The system has built-in caching (5 minutes)
   # Force cache clear if needed:
   from scripts.monitor import SkillUsageMonitor
   monitor = SkillUsageMonitor()
   monitor._cached_stats.clear()  # Clear cache
   ```

### Issue 6: Integration Problems

**Symptoms:**
- Decorators not recording usage
- Context managers not tracking
- Manual recording not working

**Solutions:**

1. **Test decorator pattern:**
   ```python
   from scripts.recorder import record_skill_usage
   
   @record_skill_usage("test-decorator")
   def test_function():
       return "Test successful"
   
   result = test_function()
   print(f"Function result: {result}")
   ```

2. **Test context manager:**
   ```python
   from scripts.recorder import track_skill_usage
   
   with track_skill_usage("test-context") as tracker:
       print("Inside context manager")
       tracker.add_metadata({"test": "value"})
   ```

3. **Verify imports:**
   ```python
   # Test all imports
   try:
       from scripts.monitor import SkillUsageMonitor
       from scripts.recorder import record_skill_usage, track_skill_usage
       from scripts.analyzer import SkillUsageAnalyzer
       from scripts.reporter import SkillUsageReporter
       print("All imports successful")
   except ImportError as e:
       print(f"Import error: {e}")
   ```

## 🔧 Advanced Troubleshooting

### Database Inspection

**Check database schema:**
```bash
sqlite3 /app/data/skill_usage.db ".schema"
```

**Count records:**
```bash
sqlite3 /app/data/skill_usage.db "SELECT COUNT(*) FROM skills;"
sqlite3 /app/data/skill_usage.db "SELECT COUNT(*) FROM skill_usage;"
```

**View recent usage:**
```bash
sqlite3 /app/data/skill_usage.db "SELECT skill_name, created_at FROM skill_usage ORDER BY created_at DESC LIMIT 10;"
```

### Performance Monitoring

**Check database size:**
```bash
ls -lh /app/data/skill_usage.db
```

**Monitor query performance:**
```python
import time
from scripts.monitor import SkillUsageMonitor

start = time.time()
monitor = SkillUsageMonitor()
stats = monitor.get_usage_stats(days=30)
end = time.time()

print(f"Query took {end - start:.2f} seconds")
print(f"Retrieved {len(stats)} records")
```

### Data Recovery

**Backup database:**
```bash
cp /app/data/skill_usage.db /app/data/skill_usage.db.backup.$(date +%Y%m%d_%H%M%S)
```

**Restore from backup:**
```bash
cp /app/data/skill_usage.db.backup.20260210_120000 /app/data/skill_usage.db
```

**Export data:**
```bash
# Export to CSV
python scripts/generate_report.py --format csv --output backup_data.csv

# Export to JSON
python scripts/generate_report.py --format json --output backup_data.json
```

## 📊 Diagnostic Commands

### Quick System Check
```bash
# Run comprehensive diagnostics
python scripts/monitor.py --health
```

### Skill Discovery Test
```bash
# Test skill scanning
python -c "
from pathlib import Path
skills_dir = Path('/app/.proteus/skills')
skills = [d.name for d in skills_dir.iterdir() if d.is_dir() and d.name != '.proteus']
print(f'Found {len(skills)} skill directories')
for skill in sorted(skills)[:10]:
    print(f'  - {skill}')
"
```

### Recording Test
```bash
# Test recording functionality
python -c "
from scripts import record_usage_now
for i in range(3):
    success = record_usage_now(f'test-skill-{i}', context_length=1000, success=True)
    print(f'Recording {i}: {success}')
"
```

## 🐛 Common Error Messages

### "sqlite3.OperationalError: database is locked"
**Cause:** Multiple processes accessing database
**Fix:** Add small delay or use connection pooling

### "AttributeError: module 'scripts' has no attribute 'monitor'"
**Cause:** Incorrect import path
**Fix:** Ensure script directory is in Python path

### "TypeError: record_skill_usage() missing 1 required positional argument"
**Cause:** Decorator used incorrectly
**Fix:** Use `@record_skill_usage("skill-name")` not `@record_skill_usage`

### "ValueError: No skills found in database"
**Cause:** Empty or uninitialized database
**Fix:** Run `--sync` command to populate database

## 🔄 Maintenance Procedures

### Monthly Maintenance
1. Generate monthly report
2. Identify low-usage skills
3. Backup database
4. Cleanup old records (optional)

### Quarterly Maintenance
1. Comprehensive analysis
2. Review all low-usage skills
3. Archive obsolete skills
4. Update integration patterns

### Emergency Procedures
1. **Database corruption:** Restore from backup
2. **Missing data:** Force re-sync
3. **Performance issues:** Optimize database
4. **Integration failures:** Test with simple example

## 📞 Getting Help

If issues persist:

1. **Check logs:** Look for error messages in output
2. **Simplify:** Test with minimal example
3. **Document:** Note exact error and steps to reproduce
4. **Search:** Check if issue is documented here

**For urgent issues:**
- Restore from latest backup
- Run diagnostic commands above
- Contact system administrator

---

**Last Updated:** 2026-02-10  
**Version:** 1.0.0
