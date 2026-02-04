#!/usr/bin/env python3
"""
记忆系统命令行接口
通过直接执行脚本实现记忆的存储和检索，无需初始化类
"""

import sys
import os
import json
import argparse

# 添加scripts目录到路径
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from memory_manager import MemoryManager

def get_memory_manager(config_path=None):
    """获取记忆管理器实例"""
    # 默认配置路径
    if config_path is None:
        config_path = os.path.join(os.path.dirname(script_dir), "assets/templates/config.yaml")
    
    # 如果配置文件不存在，使用默认配置
    if not os.path.exists(config_path):
        config_path = None
    
    return MemoryManager(config_path=config_path)

def store_memory(args):
    """存储记忆"""
    mm = get_memory_manager(args.config)
    
    # 解析标签
    tags = []
    if args.tags:
        tags = [tag.strip() for tag in args.tags.split(',')]
    
    # 解析元数据
    metadata = {}
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError:
            print(f"错误：元数据不是有效的JSON格式: {args.metadata}")
            return 1
    
    # 存储记忆
    memory_id = mm.store(
        content=args.content,
        memory_type=args.memory_type,
        importance=args.importance,
        tags=tags,
        metadata=metadata
    )
    
    print(f"✅ 记忆存储成功！")
    print(f"   记忆ID: {memory_id}")
    print(f"   内容: {args.content[:50]}..." if len(args.content) > 50 else f"   内容: {args.content}")
    print(f"   类型: {args.memory_type}")
    print(f"   重要性: {args.importance}")
    
    return 0

def retrieve_memory(args):
    """检索记忆"""
    mm = get_memory_manager(args.config)
    
    # 解析记忆类型
    memory_types = None
    if args.memory_types:
        memory_types = [mt.strip() for mt in args.memory_types.split(',')]
    
    # 检索记忆
    results = mm.retrieve(
        query=args.query,
        memory_types=memory_types,
        limit=args.limit,
        use_semantic=args.semantic
    )
    
    print(f"🔍 检索到 {len(results)} 条记忆:")
    print()
    
    for i, memory in enumerate(results, 1):
        print(f"{i}. {'='*60}")
        print(f"   ID: {memory.get('id', '未知')}")
        print(f"   内容: {memory.get('content', '无')}")
        print(f"   类型: {memory.get('memory_type', '未知')}")
        print(f"   重要性: {memory.get('importance', 0.0):.2f}")
        print(f"   相关度: {memory.get('relevance', 0.0):.2f}")
        print(f"   标签: {', '.join(memory.get('tags', []))}")
        
        # 显示时间戳
        created_at = memory.get('created_at')
        if created_at:
            from datetime import datetime
            if isinstance(created_at, (int, float)):
                dt = datetime.fromtimestamp(created_at)
                print(f"   时间: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        
        print()
    
    return 0

def get_stats(args):
    """获取统计信息"""
    mm = get_memory_manager(args.config)
    stats = mm.get_stats()
    
    print(f"📊 记忆系统统计:")
    print(f"   短期记忆: {stats.get('short_term', 0)} 条")
    print(f"   中期记忆: {stats.get('medium_term', 0)} 条")
    print(f"   长期记忆: {stats.get('long_term', 0)} 条")
    print(f"   总计: {stats.get('total', 0)} 条")
    
    return 0

def main():
    parser = argparse.ArgumentParser(
        description="记忆系统命令行工具 - 直接执行脚本实现记忆存储和检索",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 存储记忆
  python memory_cli.py store --content "用户喜欢黑咖啡" --importance 0.8 --tags "饮食,偏好"
  
  # 检索记忆
  python memory_cli.py retrieve --query "咖啡" --limit 5
  
  # 获取统计
  python memory_cli.py stats
        """
    )
    
    parser.add_argument('--config', help='配置文件路径（可选）')
    
    # 子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # store命令
    store_parser = subparsers.add_parser('store', help='存储记忆')
    store_parser.add_argument('--content', required=True, help='记忆内容')
    store_parser.add_argument('--memory-type', default='auto', 
                             choices=['auto', 'short_term', 'medium_term', 'long_term'],
                             help='记忆类型 (默认: auto)')
    store_parser.add_argument('--importance', type=float, default=0.5,
                             help='重要性评分 (0.0-1.0, 默认: 0.5)')
    store_parser.add_argument('--tags', help='标签列表，用逗号分隔')
    store_parser.add_argument('--metadata', help='元数据，JSON格式')
    
    # retrieve命令
    retrieve_parser = subparsers.add_parser('retrieve', help='检索记忆')
    retrieve_parser.add_argument('--query', default='', help='搜索查询（可选）')
    retrieve_parser.add_argument('--memory-types', 
                                help='记忆类型列表，用逗号分隔（如: short_term,long_term）')
    retrieve_parser.add_argument('--limit', type=int, default=10,
                                help='返回数量限制 (默认: 10)')
    retrieve_parser.add_argument('--no-semantic', dest='semantic', action='store_false',
                                help='禁用语义搜索')
    retrieve_parser.set_defaults(semantic=True)
    
    # stats命令
    stats_parser = subparsers.add_parser('stats', help='获取统计信息')
    
    # 解析参数
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # 执行命令
    try:
        if args.command == 'store':
            return store_memory(args)
        elif args.command == 'retrieve':
            return retrieve_memory(args)
        elif args.command == 'stats':
            return get_stats(args)
        else:
            parser.print_help()
            return 1
    except Exception as e:
        print(f"❌ 执行命令时出错: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
