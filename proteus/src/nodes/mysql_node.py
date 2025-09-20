"""MySQL数据库操作节点 - 支持表schema获取和SQL执行功能"""

import os
import json
from typing import Dict, Any, Optional
import aiomysql
from .base import BaseNode
from ..api.llm_api import call_llm_api


class MysqlNode(BaseNode):
    """MySQL数据库操作节点：支持获取表schema和执行SQL两个主要功能"""

    def __init__(self):
        super().__init__()
        self.db_config = {}
        # 支持的操作类型
        self.OPERATION_TYPES = {
            "get_schema": "获取表结构信息",
            "execute_sql": "执行SQL语句",
            "nlp_query": "自然语言查询（原有功能）",
        }

    async def _load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """加载数据库配置

        Args:
            config_path: 配置文件路径（已废弃，仅保留兼容性）

        Returns:
            数据库配置字典
        """
        # 直接从环境变量读取配置
        config = {
            "host": os.getenv("MYSQL_HOST"),
            "port": int(os.getenv("MYSQL_PORT", "3306")),
            "user": os.getenv("MYSQL_USER"),
            "password": os.getenv("MYSQL_PASSWORD"),
            "database": os.getenv("MYSQL_DATABASE"),
        }

        return config

    async def _get_table_schema(self, pool) -> str:
        """获取数据库表结构信息 - 优化版本，自动获取所有相关表信息

        Args:
            pool: 数据库连接池
            table_hint: 可选的表名提示（保持向后兼容）

        Returns:
            表结构信息字符串
        """
        schema_info = []

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # 获取所有表名
                await cursor.execute("SHOW TABLES")
                tables = await cursor.fetchall()

                table_list = [table[0] for table in tables]

                for table_name in table_list:
                    await cursor.execute(f"DESCRIBE `{table_name}`")
                    columns = await cursor.fetchall()

                    schema_info.append(f"表名: {table_name}")
                    for col in columns:
                        field, type_, null, key, default, extra = col
                        key_info = ""
                        if key == "PRI":
                            key_info = " (主键)"
                        elif key == "UNI":
                            key_info = " (唯一键)"
                        elif key == "MUL":
                            key_info = " (索引)"

                        null_info = " (可为空)" if null == "YES" else " (不可为空)"
                        schema_info.append(f"  - {field}: {type_}{key_info}{null_info}")

                    # 获取表的注释信息
                    await cursor.execute(f"SHOW TABLE STATUS LIKE '{table_name}'")
                    table_status = await cursor.fetchone()
                    if table_status and table_status[17]:  # Comment字段
                        schema_info.append(f"  表注释: {table_status[17]}")

                    schema_info.append("")

        return "\n".join(schema_info)

    async def _generate_sql(
        self, question: str, schema_info: str, table_hint: Optional[str] = None
    ) -> str:
        """使用 LLM 将自然语言转换为 SQL - 优化版本，智能分析问题和表结构

        Args:
            question: 自然语言问题
            schema_info: 数据库表结构信息
            table_hint: 可选的表名提示（保持向后兼容）

        Returns:
            生成的 SQL 语句
        """
        system_prompt = f"""你是一个专业的 SQL 生成助手。根据用户的自然语言问题和数据库表结构，生成准确的 SQL 查询语句。

数据库表结构信息：
{schema_info}

要求：
1. 只返回 SQL 语句，不要包含任何解释或其他文本
2. 使用标准的 MySQL 语法
3. 对于 SELECT 查询，请添加 LIMIT 子句限制结果数量（默认50条）
4. 确保 SQL 语句语法正确
5. 使用反引号包围表名和列名以避免关键字冲突
6. 如果问题涉及模糊匹配，使用 LIKE 操作符和通配符 %
7. 如果问题涉及统计，使用适当的聚合函数（COUNT, SUM, AVG, MAX, MIN）
8. 智能分析问题中的关键词，选择最相关的表和字段
9. 如果需要多表查询，使用适当的 JOIN 语句
10. 对于时间相关查询，使用适当的日期函数
11. 注意字段的数据类型，使用正确的比较操作
{f'12. 优先考虑使用表: {table_hint}' if table_hint else ''}

示例：
用户问题：查询所有用户信息
SQL：SELECT * FROM `users` LIMIT 50;

用户问题：统计订单总数
SQL：SELECT COUNT(*) as total_orders FROM `orders`;

用户问题：查询最近一周的订单
SQL：SELECT * FROM `orders` WHERE `created_at` >= DATE_SUB(NOW(), INTERVAL 7 DAY) LIMIT 50;

用户问题：查询用户名包含"张"的用户
SQL：SELECT * FROM `users` WHERE `name` LIKE '%张%' LIMIT 50;
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请为以下问题生成 SQL 语句：{question}"},
        ]

        try:
            response, _ = await call_llm_api(messages, temperature=0.1)
            # 清理响应，移除可能的代码块标记
            sql = response.strip()
            if sql.startswith("```sql"):
                sql = sql[6:]
            if sql.startswith("```"):
                sql = sql[3:]
            if sql.endswith("```"):
                sql = sql[:-3]
            sql = sql.strip()

            return sql
        except Exception as e:
            raise ValueError(f"SQL 生成失败: {str(e)}")

    async def _execute_sql(self, pool, sql: str, top_k: int = 50) -> Dict[str, Any]:
        """执行 SQL 语句

        Args:
            pool: 数据库连接池
            sql: SQL 语句
            top_k: 最大返回行数

        Returns:
            执行结果
        """
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 如果是 SELECT 语句且没有 LIMIT，添加 LIMIT
                sql_upper = sql.upper().strip()
                if sql_upper.startswith("SELECT") and "LIMIT" not in sql_upper:
                    sql = f"{sql.rstrip(';')} LIMIT {top_k}"

                await cursor.execute(sql)

                if sql_upper.startswith("SELECT"):
                    # 查询语句
                    rows = await cursor.fetchall()
                    columns = (
                        [d[0] for d in cursor.description] if cursor.description else []
                    )
                    return {
                        "type": "query",
                        "data": rows,
                        "columns": columns,
                        "row_count": len(rows),
                    }
                else:
                    # 执行语句（INSERT, UPDATE, DELETE 等）
                    affected_rows = cursor.rowcount
                    return {
                        "type": "execute",
                        "affected_rows": affected_rows,
                        "data": None,
                    }

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行节点 - 支持多种操作类型

        Args:
            params: 节点参数，必须包含 "operation" 字段指定操作类型:
                - "get_schema": 获取表结构信息
                - "execute_sql": 直接执行SQL语句
                - "nlp_query": 自然语言查询（原有功能，默认）

        Returns:
            执行结果
        """
        operation = params.get("operation", "nlp_query")

        # 验证操作类型
        if operation not in self.OPERATION_TYPES:
            raise ValueError(
                f"不支持的操作类型: {operation}. 支持的操作类型: {list(self.OPERATION_TYPES.keys())}"
            )

        # 根据操作类型调用相应的方法
        if operation == "get_schema":
            return await self.get_table_schema(params)
        elif operation == "execute_sql":
            return await self.execute_sql_directly(params)
        elif operation == "nlp_query":
            return await self._execute_nlp_query(params)
        else:
            raise ValueError(f"未实现的操作类型: {operation}")

    async def _execute_nlp_query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行自然语言查询（原有功能）

        Args:
            params: 节点参数，必须包含 "question" 字段

        Returns:
            执行结果
        """
        # 只需要用户问题
        question = str(params["question"])

        # 可选参数，保持向后兼容
        top_k = int(params.get("top_k", 50))

        # 自动从环境变量获取数据库配置
        config = await self._load_config()

        # 验证必需的配置
        required_fields = ["host", "user", "password", "database"]
        missing_fields = [field for field in required_fields if not config.get(field)]
        if missing_fields:
            raise ValueError(
                f"缺少必需的数据库配置环境变量: {', '.join(missing_fields)}"
            )

        pool = None
        sql = None
        execution_result = None
        try:
            # 创建数据库连接池
            pool = await aiomysql.create_pool(
                host=config["host"],
                port=config["port"],
                user=config["user"],
                password=config["password"],
                db=config["database"],
                autocommit=True,
                maxsize=5,
                minsize=1,
            )

            # 自动获取所有表结构信息（不需要table_hint）
            schema_info = await self._get_table_schema(pool)

            # 基于问题和表信息生成 SQL
            sql = await self._generate_sql(question, schema_info)

            # 执行 SQL
            execution_result = await self._execute_sql(pool, sql, top_k)

            # 构建返回结果
            result = {
                "operation": "nlp_query",
                "question": question,
                "generated_sql": sql,
                "execution_result": execution_result,
                "success": True,
            }

            return {"result": result}

        except Exception as e:
            error_result = {
                "operation": "nlp_query",
                "question": question,
                "generated_sql": sql,
                "execution_result": execution_result,
                "success": False,
                "error": str(e),
            }
            return {"result": error_result}

        finally:
            if pool:
                pool.close()
                await pool.wait_closed()

    async def get_table_schema(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取数据库表结构信息

        Args:
            params: 参数字典，可包含:
                - table_name: 可选，指定表名，如果不提供则返回所有表的schema
                - database: 可选，指定数据库名，如果不提供则使用配置中的默认数据库

        Returns:
            包含表结构信息的字典
        """
        table_name = params.get("table_name")
        database = params.get("database")

        # 获取数据库配置
        config = await self._load_config()
        if database:
            config["database"] = database

        # 验证必需的配置
        required_fields = ["host", "user", "password", "database"]
        missing_fields = [field for field in required_fields if not config.get(field)]
        if missing_fields:
            raise ValueError(
                f"缺少必需的数据库配置环境变量: {', '.join(missing_fields)}"
            )

        pool = None
        try:
            # 创建数据库连接池
            pool = await aiomysql.create_pool(
                host=config["host"],
                port=config["port"],
                user=config["user"],
                password=config["password"],
                db=config["database"],
                autocommit=True,
                maxsize=5,
                minsize=1,
            )

            # 获取表结构信息
            schema_info = await self._get_table_schema(pool, table_name)

            result = {
                "operation": "get_schema",
                "database": config["database"],
                "table_name": table_name,
                "schema_info": schema_info,
                "success": True,
            }

            return {"result": result}

        except Exception as e:
            error_result = {
                "operation": "get_schema",
                "database": config.get("database"),
                "table_name": table_name,
                "schema_info": None,
                "success": False,
                "error": str(e),
            }
            return {"result": error_result}

        finally:
            if pool:
                pool.close()
                await pool.wait_closed()

    async def execute_sql_directly(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """直接执行SQL语句

        Args:
            params: 参数字典，必须包含:
                - sql: 要执行的SQL语句
                - top_k: 可选，查询结果的最大行数，默认50
                - database: 可选，指定数据库名，如果不提供则使用配置中的默认数据库

        Returns:
            SQL执行结果
        """
        sql = params.get("sql")
        if not sql:
            raise ValueError("缺少必需参数: sql")

        top_k = int(params.get("top_k", 50))
        database = params.get("database")

        # 获取数据库配置
        config = await self._load_config()
        if database:
            config["database"] = database

        # 验证必需的配置
        required_fields = ["host", "user", "password", "database"]
        missing_fields = [field for field in required_fields if not config.get(field)]
        if missing_fields:
            raise ValueError(
                f"缺少必需的数据库配置环境变量: {', '.join(missing_fields)}"
            )

        pool = None
        try:
            # 创建数据库连接池
            pool = await aiomysql.create_pool(
                host=config["host"],
                port=config["port"],
                user=config["user"],
                password=config["password"],
                db=config["database"],
                autocommit=True,
                maxsize=5,
                minsize=1,
            )

            # 执行SQL
            execution_result = await self._execute_sql(pool, sql, top_k)

            result = {
                "operation": "execute_sql",
                "database": config["database"],
                "sql": sql,
                "execution_result": execution_result,
                "success": True,
            }

            return {"result": result}

        except Exception as e:
            error_result = {
                "operation": "execute_sql",
                "database": config.get("database"),
                "sql": sql,
                "execution_result": None,
                "success": False,
                "error": str(e),
            }
            return {"result": error_result}

        finally:
            if pool:
                pool.close()
                await pool.wait_closed()

    async def simple_execute(self, question: str) -> Dict[str, Any]:
        """简化的执行方法，只需要问题参数（自然语言查询）

        Args:
            question: 用户的自然语言问题

        Returns:
            执行结果
        """
        return await self.execute({"operation": "nlp_query", "question": question})

    async def simple_get_schema(
        self, table_name: str = None, database: str = None
    ) -> Dict[str, Any]:
        """简化的获取表结构方法

        Args:
            table_name: 可选，指定表名
            database: 可选，指定数据库名

        Returns:
            表结构信息
        """
        params = {"operation": "get_schema"}
        if table_name:
            params["table_name"] = table_name
        if database:
            params["database"] = database
        return await self.execute(params)

    async def simple_execute_sql(
        self, sql: str, top_k: int = 50, database: str = None
    ) -> Dict[str, Any]:
        """简化的SQL执行方法

        Args:
            sql: 要执行的SQL语句
            top_k: 查询结果的最大行数，默认50
            database: 可选，指定数据库名

        Returns:
            SQL执行结果
        """
        params = {"operation": "execute_sql", "sql": sql, "top_k": top_k}
        if database:
            params["database"] = database
        return await self.execute(params)

    def get_supported_operations(self) -> Dict[str, str]:
        """获取支持的操作类型

        Returns:
            操作类型字典
        """
        return self.OPERATION_TYPES.copy()

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """智能体调用节点

        Args:
            params: 节点参数，必须包含operation字段指定操作类型

        Returns:
            执行结果中的result字段
        """
        result = await self.execute(params)
        return {"result": result.get("result", {})}
