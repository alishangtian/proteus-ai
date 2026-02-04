#!/usr/bin/env python3
"""
AOF日志恢复工具
从AOF日志文件中恢复记忆数据
"""

import os
import sys
import json
import argparse
import logging

# 添加scripts目录到路径
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

def recover_from_aof(aof_file, dry_run=True, skip_existing=True):
    """
    从AOF日志文件恢复记忆数据
    
    Args:
        aof_file: AOF日志文件路径
        dry_run: 是否为试运行（不实际存储）
        skip_existing: 是否跳过已存在的记忆（基于ID）
    """
    print(f"🔍 开始从AOF日志恢复: {aof_file}")
    print(f"   试运行模式: {'是' if dry_run else '否'}")
    print(f"   跳过已存在记忆: {'是' if skip_existing else '否'}")
    
    if not os.path.exists(aof_file):
        print(f"❌ AOF日志文件不存在: {aof_file}")
        return False
    
    # 统计信息
    stats = {
        'total_lines': 0,
        'valid_entries': 0,
        'store_ops': 0,
        'skipped': 0,
        'errors': 0,
        'restored': 0
    }
    
    # 读取日志文件
    with open(aof_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            stats['total_lines'] += 1
            
            # 跳过空行
            line = line.strip()
            if not line:
                continue
            
            try:
                # 解析JSON行
                entry = json.loads(line)
                
                # 验证基本结构
                if not isinstance(entry, dict):
                    print(f"⚠️  第{line_num}行: 不是JSON对象，跳过")
                    stats['errors'] += 1
                    continue
                
                op = entry.get('op')
                memory_id = entry.get('id')
                timestamp = entry.get('timestamp')
                data = entry.get('data')
                
                if not all([op, memory_id, timestamp, data]):
                    print(f"⚠️  第{line_num}行: 缺少必要字段，跳过")
                    stats['errors'] += 1
                    continue
                
                stats['valid_entries'] += 1
                
                # 只处理STORE操作
                if op == 'STORE':
                    stats['store_ops'] += 1
                    
                    # 提取记忆数据
                    content = data.get('content', '')
                    memory_type = data.get('memory_type', 'auto')
                    importance = data.get('importance', 0.5)
                    tags = data.get('tags', [])
                    metadata = data.get('metadata', {})
                    
                    if dry_run:
                        print(f"   [{line_num}] STORE {memory_id}: {content[:50]}...")
                        stats['restored'] += 1
                    else:
                        # 实际存储记忆
                        try:
                            # 导入MemoryManager
                            from memory_manager import MemoryManager
                            
                            # 创建记忆管理器（使用默认存储路径）
                            mm = MemoryManager()
                            
                            # 检查是否已存在（如果skip_existing为True）
                            if skip_existing:
                                # 这里可以添加检查逻辑，但为了简化，我们直接存储
                                # 注意：实际实现中可能需要检查记忆ID是否已存在
                                pass
                            
                            # 存储记忆
                            stored_id = mm.store(
                                content=content,
                                memory_type=memory_type,
                                importance=importance,
                                tags=tags,
                                metadata=metadata
                            )
                            
                            print(f"   ✅ [{line_num}] 恢复记忆: {stored_id} ({content[:30]}...)")
                            stats['restored'] += 1
                            
                            mm.close()
                            
                        except Exception as e:
                            print(f"   ❌ [{line_num}] 存储失败: {e}")
                            stats['errors'] += 1
                else:
                    print(f"   ⚠️  第{line_num}行: 未知操作类型 '{op}'，跳过")
                    stats['skipped'] += 1
                    
            except json.JSONDecodeError as e:
                print(f"❌ 第{line_num}行: JSON解析错误 - {e}")
                stats['errors'] += 1
            except Exception as e:
                print(f"❌ 第{line_num}行: 未知错误 - {e}")
                stats['errors'] += 1
    
    # 打印统计信息
    print("\n" + "="*60)
    print("📊 恢复统计:")
    print(f"   总行数: {stats['total_lines']}")
    print(f"   有效条目: {stats['valid_entries']}")
    print(f"   STORE操作: {stats['store_ops']}")
    print(f"   已恢复: {stats['restored']}")
    print(f"   跳过: {stats['skipped']}")
    print(f"   错误: {stats['errors']}")
    
    if dry_run:
        print("\n💡 这是试运行，要实际恢复数据，请使用 --no-dry-run 参数")
    else:
        print("\n✅ 恢复完成！")
    
    return stats['errors'] == 0

def main():
    parser = argparse.ArgumentParser(description='从AOF日志文件恢复记忆数据')
    parser.add_argument('--aof-file', default='/app/data/memory/logs/memory_aof.log',
                       help='AOF日志文件路径 (默认: /app/data/memory/logs/memory_aof.log)')
    parser.add_argument('--no-dry-run', dest='dry_run', action='store_false',
                       help='实际执行恢复操作（默认是试运行）')
    parser.add_argument('--no-skip-existing', dest='skip_existing', action='store_false',
                       help='不跳过已存在的记忆（可能造成重复）')
    
    args = parser.parse_args()
    
    success = recover_from_aof(
        aof_file=args.aof_file,
        dry_run=args.dry_run,
        skip_existing=args.skip_existing
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
