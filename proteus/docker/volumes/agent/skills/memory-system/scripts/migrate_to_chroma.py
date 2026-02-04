"""
数据迁移脚本 - 将旧版JSON记忆数据迁移到SQLite + Chroma架构
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DataMigrator:
    """数据迁移器"""
    
    def __init__(self, storage_base="/app/data/memory"):
        """
        初始化迁移器
        
        Args:
            storage_base: 存储根目录
        """
        self.storage_base = storage_base
        
        # 旧版文件路径
        self.old_long_term_file = os.path.join(storage_base, "long", "memories.json")
        self.old_vectors_file = os.path.join(storage_base, "vectors", "embeddings.json")
        
        # 新版目录
        self.new_sqlite_db = os.path.join(storage_base, "long", "memory.db")
        self.new_chroma_dir = os.path.join(storage_base, "chroma")
        
        logger.info(f"数据迁移器初始化")
        logger.info(f"旧版长期记忆文件: {self.old_long_term_file}")
        logger.info(f"旧版向量文件: {self.old_vectors_file}")
        logger.info(f"新版SQLite数据库: {self.new_sqlite_db}")
        logger.info(f"新版Chroma目录: {self.new_chroma_dir}")
    
    def check_old_data_exists(self) -> bool:
        """检查旧数据是否存在"""
        long_term_exists = os.path.exists(self.old_long_term_file)
        vectors_exists = os.path.exists(self.old_vectors_file)
        
        logger.info(f"旧版长期记忆文件存在: {long_term_exists}")
        logger.info(f"旧版向量文件存在: {vectors_exists}")
        
        return long_term_exists or vectors_exists
    
    def load_old_memories(self) -> List[Dict[str, Any]]:
        """加载旧版记忆数据"""
        memories = []
        
        if os.path.exists(self.old_long_term_file):
            try:
                with open(self.old_long_term_file, 'r', encoding='utf-8') as f:
                    memories = json.load(f)
                logger.info(f"从 {self.old_long_term_file} 加载了 {len(memories)} 条记忆")
            except Exception as e:
                logger.error(f"加载旧版记忆文件失败: {e}")
        
        return memories
    
    def load_old_vectors(self) -> Dict[str, Any]:
        """加载旧版向量数据"""
        vectors = {}
        
        if os.path.exists(self.old_vectors_file):
            try:
                with open(self.old_vectors_file, 'r', encoding='utf-8') as f:
                    vectors = json.load(f)
                logger.info(f"从 {self.old_vectors_file} 加载了 {len(vectors)} 个向量")
            except Exception as e:
                logger.error(f"加载旧版向量文件失败: {e}")
        
        return vectors
    
    def create_backup(self) -> str:
        """创建数据备份"""
        backup_dir = os.path.join(self.storage_base, "backup")
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"migration_backup_{timestamp}.json")
        
        backup_data = {
            "timestamp": timestamp,
            "old_memories": self.load_old_memories(),
            "old_vectors": self.load_old_vectors(),
            "metadata": {
                "storage_base": self.storage_base,
                "migration_tool": "migrate_to_chroma.py"
            }
        }
        
        try:
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            logger.info(f"数据备份已创建: {backup_file}")
            return backup_file
        except Exception as e:
            logger.error(f"创建备份失败: {e}")
            return ""
    
    def migrate_to_sqlite(self) -> Dict[str, Any]:
        """
        迁移到SQLite数据库
        
        Returns:
            Dict: 迁移统计信息
        """
        stats = {
            "total_memories": 0,
            "migrated": 0,
            "skipped": 0,
            "failed": 0,
            "errors": []
        }
        
        memories = self.load_old_memories()
        stats["total_memories"] = len(memories)
        
        if not memories:
            logger.info("没有需要迁移的记忆数据")
            return stats
        
        try:
            # 导入SQLiteStore
            from scripts.sqlite_store import SQLiteStore
            
            # 初始化SQLite存储
            sqlite_store = SQLiteStore(self.new_sqlite_db)
            
            for memory in memories:
                try:
                    memory_id = memory.get("id")
                    content = memory.get("content", "")
                    importance = memory.get("importance", 0.5)
                    memory_type = memory.get("memory_type", "long_term")
                    tags = memory.get("tags", [])
                    metadata = memory.get("metadata", {})
                    
                    # 添加迁移标记
                    if metadata is None:
                        metadata = {}
                    metadata["migrated_from"] = "legacy_json"
                    metadata["original_created_at"] = memory.get("created_at")
                    
                    # 存储到SQLite
                    success = sqlite_store.store_memory(
                        memory_id=memory_id,
                        content=content,
                        importance=importance,
                        memory_type=memory_type,
                        tags=tags,
                        metadata=metadata
                    )
                    
                    if success:
                        stats["migrated"] += 1
                    else:
                        stats["skipped"] += 1  # 可能是重复内容
                        
                except Exception as e:
                    stats["failed"] += 1
                    stats["errors"].append(f"记忆ID {memory.get('id', 'unknown')}: {str(e)}")
                    logger.warning(f"迁移记忆失败: {memory.get('id', 'unknown')} - {e}")
            
            sqlite_store.close()
            logger.info(f"SQLite迁移完成: {stats['migrated']}条成功, {stats['skipped']}条跳过, {stats['failed']}条失败")
            
        except ImportError as e:
            error_msg = f"无法导入SQLiteStore: {e}"
            stats["errors"].append(error_msg)
            logger.error(error_msg)
        except Exception as e:
            error_msg = f"SQLite迁移过程失败: {e}"
            stats["errors"].append(error_msg)
            logger.error(error_msg)
        
        return stats
    
    def migrate_to_chroma(self) -> Dict[str, Any]:
        """
        迁移向量数据到Chroma
        
        Returns:
            Dict: 迁移统计信息
        """
        stats = {
            "total_vectors": 0,
            "migrated": 0,
            "failed": 0,
            "errors": []
        }
        
        vectors = self.load_old_vectors()
        stats["total_vectors"] = len(vectors)
        
        if not vectors:
            logger.info("没有需要迁移的向量数据")
            return stats
        
        try:
            # 导入Chroma客户端
            from scripts.chroma_client import create_chroma_client
            
            # 初始化Chroma
            chroma_config = {
                "persist_directory": self.new_chroma_dir,
                "collection_name": "memories"
            }
            
            chroma_client = create_chroma_client(chroma_config)
            
            batch_size = 100
            current_batch = []
            batch_ids = []
            
            for memory_id, vector_data in vectors.items():
                try:
                    embedding = vector_data.get("embedding", [])
                    text = vector_data.get("text", "")
                    importance = vector_data.get("importance", 0.5)
                    created_at = vector_data.get("created_at", datetime.now().isoformat())
                    
                    if embedding and text:
                        metadata = {
                            "memory_id": memory_id,
                            "importance": importance,
                            "migrated_from": "legacy_vectors",
                            "original_timestamp": created_at
                        }
                        
                        current_batch.append({
                            "id": memory_id,
                            "embedding": embedding,
                            "document": text,
                            "metadata": metadata
                        })
                        batch_ids.append(memory_id)
                        
                        # 批量处理
                        if len(current_batch) >= batch_size:
                            self._add_batch_to_chroma(chroma_client, current_batch, stats)
                            current_batch = []
                            batch_ids = []
                            
                except Exception as e:
                    stats["failed"] += 1
                    stats["errors"].append(f"向量 {memory_id}: {str(e)}")
                    logger.warning(f"处理向量失败: {memory_id} - {e}")
            
            # 处理最后一批
            if current_batch:
                self._add_batch_to_chroma(chroma_client, current_batch, stats)
            
            logger.info(f"Chroma迁移完成: {stats['migrated']}个成功, {stats['failed']}个失败")
            
        except ImportError as e:
            error_msg = f"无法导入Chroma客户端: {e}"
            stats["errors"].append(error_msg)
            logger.error(error_msg)
        except Exception as e:
            error_msg = f"Chroma迁移过程失败: {e}"
            stats["errors"].append(error_msg)
            logger.error(error_msg)
        
        return stats
    
    def _add_batch_to_chroma(self, chroma_client, batch: List[Dict], stats: Dict):
        """批量添加到Chroma"""
        try:
            vectors = [item["embedding"] for item in batch]
            ids = [item["id"] for item in batch]
            documents = [item["document"] for item in batch]
            metadatas = [item["metadata"] for item in batch]
            
            success = chroma_client.add_embeddings(
                vectors=vectors,
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            
            if success:
                stats["migrated"] += len(batch)
                logger.info(f"批量添加 {len(batch)} 个向量到Chroma成功")
            else:
                stats["failed"] += len(batch)
                logger.warning(f"批量添加 {len(batch)} 个向量到Chroma失败")
                
        except Exception as e:
            stats["failed"] += len(batch)
            stats["errors"].append(f"批量添加失败: {str(e)}")
            logger.error(f"批量添加到Chroma失败: {e}")
    
    def run_migration(self, backup_first: bool = True) -> Dict[str, Any]:
        """
        运行完整迁移流程
        
        Args:
            backup_first: 是否先创建备份
            
        Returns:
            Dict: 迁移统计信息
        """
        logger.info("开始数据迁移流程")
        
        # 检查旧数据
        if not self.check_old_data_exists():
            logger.warning("没有找到旧数据，无需迁移")
            return {"status": "skipped", "reason": "no_old_data"}
        
        # 创建备份
        backup_file = ""
        if backup_first:
            backup_file = self.create_backup()
            if not backup_file:
                logger.warning("备份创建失败，继续迁移？")
                # 这里可以添加用户确认逻辑
        
        # 迁移到SQLite
        logger.info("开始迁移到SQLite...")
        sqlite_stats = self.migrate_to_sqlite()
        
        # 迁移到Chroma
        logger.info("开始迁移到Chroma...")
        chroma_stats = self.migrate_to_chroma()
        
        # 汇总统计
        result = {
            "status": "completed",
            "backup_file": backup_file,
            "sqlite_migration": sqlite_stats,
            "chroma_migration": chroma_stats,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_memories_migrated": sqlite_stats["migrated"],
                "total_vectors_migrated": chroma_stats["migrated"],
                "total_failed": sqlite_stats["failed"] + chroma_stats["failed"],
                "total_skipped": sqlite_stats["skipped"]
            }
        }
        
        # 保存迁移报告
        self.save_migration_report(result)
        
        logger.info("数据迁移流程完成")
        return result
    
    def save_migration_report(self, report: Dict[str, Any]):
        """保存迁移报告"""
        report_dir = os.path.join(self.storage_base, "reports")
        os.makedirs(report_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(report_dir, f"migration_report_{timestamp}.json")
        
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger.info(f"迁移报告已保存: {report_file}")
        except Exception as e:
            logger.error(f"保存迁移报告失败: {e}")
    
    def verify_migration(self) -> Dict[str, Any]:
        """验证迁移结果"""
        logger.info("开始验证迁移结果...")
        
        verification = {
            "sqlite_verification": {"status": "pending", "details": {}},
            "chroma_verification": {"status": "pending", "details": {}},
            "overall_status": "pending"
        }
        
        # 验证SQLite
        try:
            from scripts.sqlite_store import SQLiteStore
            
            sqlite_store = SQLiteStore(self.new_sqlite_db)
            memory_count = sqlite_store.get_memory_count()
            sqlite_store.close()
            
            verification["sqlite_verification"] = {
                "status": "success",
                "details": {
                    "memory_count": memory_count,
                    "database_file": self.new_sqlite_db,
                    "file_exists": os.path.exists(self.new_sqlite_db)
                }
            }
            
            logger.info(f"SQLite验证成功: {memory_count} 条记忆")
            
        except Exception as e:
            verification["sqlite_verification"] = {
                "status": "failed",
                "details": {"error": str(e)}
            }
            logger.error(f"SQLite验证失败: {e}")
        
        # 验证Chroma
        try:
            from scripts.chroma_client import create_chroma_client
            
            chroma_config = {
                "persist_directory": self.new_chroma_dir,
                "collection_name": "memories"
            }
            
            chroma_client = create_chroma_client(chroma_config)
            chroma_count = chroma_client.count()
            
            verification["chroma_verification"] = {
                "status": "success",
                "details": {
                    "vector_count": chroma_count,
                    "collection_name": chroma_client.collection_name,
                    "directory_exists": os.path.exists(self.new_chroma_dir)
                }
            }
            
            logger.info(f"Chroma验证成功: {chroma_count} 个向量")
            
        except Exception as e:
            verification["chroma_verification"] = {
                "status": "failed",
                "details": {"error": str(e)}
            }
            logger.error(f"Chroma验证失败: {e}")
        
        # 总体状态
        sqlite_ok = verification["sqlite_verification"]["status"] == "success"
        chroma_ok = verification["chroma_verification"]["status"] == "success"
        
        if sqlite_ok and chroma_ok:
            verification["overall_status"] = "success"
        elif not sqlite_ok and not chroma_ok:
            verification["overall_status"] = "failed"
        else:
            verification["overall_status"] = "partial"
        
        logger.info(f"迁移验证完成: {verification['overall_status']}")
        return verification


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="迁移旧版记忆数据到SQLite + Chroma架构")
    parser.add_argument("--storage-base", default="/app/data/memory", 
                       help="存储根目录 (默认: /app/data/memory)")
    parser.add_argument("--no-backup", action="store_true", 
                       help="不创建备份（危险！）")
    parser.add_argument("--verify-only", action="store_true", 
                       help="仅验证，不执行迁移")
    parser.add_argument("--skip-verification", action="store_true", 
                       help="跳过迁移后验证")
    
    args = parser.parse_args()
    
    # 创建迁移器
    migrator = DataMigrator(args.storage_base)
    
    if args.verify_only:
        # 仅验证
        verification = migrator.verify_migration()
        print("\n=== 迁移验证结果 ===")
        print(json.dumps(verification, indent=2, ensure_ascii=False))
        return
    
    # 执行迁移
    print("\n=== 开始数据迁移 ===")
    result = migrator.run_migration(backup_first=not args.no_backup)
    
    print("\n=== 迁移统计 ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if not args.skip_verification:
        print("\n=== 开始迁移后验证 ===")
        verification = migrator.verify_migration()
        print(json.dumps(verification, indent=2, ensure_ascii=False))
    
    print("\n=== 迁移完成 ===")
    
    # 提供下一步建议
    if result.get("status") == "completed":
        print("""
下一步建议:
1. 测试新系统: 运行 test_memory_system.py 验证功能
2. 清理旧数据: 确认迁移成功后，可以删除旧文件
3. 更新配置: 确保config.yaml中启用了新架构
4. 监控运行: 观察系统性能和数据一致性
        """)
    else:
        print("迁移未完成，请检查错误信息")


if __name__ == "__main__":
    main()
