#!/usr/bin/env python3
"""
技能使用监控系统主模块 - 核心功能
"""

import json
import sqlite3
import threading
import time
import shutil
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional


class SkillUsageMonitor:
    """技能使用监控系统主类"""
    
    def __init__(self, db_path: str = None):
        """初始化监控系统"""
        if db_path is None:
            data_dir = Path("/app/data")
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / "skill_usage.db")
        
        self.db_path = db_path
        
        # 锁用于线程安全
        self._lock = threading.RLock()
        
        # 缓存
        self._cached_stats = {}
        self._cache_time = {}
        self._cache_duration = 300  # 5分钟
        
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 创建技能表
            cursor.execute('CREATE TABLE IF NOT EXISTS skills (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, category TEXT, description TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, deleted BOOLEAN DEFAULT 0)')
            
            # 创建使用记录表
            cursor.execute('CREATE TABLE IF NOT EXISTS skill_usage (id INTEGER PRIMARY KEY AUTOINCREMENT, skill_name TEXT NOT NULL, skill_id INTEGER, context_length INTEGER DEFAULT 0, success BOOLEAN DEFAULT 1, error_message TEXT, execution_time REAL, metadata TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (skill_id) REFERENCES skills (id))')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_skill_usage_skill_name ON skill_usage (skill_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_skill_usage_created_at ON skill_usage (created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_skill_usage_success ON skill_usage (success)')
            
            conn.commit()
            conn.close()
    
    def record_usage(self, skill_name: str, **kwargs) -> bool:
        """
        记录技能使用
        
        Args:
            skill_name: 技能名称
            **kwargs: 额外参数
                - context_length: 上下文长度
                - success: 是否成功 (默认: True)
                - error_message: 错误信息
                - execution_time: 执行时间（秒）
                - metadata: 额外元数据（字典或JSON字符串）
        
        Returns:
            是否成功记录
        """
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # 获取技能ID（如果不存在则创建）
                cursor.execute("SELECT id FROM skills WHERE name = ?", (skill_name,))
                result = cursor.fetchone()
                
                if result:
                    skill_id = result[0]
                else:
                    # 创建新技能记录
                    category = self._guess_category(skill_name)
                    cursor.execute(
                        "INSERT INTO skills (name, category) VALUES (?, ?)",
                        (skill_name, category)
                    )
                    skill_id = cursor.lastrowid
                
                # 准备数据
                context_length = kwargs.get('context_length', 0)
                success = kwargs.get('success', True)
                error_message = kwargs.get('error_message')
                execution_time = kwargs.get('execution_time')
                
                # 处理metadata
                metadata = kwargs.get('metadata')
                if metadata and not isinstance(metadata, str):
                    metadata = json.dumps(metadata)
                
                # 插入使用记录
                cursor.execute('INSERT INTO skill_usage (skill_name, skill_id, context_length, success, error_message, execution_time, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)', (skill_name, skill_id, context_length, success, error_message, execution_time, metadata))
                
                # 更新技能的最后更新时间
                cursor.execute(
                    "UPDATE skills SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (skill_id,)
                )
                
                conn.commit()
                conn.close()
                
                # 清除缓存
                cache_key = f"stats_{hash(skill_name)}"
                if cache_key in self._cached_stats:
                    del self._cached_stats[cache_key]
                
                return True
                
        except Exception as e:
            print(f"记录技能使用失败: {e}")
            return False
    
    def _guess_category(self, skill_name: str) -> str:
        """根据技能名称猜测分类"""
        name_lower = skill_name.lower()
        
        # 检查名称关键词
        if any(word in name_lower for word in ['web', 'http', 'api', 'crawl', 'scrap', 'request']):
            return "web"
        elif any(word in name_lower for word in ['pdf', 'doc', 'excel', 'word', 'office', 'document']):
            return "document"
        elif any(word in name_lower for word in ['image', 'photo', 'visual', 'vision', 'video', 'audio']):
            return "multimedia"
        elif any(word in name_lower for word in ['data', 'analys', 'process', 'transform', 'convert']):
            return "data-processing"
        elif any(word in name_lower for word in ['memory', 'storage', 'db', 'database', 'vector', 'cache']):
            return "storage"
        elif any(word in name_lower for word in ['search', 'query', 'index', 'retrieve']):
            return "search"
        elif any(word in name_lower for word in ['code', 'program', 'script', 'exec', 'python', 'shell']):
            return "code"
        elif any(word in name_lower for word in ['skill', 'manage', 'monitor', 'system', 'admin']):
            return "system"
        elif any(word in name_lower for word in ['test', 'debug', 'valid', 'verify', 'check']):
            return "testing"
        else:
            return "uncategorized"
    
    def get_usage_stats(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        获取技能使用统计
        
        Args:
            days: 分析天数
        
        Returns:
            技能统计列表
        """
        cache_key = f"stats_all_{days}"
        current_time = time.time()
        
        # 检查缓存
        if cache_key in self._cached_stats:
            cache_time = self._cache_time.get(cache_key, 0)
            if current_time - cache_time < self._cache_duration:
                return self._cached_stats[cache_key]
        
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取技能列表
            cursor.execute("SELECT name, category, description FROM skills WHERE deleted = 0 ORDER BY name")
            skills = cursor.fetchall()
            
            # 计算时间范围
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
            
            results = []
            for skill_name, category, description in skills:
                # 获取使用统计
                cursor.execute('SELECT COUNT(*) as usage_count, MAX(created_at) as last_used, AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) * 100 as success_rate, AVG(context_length) as avg_context_length, AVG(execution_time) as avg_execution_time FROM skill_usage WHERE skill_name = ? AND created_at >= ?', (skill_name, cutoff_date))
                
                stats = cursor.fetchone()
                
                if stats:
                    usage_count, last_used, success_rate, avg_context_length, avg_execution_time = stats
                    
                    # 计算距离上次使用的天数
                    if last_used:
                        try:
                            last_used_dt = datetime.fromisoformat(last_used.replace('Z', '+00:00'))
                            days_since = (datetime.now() - last_used_dt).days
                        except:
                            days_since = None
                    else:
                        days_since = None
                    
                    skill_data = {
                        'name': skill_name,
                        'category': category or 'uncategorized',
                        'description': description or '',
                        'usage_count': usage_count or 0,
                        'last_used': last_used,
                        'days_since_last_use': days_since,
                        'success_rate': round(success_rate, 1) if success_rate else None,
                        'avg_context_length': round(avg_context_length) if avg_context_length else None,
                        'avg_execution_time': round(avg_execution_time, 3) if avg_execution_time else None
                    }
                else:
                    # 没有使用记录
                    skill_data = {
                        'name': skill_name,
                        'category': category or 'uncategorized',
                        'description': description or '',
                        'usage_count': 0,
                        'last_used': None,
                        'days_since_last_use': None,
                        'success_rate': None,
                        'avg_context_length': None,
                        'avg_execution_time': None
                    }
                
                results.append(skill_data)
            
            conn.close()
            
            # 缓存结果
            self._cached_stats[cache_key] = results
            self._cache_time[cache_key] = current_time
            
            return results
    
    def identify_low_usage_skills(self, days: int = 30, 
                                 usage_threshold: int = 3,
                                 inactive_days: int = 60) -> List[Dict[str, Any]]:
        """
        识别低使用率技能
        
        Args:
            days: 分析天数
            usage_threshold: 使用次数阈值（≤此值为低使用率）
            inactive_days: 不活跃天数阈值（≥此值为不活跃）
        
        Returns:
            低使用率技能列表，包含原因
        """
        stats = self.get_usage_stats(days)
        
        low_usage_skills = []
        for skill in stats:
            reasons = []
            
            # 检查使用次数
            if skill['usage_count'] <= usage_threshold:
                if skill['usage_count'] == 0:
                    reasons.append("从未使用")
                elif skill['usage_count'] <= usage_threshold:
                    reasons.append(f"使用次数少（≤{usage_threshold}次）")
            
            # 检查不活跃时间
            if skill['last_used'] and skill['days_since_last_use']:
                if skill['days_since_last_use'] >= inactive_days:
                    reasons.append(f"长期不活跃（≥{inactive_days}天）")
            
            # 检查成功率
            if skill['success_rate'] is not None and skill['success_rate'] < 70:
                reasons.append(f"低成功率（{skill['success_rate']}%）")
            
            # 检查上下文长度（可能表明复杂或难用）
            if skill['avg_context_length'] and skill['avg_context_length'] > 5000:
                reasons.append("高上下文需求")
            
            # 如果有任何原因，标记为低使用率
            if reasons:
                low_skill = skill.copy()
                low_skill['reasons'] = reasons
                low_skill['severity'] = len(reasons)  # 严重程度基于原因数量
                
                # 计算优先级分数（0-100，越高越优先处理）
                priority_score = 0
                if skill['usage_count'] == 0:
                    priority_score += 30
                if skill['days_since_last_use'] and skill['days_since_last_use'] >= 90:
                    priority_score += 20
                if skill['success_rate'] and skill['success_rate'] < 50:
                    priority_score += 25
                if '高上下文需求' in reasons:
                    priority_score += 15
                
                low_skill['priority_score'] = priority_score
                low_usage_skills.append(low_skill)
        
        # 按优先级排序
        low_usage_skills.sort(key=lambda x: x['priority_score'], reverse=True)
        
        return low_usage_skills
    
    def sync_skills(self):
        """同步技能数据库"""
        skills_dir = Path("/app/.proteus/skills")
        
        if not skills_dir.exists():
            return
        
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取现有技能
            cursor.execute("SELECT name FROM skills")
            existing_skills = {row[0] for row in cursor.fetchall()}
            
            # 扫描目录
            for item in skills_dir.iterdir():
                if item.is_dir() and item.name != ".proteus":
                    skill_name = item.name
                    
                    if skill_name not in existing_skills:
                        # 创建新技能记录
                        category = self._guess_category(skill_name)
                        cursor.execute("INSERT OR IGNORE INTO skills (name, category) VALUES (?, ?)", (skill_name, category))
            
            conn.commit()
            conn.close()
            
            # 清除缓存
            self._cached_stats.clear()
    
    def get_system_health(self) -> Dict[str, Any]:
        """
        获取系统健康状态
        
        Returns:
            健康状态数据
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取数据库统计
            cursor.execute("SELECT COUNT(*) FROM skills")
            total_skills = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM skill_usage")
            total_records = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM skill_usage WHERE success = 0")
            failed_records = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT skill_name) FROM skill_usage WHERE created_at >= datetime('now', '-30 days')")
            active_skills = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM skills WHERE deleted = 1")
            deleted_skills = cursor.fetchone()[0]
            
            conn.close()
            
            # 计算健康分数
            if total_skills > 0:
                usage_rate = (active_skills / total_skills) * 100
                error_rate = (failed_records / total_records * 100) if total_records > 0 else 0
            else:
                usage_rate = 0
                error_rate = 0
            
            # 健康分数（0-100）
            health_score = 0
            if total_skills >= 10:
                health_score += 20
            
            if usage_rate >= 50:
                health_score += 30
            elif usage_rate >= 20:
                health_score += 15
            
            if error_rate <= 10:
                health_score += 30
            elif error_rate <= 20:
                health_score += 15
            
            if deleted_skills <= total_skills * 0.2:
                health_score += 20
            
            return {
                'total_skills': total_skills,
                'active_skills': active_skills,
                'inactive_skills': total_skills - active_skills,
                'usage_rate': round(usage_rate, 1),
                'total_records': total_records,
                'failed_records': failed_records,
                'error_rate': round(error_rate, 1),
                'deleted_skills': deleted_skills,
                'health_score': min(100, health_score),
                'health_status': self._get_health_status(health_score),
                'database_size': Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
            }
    
    def _get_health_status(self, score: float) -> str:
        """获取健康状态描述"""
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
    
    def backup_database(self, backup_dir: str = None) -> str:
        """
        备份数据库
        
        Args:
            backup_dir: 备份目录
        
        Returns:
            备份文件路径
        """
        if backup_dir is None:
            backup_dir = "/app/data/backups"
        
        Path(backup_dir).mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = str(Path(backup_dir) / f"skill_usage_{timestamp}.db")
        
        with self._lock:
            shutil.copy2(self.db_path, backup_path)
        
        return backup_path
    
    def cleanup_old_records(self, days_to_keep: int = 365) -> int:
        """
        清理旧记录
        
        Args:
            days_to_keep: 保留天数
        
        Returns:
            删除的记录数
        """
        cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).strftime('%Y-%m-d %H:%M:%S')
        
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取要删除的记录数
            cursor.execute("SELECT COUNT(*) FROM skill_usage WHERE created_at < ?", (cutoff_date,))
            count = cursor.fetchone()[0]
            
            if count > 0:
                # 删除记录
                cursor.execute("DELETE FROM skill_usage WHERE created_at < ?", (cutoff_date,))
                
                # 清理孤立的技能记录
                cursor.execute('DELETE FROM skills WHERE id IN (SELECT s.id FROM skills s LEFT JOIN skill_usage u ON s.id = u.skill_id WHERE u.id IS NULL AND s.deleted = 1 AND s.updated_at < ?)', (cutoff_date,))
                
                conn.commit()
            
            conn.close()
            
            # 清除缓存
            self._cached_stats.clear()
            
            return count


# 便捷函数
def create_monitor_instance() -> SkillUsageMonitor:
    """创建监控实例"""
    return SkillUsageMonitor()

def record_usage_now(skill_name: str, **kwargs) -> bool:
    """立即记录技能使用"""
    monitor = SkillUsageMonitor()
    return monitor.record_usage(skill_name, **kwargs)
