from typing import Dict, Any, Optional, List
import logging
import json
import uuid
from datetime import datetime
import time

from src.api.llm_api import call_llm_api
from src.agent.prompt.sop_memory_prompt import SOP_MEMORY_ANALYSIS_PROMPT
from src.utils.chrome_vector_db import ChromeVectorDB
from src.utils.ollama_embedding import get_embedding_model

logger = logging.getLogger(__name__)


class SopMemoryManager:
    """标准操作流程（SOP）记忆管理器，使用 Chrome 向量数据库和 Ollama bge-m3 嵌入模型

    主要功能：
    - 分析用户问题、工具调用链、最终结果，提取标准解题经验
    - 将SOP记忆存储到Chrome向量数据库
    - 使用向量相似性搜索检索相关SOP记忆
    - 支持基于问题类型的SOP检索
    """

    def __init__(
        self,
        vector_db: Optional[ChromeVectorDB] = None,
        ollama_url: str = "http://127.0.0.1:11434",
    ):
        """初始化SOP记忆管理器

        Args:
            vector_db: Chrome向量数据库实例，如果为None则创建默认实例
            ollama_url: Ollama服务地址
        """
        self.vector_db = vector_db or ChromeVectorDB(ollama_url=ollama_url)
        self.embedding_model = get_embedding_model(base_url=ollama_url)
        self.collection_name = "sop_memories"

        # 测试连接和嵌入函数
        if not self.embedding_model.test_connection():
            logger.warning("Ollama 服务连接失败，嵌入功能可能不可用")
        else:
            # 测试嵌入函数
            if not self.vector_db.test_embedding_function():
                logger.warning("嵌入函数测试失败，向量搜索可能不可用")

        # 多级召回配置
        self.first_stage_candidates = 20  # 第一级召回候选数量
        self.second_stage_results = 5  # 第二级召回最终结果数量
        self.similarity_threshold = 0.4  # 相似度阈值

    async def analyze_problem_solution(
        self,
        user_query: str,
        tool_chain: List[Dict[str, Any]],
        final_result: str,
        problem_type: Optional[str] = None,
        is_success: bool = True,
        old_sop_memory: Optional[str] = None,
        model_name: str = None,
    ) -> str:
        """
        调用LLM分析问题解决过程，提取标准解题经验（限800字符）。
        关注问题类型、工具调用链、最终结果的完整关系。

        Args:
            user_query: 用户原始问题
            tool_chain: 工具调用链，包含工具名称和输入参数
            final_result: 最终解决结果
            problem_type: 问题类型（可选，可自动识别）
            is_success: 是否成功解决
            old_sop_memory: 历史SOP记忆
            model_name: 使用的模型名称

        Returns:
            str: 标准解题经验
        """
        # 构建上下文信息
        context_info = ""
        resolution_status = "成功" if is_success else "失败"

        if old_sop_memory:
            context_info += f"- 历史SOP: {old_sop_memory}\n"

        # 格式化工具调用链信息
        tool_chain_info = []
        for i, tool_call in enumerate(tool_chain, 1):
            tool_name = tool_call.get("tool_name", "未知工具")
            action_input = tool_call.get("action_input", {})
            tool_chain_info.append(
                f"步骤{i}: {tool_name} - 输入: {json.dumps(action_input, ensure_ascii=False)}"
            )

        tool_chain_str = "\n".join(tool_chain_info)

        # 如果未提供问题类型，尝试自动识别
        if not problem_type:
            problem_type = await self._infer_problem_type(user_query, tool_chain)

        # 使用SOP记忆分析提示词模板
        prompt = SOP_MEMORY_ANALYSIS_PROMPT.format(
            user_query=user_query,
            problem_type=problem_type,
            tool_chain=tool_chain_str,
            final_result=final_result,
            resolution_status=resolution_status,
            context_info=context_info,
        )

        if not model_name:
            logger.error("没有可用的模型进行SOP分析")
            return ""

        try:
            model_response = await call_llm_api(
                [{"role": "user", "content": prompt}], model_name=model_name
            )

            if isinstance(model_response, tuple) and len(model_response) == 2:
                extracted_text = model_response[0]
            else:
                extracted_text = model_response

            # 清理并限制长度
            result = extracted_text.strip()
            # 移除可能的markdown标记
            result = result.replace("```", "").replace("**", "").strip()

            logger.info(
                f"问题类型 '{problem_type}' ({resolution_status}) SOP经验({len(result)}字符): {result}"
            )
            return result
        except Exception as e:
            logger.error(f"调用LLM分析问题解决过程时发生错误: {e}", exc_info=True)
            return ""

    async def _infer_problem_type(
        self, user_query: str, tool_chain: List[Dict[str, Any]]
    ) -> str:
        """
        使用模型根据用户查询和工具调用链智能推断问题类型

        Args:
            user_query: 用户原始问题
            tool_chain: 工具调用链

        Returns:
            str: 推断的问题类型
        """
        try:
            # 如果工具链为空，使用基于用户查询的推断
            if not tool_chain:
                return await self._infer_problem_type_from_query(user_query)

            # 使用模型进行智能推断
            return await self._infer_problem_type_with_model(user_query, tool_chain)

        except Exception as e:
            logger.warning(f"使用模型推断问题类型失败，降级到基于工具的推断: {e}")
            # 降级到基于工具的推断
            return await self._infer_problem_type_from_tools(tool_chain)

    async def _infer_problem_type_from_query(self, user_query: str) -> str:
        """
        仅基于用户查询推断问题类型
        """
        # 常见问题类型的关键词映射
        query_keywords = {
            "信息检索类问题": [
                "搜索",
                "查找",
                "查询",
                "获取",
                "了解",
                "什么是",
                "如何",
                "怎样",
            ],
            "文件操作类问题": [
                "文件",
                "读取",
                "写入",
                "创建",
                "删除",
                "修改",
                "保存",
                "打开",
            ],
            "数据分析类问题": ["分析", "计算", "统计", "处理", "汇总", "图表", "趋势"],
            "网络操作类问题": ["网页", "网站", "链接", "下载", "访问", "爬取", "网络"],
            "代码相关类问题": ["代码", "编程", "函数", "类", "方法", "变量", "调试"],
            "配置管理类问题": ["配置", "设置", "参数", "选项", "环境", "系统"],
            "数据处理类问题": ["数据", "数据库", "表格", "记录", "导入", "导出"],
        }

        user_query_lower = user_query.lower()
        for problem_type, keywords in query_keywords.items():
            if any(keyword in user_query_lower for keyword in keywords):
                return problem_type

        return "通用问题"

    async def _infer_problem_type_from_tools(
        self, tool_chain: List[Dict[str, Any]]
    ) -> str:
        """
        基于工具调用链推断问题类型（降级方法）
        """
        tool_names = [tool.get("tool_name", "").lower() for tool in tool_chain]

        # 基于工具名称推断问题类型
        if any("search" in name or "query" in name for name in tool_names):
            return "信息检索类问题"
        elif any(
            "file" in name or "read" in name or "write" in name for name in tool_names
        ):
            return "文件操作类问题"
        elif any(
            "calculate" in name or "analyze" in name or "process" in name
            for name in tool_names
        ):
            return "数据分析类问题"
        elif any("web" in name or "browser" in name for name in tool_names):
            return "网络操作类问题"
        elif any("code" in name or "program" in name for name in tool_names):
            return "代码相关类问题"
        elif any("config" in name or "setting" in name for name in tool_names):
            return "配置管理类问题"
        else:
            return "通用问题"

    async def _infer_problem_type_with_model(
        self, user_query: str, tool_chain: List[Dict[str, Any]]
    ) -> str:
        """
        使用LLM模型智能推断问题类型
        """
        # 构建工具调用链信息
        tool_chain_info = []
        for i, tool_call in enumerate(tool_chain, 1):
            tool_name = tool_call.get("tool_name", "未知工具")
            action_input = tool_call.get("action_input", {})
            tool_chain_info.append(
                f"步骤{i}: {tool_name} - 输入: {json.dumps(action_input, ensure_ascii=False)}"
            )

        tool_chain_str = "\n".join(tool_chain_info)

        # 使用预定义的问题类型推断提示词模板
        from src.agent.prompt.sop_memory_prompt import PROBLEM_TYPE_INFERENCE_PROMPT

        prompt = PROBLEM_TYPE_INFERENCE_PROMPT.format(
            user_query=user_query, tool_chain=tool_chain_str
        )

        try:
            # 使用默认模型进行推断
            model_response = await call_llm_api(
                [{"role": "user", "content": prompt}], model_name="deepseek-chat"
            )

            if isinstance(model_response, tuple) and len(model_response) == 2:
                problem_type = model_response[0].strip()
            else:
                problem_type = model_response.strip()

            # 验证问题类型是否在预定义范围内
            valid_types = [
                "信息检索类问题",
                "文件操作类问题",
                "数据分析类问题",
                "网络操作类问题",
                "代码相关类问题",
                "配置管理类问题",
                "数据处理类问题",
                "通用问题",
            ]

            if problem_type in valid_types:
                logger.info(f"模型推断问题类型: {problem_type}")
                return problem_type
            else:
                logger.warning(
                    f"模型返回的问题类型不在预定义范围内: {problem_type}，使用基于工具的推断"
                )
                return await self._infer_problem_type_from_tools(tool_chain)

        except Exception as e:
            logger.error(f"使用模型推断问题类型时发生错误: {e}")
            raise

    async def save_sop_memory(
        self,
        problem_type: str,
        sop_experience: str,
        user_query: str,
        tool_chain: List[Dict[str, Any]],
        final_result: str,
        user_name: str = None,
    ) -> str:
        """
        将SOP记忆存储到Chrome向量数据库中。

        Args:
            problem_type: 问题类型
            sop_experience: SOP经验内容
            user_query: 用户原始问题
            tool_chain: 工具调用链
            final_result: 最终结果
            user_name: 用户名，用于用户隔离

        Returns:
            str: 存储的文档ID
        """
        try:
            # 构建文档内容用于嵌入（分离 title 与 content 两个条目，便于对标题和正文分别召回）
            document_content = f"""
问题类型: {problem_type}
用户问题: {user_query}
SOP经验: {sop_experience}
工具链: {len(tool_chain)} 个工具
最终结果: {final_result}
            """.strip()
 
            # 生成基础文档ID（用于关联 title 与 content）
            base_id = str(uuid.uuid4())
            title_id = f"{base_id}_title"
            content_id = f"{base_id}_content"
 
            # 构建 title 文档和 content 文档
            # title 保持简短，方便标题匹配；content 存放完整内容以供精排
            title_text = f"{problem_type} | {sop_experience[:120].strip()}"
            content_text = document_content
 
            # 构建元数据（分别为 title/content 提供方便的字段）
            common_metadata = {
                "problem_type": problem_type,
                "user_query": user_query,  # 限制长度
                "tool_count": len(tool_chain),
                "final_result_preview": final_result,  # 限制长度
                "user_name": user_name or "global",
                "created_at": datetime.now().isoformat(),
                "parent_id": base_id,
            }
 
            title_metadata = common_metadata.copy()
            title_metadata.update({"is_title": True, "sop_experience": sop_experience[:200], "title": title_text})
 
            content_metadata = common_metadata.copy()
            content_metadata.update({"is_title": False, "sop_experience": sop_experience})
 
            # 存储到向量数据库：先存标题（便于标题召回），再存正文
            self.vector_db.add_documents(
                collection_name=self.collection_name,
                documents=[title_text, content_text],
                metadatas=[title_metadata, content_metadata],
                ids=[title_id, content_id],
            )

            logger.info(
                f"成功保存问题类型 '{problem_type}' 的SOP记忆到向量数据库 (user: {user_name or 'global'})"
            )
            # 返回 base_id，作为这条 SOP 的唯一标识（title/content 共用）
            return base_id
        except Exception as e:
            logger.error(
                f"保存问题类型 '{problem_type}' 的SOP记忆到向量数据库失败: {e}",
                exc_info=True,
            )
            raise

    async def search_sop_memories(
        self,
        query: str,
        n_results: int = 5,
        problem_type: Optional[str] = None,
        user_name: str = None,
        use_multi_stage: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        使用向量相似性搜索检索相关的SOP记忆。

        Args:
            query: 搜索查询
            n_results: 返回结果数量
            problem_type: 过滤问题类型
            user_name: 用户名，用于用户隔离
            use_multi_stage: 是否使用多级召回

        Returns:
            List[Dict]: 匹配的SOP记忆列表
        """
        try:
            if use_multi_stage:
                # 使用多级召回
                return await self.multi_stage_search_sop_memories(
                    query=query,
                    n_results=n_results,
                    problem_type=problem_type,
                    user_name=user_name,
                )
            else:
                # 使用传统单级召回
                # 构建过滤条件
                where_filter = {}
                if problem_type:
                    where_filter["problem_type"] = problem_type
                if user_name:
                    where_filter["user_name"] = user_name

                # 执行向量搜索（会自动调用嵌入模型为查询文本生成向量）
                results = self.vector_db.query(
                    collection_name=self.collection_name,
                    query_texts=[query],
                    n_results=n_results,
                    where=where_filter if where_filter else None,
                )

                # 格式化返回结果
                formatted_results = []
                for i in range(len(results["documents"][0])):
                    distance = results["distances"][0][i]
                    similarity_score = 1.0 - distance if distance <= 1.0 else 0.0

                    formatted_results.append(
                        {
                            "document": results["documents"][0][i],
                            "metadata": results["metadatas"][0][i],
                            "distance": distance,
                            "similarity_score": similarity_score,
                            "id": results["ids"][0][i],
                            "recall_stage": "single_stage",
                        }
                    )

                logger.info(
                    f"单级搜索查询 '{query}' 返回 {len(formatted_results)} 个相关SOP记忆"
                )
                return formatted_results
        except Exception as e:
            logger.error(f"搜索SOP记忆失败: {e}", exc_info=True)
            return []

    async def load_sop_memory_by_type(
        self, problem_type: str, user_name: str = None, n_results: int = 3
    ) -> List[Dict[str, Any]]:
        """
        根据问题类型加载相关的SOP记忆。

        Args:
            problem_type: 问题类型
            user_name: 用户名
            n_results: 返回结果数量

        Returns:
            List[Dict]: 相关SOP记忆列表
        """
        return await self.search_sop_memories(
            query=problem_type,
            n_results=n_results,
            problem_type=problem_type,
            user_name=user_name,
        )

    async def first_stage_recall(
        self,
        query: str,
        n_candidates: int = None,
        problem_type: Optional[str] = None,
        user_name: str = None,
    ) -> List[Dict[str, Any]]:
        """
        第一级召回：基于用户问题的快速相似度匹配

        Args:
            query: 用户查询文本
            n_candidates: 候选数量，如果为None则使用默认值
            problem_type: 过滤问题类型
            user_name: 用户名，用于用户隔离

        Returns:
            List[Dict]: 第一级召回候选结果
        """
        try:
            start_time = time.time()

            # 构建过滤条件
            where_filter = {}
            if problem_type:
                where_filter["problem_type"] = problem_type
            if user_name:
                where_filter["user_name"] = user_name

            # 第一级召回：基于用户问题字段的快速匹配
            # 这里我们使用用户查询与存储的用户问题字段进行相似度匹配
            results = self.vector_db.query(
                collection_name=self.collection_name,
                query_texts=[query],
                n_results=n_candidates or self.first_stage_candidates,
                where=where_filter if where_filter else None,
            )

            # 格式化返回结果
            formatted_results = []
            for i in range(len(results["documents"][0])):
                metadata = results["metadatas"][0][i]
                distance = results["distances"][0][i]

                # 计算相似度分数（距离转换为相似度）
                similarity_score = 1.0 - distance if distance <= 1.0 else 0.0

                formatted_results.append(
                    {
                        "document": results["documents"][0][i],
                        "metadata": metadata,
                        "distance": distance,
                        "similarity_score": similarity_score,
                        "id": results["ids"][0][i],
                        "recall_stage": "first_stage",
                    }
                )

            elapsed_time = time.time() - start_time
            logger.info(
                f"第一级召回完成: 查询 '{query}' 返回 {len(formatted_results)} 个候选结果，耗时 {elapsed_time:.3f}s"
            )
            return formatted_results
        except Exception as e:
            logger.error(f"第一级召回失败: {e}", exc_info=True)
            return []

    async def second_stage_recall(
        self,
        query: str,
        first_stage_candidates: List[Dict[str, Any]],
        n_results: int = None,
    ) -> List[Dict[str, Any]]:
        """
        第二级召回：基于完整SOP内容的精确相似度匹配

        Args:
            query: 用户查询文本
            first_stage_candidates: 第一级召回候选结果
            n_results: 最终结果数量，如果为None则使用默认值

        Returns:
            List[Dict]: 第二级召回最终结果
        """
        try:
            start_time = time.time()

            if not first_stage_candidates:
                logger.info("第二级召回：第一级召回无候选结果，直接返回空列表")
                return []

            # 提取第一级候选的ID
            candidate_ids = [candidate["id"] for candidate in first_stage_candidates]

            # 构建用于第二级精排的查询文本：使用原始用户 query（简洁语义），
            # 第二级会使用 ids 限制候选集合，因此这里保留原始 query 更有利于命中候选
            sop_query_text = query.strip()

            # 第二级召回：基于完整SOP内容进行精确匹配
            # 这里我们使用包含完整上下文的查询文本
            # 使用 ids 限制搜索范围（比使用 where 对 id 的过滤更兼容 ChromaDB）
            results = self.vector_db.query(
                collection_name=self.collection_name,
                query_texts=[sop_query_text],
                n_results=n_results or self.second_stage_results,
                where=None,
                ids=candidate_ids if candidate_ids else None,
            )

            # 格式化返回结果并计算综合分数
            final_results = []
            for i in range(len(results["documents"][0])):
                metadata = results["metadatas"][0][i]
                distance = results["distances"][0][i]

                # 计算第二级相似度分数
                second_stage_similarity = 1.0 - distance if distance <= 1.0 else 0.0

                # 查找对应的第一级召回结果
                first_stage_result = next(
                    (
                        candidate
                        for candidate in first_stage_candidates
                        if candidate["id"] == results["ids"][0][i]
                    ),
                    None,
                )

                # 计算综合分数（第一级和第二级的加权平均）
                first_stage_score = (
                    first_stage_result["similarity_score"]
                    if first_stage_result
                    else 0.0
                )
                combined_score = first_stage_score * 0.4 + second_stage_similarity * 0.6

                final_results.append(
                    {
                        "document": results["documents"][0][i],
                        "metadata": metadata,
                        "distance": distance,
                        "similarity_score": combined_score,
                        "first_stage_score": first_stage_score,
                        "second_stage_score": second_stage_similarity,
                        "id": results["ids"][0][i],
                        "recall_stage": "second_stage",
                    }
                )

            # 按综合分数排序
            final_results.sort(key=lambda x: x["similarity_score"], reverse=True)

            elapsed_time = time.time() - start_time
            logger.info(
                f"第二级召回完成: 从 {len(first_stage_candidates)} 个候选筛选出 {len(final_results)} 个最终结果，耗时 {elapsed_time:.3f}s"
            )
            return final_results
        except Exception as e:
            logger.error(f"第二级召回失败: {e}", exc_info=True)
            return []

    async def multi_stage_search_sop_memories(
        self,
        query: str,
        n_results: int = None,
        problem_type: Optional[str] = None,
        user_name: str = None,
    ) -> List[Dict[str, Any]]:
        """
        多级召回搜索：第一级问题相似度召回 + 第二级完整SOP相似度召回

        Args:
            query: 搜索查询
            n_results: 返回结果数量
            problem_type: 过滤问题类型
            user_name: 用户名，用于用户隔离

        Returns:
            List[Dict]: 匹配的SOP记忆列表
        """
        try:
            start_time = time.time()
            logger.info(f"开始多级召回搜索: '{query}'")

            # 第一级召回：基于用户问题的快速相似度匹配
            first_stage_results = await self.first_stage_recall(
                query=query,
                n_candidates=self.first_stage_candidates,
                problem_type=problem_type,
                user_name=user_name,
            )

            # 过滤低相似度的候选结果
            filtered_candidates = [
                candidate
                for candidate in first_stage_results
                if candidate["similarity_score"] >= self.similarity_threshold
            ]

            if not filtered_candidates:
                logger.info("多级召回：第一级召回无符合条件的候选结果")
                return []

            # 第二级召回：基于完整SOP内容的精确相似度匹配
            second_stage_results = await self.second_stage_recall(
                query=query,
                first_stage_candidates=filtered_candidates,
                n_results=n_results or self.second_stage_results,
            )

            elapsed_time = time.time() - start_time
            logger.info(
                f"多级召回搜索完成: 查询 '{query}' 返回 {len(second_stage_results)} 个最终结果，总耗时 {elapsed_time:.3f}s"
            )

            return second_stage_results
        except Exception as e:
            logger.error(f"多级召回搜索失败: {e}", exc_info=True)
            # 降级到单级召回
            return await self.search_sop_memories(
                query=query,
                n_results=n_results or self.second_stage_results,
                problem_type=problem_type,
                user_name=user_name,
            )

    async def process_sop_memory(
        self,
        user_query: str,
        tool_chain: List[Dict[str, Any]],
        final_result: str,
        problem_type: Optional[str] = None,
        is_success: bool = True,
        user_name: str = None,
        model_name: str = None,
    ) -> Optional[str]:
        """
        异步处理SOP记忆提取和保存。
        从成功的问题解决过程中提取标准解题经验，用于优化后续同类问题的解决。

        Args:
            user_query: 用户原始问题
            tool_chain: 工具调用链
            final_result: 最终解决结果
            problem_type: 问题类型（可选，可自动识别）
            is_success: 是否成功解决
            user_name: 用户名，用于记忆隔离
            model_name: 使用的模型名称

        Returns:
            Optional[str]: 生成的SOP经验
        """
        try:
            resolution_status = "成功" if is_success else "失败"
            logger.info(
                f"开始处理问题类型 '{problem_type or '待识别'}' 的SOP记忆提取 (状态: {resolution_status})"
            )

            # 如果未提供问题类型，自动识别
            if not problem_type:
                problem_type = await self._infer_problem_type(user_query, tool_chain)

            # 只在成功解决时提取SOP经验
            sop_experience = ""
            if is_success:
                # 搜索相关的历史SOP记忆
                related_memories = await self.load_sop_memory_by_type(
                    problem_type, user_name
                )
                old_sop_memory = None
                if related_memories:
                    # 使用最相关的历史记忆作为参考
                    old_sop_memory = related_memories[0]["metadata"].get(
                        "sop_experience"
                    )

                sop_experience = await self.analyze_problem_solution(
                    user_query=user_query,
                    tool_chain=tool_chain,
                    final_result=final_result,
                    problem_type=problem_type,
                    is_success=is_success,
                    old_sop_memory=old_sop_memory,
                    model_name=model_name,
                )

            # 保存SOP经验到向量数据库
            if sop_experience and sop_experience.strip():
                await self.save_sop_memory(
                    problem_type=problem_type,
                    sop_experience=sop_experience,
                    user_query=user_query,
                    tool_chain=tool_chain,
                    final_result=final_result,
                    user_name=user_name,
                )
                logger.info(
                    f"问题类型 '{problem_type}' ({resolution_status}) SOP经验已更新: {sop_experience[:100]}..."
                )
            else:
                logger.info(
                    f"问题类型 '{problem_type}' ({resolution_status}) 未生成新的SOP经验"
                )
            return sop_experience
        except Exception as e:
            logger.error(
                f"处理问题类型 '{problem_type}' 的SOP记忆失败: {e}", exc_info=True
            )
            return None

    async def get_all_sop_memories(self, user_name: str = None) -> List[Dict[str, Any]]:
        """
        获取所有SOP记忆（通过搜索空查询实现）。

        Args:
            user_name: 用户名

        Returns:
            List[Dict]: 所有SOP记忆列表
        """
        return await self.search_sop_memories(
            query="", n_results=100, user_name=user_name  # 获取较多结果
        )

    async def clear_sop_memory(
        self, problem_type: str = None, user_name: str = None
    ) -> bool:
        """
        清除指定条件的SOP记忆。

        Args:
            problem_type: 问题类型，如果为None则清除所有
            user_name: 用户名

        Returns:
            bool: 是否成功清除
        """
        try:
            # 获取要删除的文档
            memories = await self.get_all_sop_memories(user_name)
            ids_to_delete = []

            for memory in memories:
                metadata = memory["metadata"]
                if problem_type is None or metadata.get("problem_type") == problem_type:
                    if user_name is None or metadata.get("user_name") == user_name:
                        ids_to_delete.append(memory["id"])

            if ids_to_delete:
                self.vector_db.delete_documents(self.collection_name, ids_to_delete)
                logger.info(
                    f"成功清除 {len(ids_to_delete)} 个SOP记忆 (problem_type: {problem_type or 'all'}, user: {user_name or 'all'})"
                )
            else:
                logger.info("没有找到匹配的SOP记忆需要清除")

            return True
        except Exception as e:
            logger.error(f"清除SOP记忆失败: {e}", exc_info=True)
            return False

    def get_collection_info(self) -> Dict[str, Any]:
        """
        获取向量数据库集合信息。

        Returns:
            Dict: 集合信息
        """
        try:
            return self.vector_db.get_collection_info(self.collection_name)
        except Exception as e:
            logger.error(f"获取集合信息失败: {e}")
            return {}

    def test_embedding_function(self) -> bool:
        """
        测试嵌入函数是否正常工作。

        Returns:
            bool: 嵌入函数是否正常工作
        """
        return self.vector_db.test_embedding_function()

    def set_multi_stage_config(
        self,
        first_stage_candidates: int = None,
        second_stage_results: int = None,
        similarity_threshold: float = None,
    ):
        """
        设置多级召回配置参数。

        Args:
            first_stage_candidates: 第一级召回候选数量
            second_stage_results: 第二级召回最终结果数量
            similarity_threshold: 相似度阈值
        """
        if first_stage_candidates is not None:
            self.first_stage_candidates = first_stage_candidates
        if second_stage_results is not None:
            self.second_stage_results = second_stage_results
        if similarity_threshold is not None:
            self.similarity_threshold = similarity_threshold

        logger.info(
            f"多级召回配置已更新: 第一级候选={self.first_stage_candidates}, "
            f"第二级结果={self.second_stage_results}, 相似度阈值={self.similarity_threshold}"
        )

    def get_multi_stage_config(self) -> Dict[str, Any]:
        """
        获取多级召回配置信息。

        Returns:
            Dict: 多级召回配置信息
        """
        return {
            "first_stage_candidates": self.first_stage_candidates,
            "second_stage_results": self.second_stage_results,
            "similarity_threshold": self.similarity_threshold,
            "collection_name": self.collection_name,
        }

    async def compare_recall_methods(
        self,
        query: str,
        problem_type: Optional[str] = None,
        user_name: str = None,
    ) -> Dict[str, Any]:
        """
        比较多级召回和单级召回的搜索结果。

        Args:
            query: 搜索查询
            problem_type: 过滤问题类型
            user_name: 用户名

        Returns:
            Dict: 比较结果
        """
        try:
            start_time = time.time()

            # 多级召回
            multi_stage_start = time.time()
            multi_stage_results = await self.multi_stage_search_sop_memories(
                query=query,
                problem_type=problem_type,
                user_name=user_name,
            )
            multi_stage_time = time.time() - multi_stage_start

            # 单级召回
            single_stage_start = time.time()
            single_stage_results = await self.search_sop_memories(
                query=query,
                use_multi_stage=False,
                problem_type=problem_type,
                user_name=user_name,
            )
            single_stage_time = time.time() - single_stage_start

            total_time = time.time() - start_time

            comparison_result = {
                "query": query,
                "multi_stage": {
                    "results_count": len(multi_stage_results),
                    "execution_time": multi_stage_time,
                    "top_similarity": (
                        multi_stage_results[0]["similarity_score"]
                        if multi_stage_results
                        else 0.0
                    ),
                },
                "single_stage": {
                    "results_count": len(single_stage_results),
                    "execution_time": single_stage_time,
                    "top_similarity": (
                        single_stage_results[0]["similarity_score"]
                        if single_stage_results
                        else 0.0
                    ),
                },
                "total_time": total_time,
                "performance_improvement": (
                    single_stage_time - multi_stage_time
                    if single_stage_time > multi_stage_time
                    else 0.0
                ),
            }

            logger.info(
                f"召回方法比较完成: 多级召回={multi_stage_time:.3f}s, "
                f"单级召回={single_stage_time:.3f}s, 性能提升={comparison_result['performance_improvement']:.3f}s"
            )

            return comparison_result
        except Exception as e:
            logger.error(f"召回方法比较失败: {e}", exc_info=True)
            return {"error": str(e)}


from src.utils.dynamic_observer import auto_apply_here

auto_apply_here(
    globals(),
    include=None,
    exclude=[],
    only_in_module=True,
    verbose=False,
)
