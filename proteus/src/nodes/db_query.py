"""数据库查询节点"""

from typing import Dict, Any
import aiomysql
from .base import BaseNode


class DbQueryNode(BaseNode):
    """数据库查询节点（MySQL）"""

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        host = str(params["host"])
        port = int(params.get("port", 3306))
        user = str(params["user"])
        password = str(params["password"])
        database = str(params["database"])
        query = str(params["query"])
        parameters = params.get("parameters", ())

        try:
            pool = await aiomysql.create_pool(
                host=host,
                port=port,
                user=user,
                password=password,
                db=database,
                autocommit=True,
            )

            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(query, parameters)
                    rows = await cursor.fetchall()

                    # 获取列名
                    columns = (
                        [d[0] for d in cursor.description] if cursor.description else []
                    )

                    return {
                        "result": rows,
                        "columns": columns,
                        "row_count": len(rows),
                        "query": query,
                    }

        except Exception as e:
            raise ValueError(f"数据库查询失败: {str(e)}")
        finally:
            pool.close()
            await pool.wait_closed()

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行节点并返回result字段

        Args:
            params: 节点参数

        Returns:
            Dict[str, Any]: 执行结果中的result字段（查询结果行）
        """
        result = await self.execute(params)
        return {"result": result.get("result", [])}