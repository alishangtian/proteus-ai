"""数据库执行节点"""

from typing import Dict, Any
import aiomysql
from .base import BaseNode

class DbExecuteNode(BaseNode):
    """数据库执行节点（MySQL）- 用于INSERT/UPDATE/DELETE等操作"""
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        host = str(params["host"])
        port = int(params.get("port", 3306))
        user = str(params["user"])
        password = str(params["password"])
        database = str(params["database"])
        statement = str(params["statement"])
        parameters = params.get("parameters", ())
        auto_commit = bool(params.get("auto_commit", True))
        
        try:
            pool = await aiomysql.create_pool(
                host=host,
                port=port,
                user=user,
                password=password,
                db=database,
                autocommit=auto_commit
            )
            
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(statement, parameters)
                    
                    if not auto_commit:
                        await conn.commit()
                        
                    return {
                        "result": "success",
                        "rows_affected": cursor.rowcount,
                        "last_row_id": cursor.lastrowid,
                        "statement": statement
                    }
                    
        except Exception as e:
            if not auto_commit and 'conn' in locals():
                await conn.rollback()
            raise ValueError(f"数据库执行失败: {str(e)}")
        finally:
            pool.close()
            await pool.wait_closed()
            
    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行节点并将结果转换为统一格式
        
        将数据库执行结果转换为包含操作状态、影响行数等信息的文本。
        
        Args:
            params: 节点参数
            
        Returns:
            Dict[str, Any]: 执行结果，包含纯文本格式的'result'键
        """
        try:
            execute_result = await self.execute(params)
            
            # 组织执行结果信息
            result_text = (
                f"Database operation executed successfully:\n"
                f"- Database: {params['database']}\n"
                f"- Statement: {execute_result['statement']}\n"
                f"- Rows affected: {execute_result['rows_affected']}\n"
                f"- Last inserted ID: {execute_result['last_row_id'] if execute_result['last_row_id'] else 'N/A'}\n"
                f"- Auto commit: {params.get('auto_commit', True)}"
            )
            
            return {
                "result": result_text
            }
        except Exception as e:
            return {
                "result": f"Error: {str(e)}",
                "error": str(e)
            }
