from typing import Dict, Any, Optional, List
import logging
import json
import uuid
from datetime import datetime
import time

from src.api.llm_api import call_llm_api
from src.skills.skills_prompt import (
    SKILLS_DESCRIPTION_PROMPT,
    SKILLS_DETAIL_PROMPT,
    SKILLS_MERGE_PROMPT,
)
from src.utils.chrome_vector_db import ChromeVectorDB
from src.utils.ollama_embedding import get_embedding_model
from src.utils.langfuse_wrapper import langfuse_wrapper

logger = logging.getLogger(__name__)


class SkillManager:
    """技能管理器，使用 Chrome 向量数据库和 Ollama bge-m3 嵌入模型

    主要功能：
    - 根据用户问题、工具调用链路、最终结果生成技能描述和技能详情
    - 将技能描述和详情分别存储到Chrome向量数据库
    - 使用两级召回逻辑：第一级召回技能描述，第二级召回技能详情
    """

    def __init__(
        self,
        vector_db: Optional[ChromeVectorDB] = None,
        ollama_url: str = "http://127.0.0.1:11434",
    ):
        """初始化技能管理器

        Args:
            vector_db: Chrome向量数据库实例，如果为None则创建默认实例
            ollama_url: Ollama服务地址
        """
        self.vector_db = vector_db or ChromeVectorDB(ollama_url=ollama_url)
        self.embedding_model = get_embedding_model(base_url=ollama_url)
        self.collection_name = "skills"

        # 测试连接和嵌入函数
        if not self.embedding_model.test_connection():
            logger.warning("Ollama 服务连接失败，嵌入功能可能不可用")
        else:
            # 测试嵌入函数
            if not self.vector_db.test_embedding_function():
                logger.warning("嵌入函数测试失败，向量搜索可能不可用")

        # 两级召回配置
        self.first_stage_candidates = 20  # 第一级召回候选数量（技能描述）
        self.second_stage_results = 5  # 第二级召回最终结果数量（技能详情）
        self.similarity_threshold = 0.4  # 相似度阈值

    @langfuse_wrapper.dynamic_observe()
    async def generate_skill_description(
        self,
        user_query: str,
        tool_chain: List[Dict[str, Any]],
        final_result: str,
        model_name: str = None,
    ) -> str:
        """
        调用LLM生成技能描述（限150字符）。

        Args:
            user_query: 用户原始问题
            tool_chain: 工具调用链，包含工具名称和输入参数
            final_result: 最终解决结果
            model_name: 使用的模型名称

        Returns:
            str: 技能描述
        """
        # 格式化工具调用链信息
        tool_chain_info = []
        for i, tool_call in enumerate(tool_chain, 1):
            tool_name = tool_call.get("tool_name", "未知工具")
            action_input = tool_call.get("action_input", {})
            tool_chain_info.append(
                f"步骤{i}: {tool_name} - 输入: {json.dumps(action_input, ensure_ascii=False)}"
            )

        tool_chain_str = "\n".join(tool_chain_info)

        # 使用技能描述生成提示词模板
        prompt = SKILLS_DESCRIPTION_PROMPT.format(
            user_query=user_query,
            tool_chain=tool_chain_str,
            final_result=final_result,
        )

        if not model_name:
            logger.error("没有可用的模型进行技能描述生成")
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
            # 限制长度
            if len(result) > 150:
                result = result[:150]

            logger.info(f"生成技能描述({len(result)}字符): {result}")
            return result
        except Exception as e:
            logger.error(f"调用LLM生成技能描述时发生错误: {e}", exc_info=True)
            return ""

    @langfuse_wrapper.dynamic_observe()
    async def generate_skill_detail(
        self,
        user_query: str,
        skill_description: str,
        tool_chain: List[Dict[str, Any]],
        final_result: str,
        model_name: str = None,
    ) -> str:
        """
        调用LLM生成技能详情（限800字符）。

        Args:
            user_query: 用户原始问题
            skill_description: 技能描述
            tool_chain: 工具调用链，包含工具名称和输入参数
            final_result: 最终解决结果
            model_name: 使用的模型名称

        Returns:
            str: 技能详情
        """
        # 格式化工具调用链信息
        tool_chain_info = []
        for i, tool_call in enumerate(tool_chain, 1):
            tool_name = tool_call.get("tool_name", "未知工具")
            action_input = tool_call.get("action_input", {})
            tool_chain_info.append(
                f"步骤{i}: {tool_name} - 输入: {json.dumps(action_input, ensure_ascii=False)}"
            )

        tool_chain_str = "\n".join(tool_chain_info)

        # 使用技能详情生成提示词模板
        prompt = SKILLS_DETAIL_PROMPT.format(
            user_query=user_query,
            skill_description=skill_description,
            tool_chain=tool_chain_str,
            final_result=final_result,
        )

        if not model_name:
            logger.error("没有可用的模型进行技能详情生成")
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

            logger.info(f"生成技能详情({len(result)}字符): {result[:100]}...")
            return result
        except Exception as e:
            logger.error(f"调用LLM生成技能详情时发生错误: {e}", exc_info=True)
            return ""

    @langfuse_wrapper.dynamic_observe()
    async def save_skill(
        self,
        skill_description: str,
        skill_detail: str,
        user_query: str,
        tool_chain: List[Dict[str, Any]],
        final_result: str,
        user_name: str = None,
    ) -> str:
        """
        将技能描述和详情分别存储到Chrome向量数据库中。

        采用两级存储策略：
        1. 技能描述（description）：用于第一级召回，简洁明了
        2. 技能详情（detail）：用于第二级召回，包含具体步骤和注意事项

        Args:
            skill_description: 技能描述
            skill_detail: 技能详情
            user_query: 用户原始问题
            tool_chain: 工具调用链
            final_result: 最终结果
            user_name: 用户名，用于用户隔离

        Returns:
            str: 存储的技能ID（基础ID）
        """
        try:
            # 生成基础技能ID（用于关联 description 与 detail）
            base_id = str(uuid.uuid4())
            description_id = f"{base_id}_description"
            detail_id = f"{base_id}_detail"

            # 构建描述文档（用于第一级召回）
            description_text = skill_description

            # 构建详情文档（用于第二级召回）
            detail_text = f"""
技能描述: {skill_description}
用户问题: {user_query}
详细步骤: {skill_detail}
工具链: {len(tool_chain)} 个工具
最终结果: {final_result}
            """.strip()

            # 构建元数据
            common_metadata = {
                "user_query": user_query,
                "tool_count": len(tool_chain),
                "final_result_preview": final_result[:200] if final_result else "",
                "user_name": user_name or "global",
                "created_at": datetime.now().isoformat(),
                "parent_id": base_id,
            }

            # 描述元数据（第一级召回）
            description_metadata = common_metadata.copy()
            description_metadata.update(
                {
                    "is_description": True,
                    "skill_description": skill_description,
                }
            )

            # 详情元数据（第二级召回）
            detail_metadata = common_metadata.copy()
            detail_metadata.update(
                {
                    "is_description": False,
                    "skill_description": skill_description,
                    "skill_detail": skill_detail,
                }
            )

            # 存储到向量数据库：先存描述（便于第一级召回），再存详情（第二级召回）
            self.vector_db.add_documents(
                collection_name=self.collection_name,
                documents=[description_text, detail_text],
                metadatas=[description_metadata, detail_metadata],
                ids=[description_id, detail_id],
            )

            logger.info(f"成功保存技能到向量数据库 (user: {user_name or 'global'})")
            # 返回 base_id，作为这条技能的唯一标识（description/detail 共用）
            return base_id
        except Exception as e:
            logger.error(
                f"保存技能到向量数据库失败: {e}",
                exc_info=True,
            )
            raise

    @langfuse_wrapper.dynamic_observe()
    async def first_stage_recall(
        self,
        query: str,
        n_candidates: int = None,
        user_name: str = None,
    ) -> List[Dict[str, Any]]:
        """
        第一级召回：基于技能描述的快速相似度匹配

        Args:
            query: 用户查询文本
            n_candidates: 候选数量，如果为None则使用默认值
            user_name: 用户名，用于用户隔离

        Returns:
            List[Dict]: 第一级召回候选结果（技能描述）
        """
        try:
            start_time = time.time()

            # 构建过滤条件：只召回描述文档
            where_filter = {"is_description": True}
            if user_name:
                where_filter["user_name"] = user_name

            # 第一级召回：基于技能描述的快速匹配
            results = self.vector_db.query(
                collection_name=self.collection_name,
                query_texts=[query],
                n_results=n_candidates or self.first_stage_candidates,
                where=where_filter,
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
                        "recall_stage": "first_stage_description",
                    }
                )

            elapsed_time = time.time() - start_time
            logger.info(
                f"第一级召回完成（技能描述）: 查询 '{query}' 返回 {len(formatted_results)} 个候选结果，耗时 {elapsed_time:.3f}s"
            )
            return formatted_results
        except Exception as e:
            logger.error(f"第一级召回失败: {e}", exc_info=True)
            return []

    @langfuse_wrapper.dynamic_observe()
    async def second_stage_recall(
        self,
        query: str,
        first_stage_candidates: List[Dict[str, Any]],
        n_results: int = None,
    ) -> List[Dict[str, Any]]:
        """
        第二级召回：基于技能详情的精确相似度匹配

        Args:
            query: 用户查询文本
            first_stage_candidates: 第一级召回候选结果
            n_results: 最终结果数量，如果为None则使用默认值

        Returns:
            List[Dict]: 第二级召回最终结果（技能详情）
        """
        try:
            start_time = time.time()

            if not first_stage_candidates:
                logger.info("第二级召回：第一级召回无候选结果，直接返回空列表")
                return []

            # 提取第一级候选的父ID，用于查找对应的详情文档
            parent_ids = [
                candidate["metadata"]["parent_id"]
                for candidate in first_stage_candidates
            ]

            # 构建详情文档的ID列表
            detail_ids = [f"{parent_id}_detail" for parent_id in parent_ids]

            # 第二级召回：基于技能详情进行精确匹配
            results = self.vector_db.query(
                collection_name=self.collection_name,
                query_texts=[query],
                n_results=n_results or self.second_stage_results,
                where={"is_description": False},  # 只查询详情文档
                ids=detail_ids if detail_ids else None,
            )

            # 格式化返回结果并计算综合分数
            final_results = []
            for i in range(len(results["documents"][0])):
                metadata = results["metadatas"][0][i]
                distance = results["distances"][0][i]

                # 计算第二级相似度分数
                second_stage_similarity = 1.0 - distance if distance <= 1.0 else 0.0

                # 查找对应的第一级召回结果（通过 parent_id）
                parent_id = metadata.get("parent_id")
                first_stage_result = next(
                    (
                        candidate
                        for candidate in first_stage_candidates
                        if candidate["metadata"]["parent_id"] == parent_id
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
                        "recall_stage": "second_stage_detail",
                    }
                )

            # 按综合分数排序
            final_results.sort(key=lambda x: x["similarity_score"], reverse=True)

            elapsed_time = time.time() - start_time
            logger.info(
                f"第二级召回完成（技能详情）: 从 {len(first_stage_candidates)} 个候选筛选出 {len(final_results)} 个最终结果，耗时 {elapsed_time:.3f}s"
            )
            return final_results
        except Exception as e:
            logger.error(f"第二级召回失败: {e}", exc_info=True)
            return []

    @langfuse_wrapper.dynamic_observe()
    async def search_skills(
        self,
        query: str,
        n_results: int = 5,
        user_name: str = None,
    ) -> List[Dict[str, Any]]:
        """
        使用两级召回逻辑搜索技能。
        第一级：基于技能描述召回候选
        第二级：基于技能详情精确匹配

        Args:
            query: 搜索查询
            n_results: 返回结果数量
            user_name: 用户名，用于用户隔离

        Returns:
            List[Dict]: 匹配的技能列表
        """
        try:
            start_time = time.time()
            logger.info(f"开始两级召回搜索技能: '{query}'")

            # 第一级召回：基于技能描述的快速相似度匹配
            first_stage_results = await self.first_stage_recall(
                query=query,
                n_candidates=self.first_stage_candidates,
                user_name=user_name,
            )

            # 过滤低相似度的候选结果
            filtered_candidates = [
                candidate
                for candidate in first_stage_results
                if candidate["similarity_score"] >= self.similarity_threshold
            ]

            if not filtered_candidates:
                logger.info("两级召回：第一级召回无符合条件的候选结果")
                return []

            # 第二级召回：基于技能详情的精确相似度匹配
            second_stage_results = await self.second_stage_recall(
                query=query,
                first_stage_candidates=filtered_candidates,
                n_results=n_results,
            )

            elapsed_time = time.time() - start_time
            logger.info(
                f"两级召回搜索完成: 查询 '{query}' 返回 {len(second_stage_results)} 个最终结果，总耗时 {elapsed_time:.3f}s"
            )

            return second_stage_results
        except Exception as e:
            logger.error(f"两级召回搜索技能失败: {e}", exc_info=True)
            return []

    @langfuse_wrapper.dynamic_observe()
    async def merge_skills(
        self,
        new_skill_description: str,
        new_skill_detail: str,
        similar_skills: List[Dict[str, Any]],
        model_name: str = None,
    ) -> tuple[str, str]:
        """
        使用LLM合并新技能和相似技能。

        Args:
            new_skill_description: 新技能描述
            new_skill_detail: 新技能详情
            similar_skills: 相似技能列表
            model_name: 模型名称

        Returns:
            Tuple[str, str]: 合并后的技能描述和详情
        """
        try:
            skill1 = similar_skills[0]
            skill1_description = skill1["metadata"].get("skill_description", "")
            skill1_detail = skill1["metadata"].get("skill_detail", "")

            skill2_block = ""
            if len(similar_skills) > 1:
                skill2 = similar_skills[1]
                skill2_description = skill2["metadata"].get("skill_description", "")
                skill2_detail = skill2["metadata"].get("skill_detail", "")
                skill2_block = f"""
相似技能 2:
描述: {skill2_description}
详情: {skill2_detail}
"""

            prompt = SKILLS_MERGE_PROMPT.format(
                new_skill_description=new_skill_description,
                new_skill_detail=new_skill_detail,
                skill1_description=skill1_description,
                skill1_detail=skill1_detail,
                skill2_block=skill2_block,
            )

            if not model_name:
                model_name = "deepseek-chat"

            response, _ = await call_llm_api(
                [{"role": "user", "content": prompt}],
                model_name=model_name,
                output_json=True,
            )

            # 解析JSON响应
            try:
                # 尝试清理可能的markdown标记
                cleaned_response = (
                    response.replace("```json", "").replace("```", "").strip()
                )
                merged_data = json.loads(cleaned_response)
                return merged_data.get("description", ""), merged_data.get("detail", "")
            except json.JSONDecodeError:
                logger.error(f"解析合并技能响应失败: {response}")
                return new_skill_description, new_skill_detail

        except Exception as e:
            logger.error(f"合并技能失败: {e}", exc_info=True)
            return new_skill_description, new_skill_detail

    @langfuse_wrapper.dynamic_observe()
    async def process_and_save_skill(
        self,
        user_query: str,
        tool_chain: List[Dict[str, Any]],
        final_result: str,
        user_name: str = None,
        model_name: str = None,
    ) -> Optional[str]:
        """
        完整的技能处理流程：生成技能描述和详情，并保存到向量数据库。
        包含技能召回和合并逻辑。

        Args:
            user_query: 用户原始问题
            tool_chain: 工具调用链
            final_result: 最终解决结果
            user_name: 用户名，用于技能隔离
            model_name: 使用的模型名称

        Returns:
            Optional[str]: 保存的技能ID，如果失败则返回None
        """
        try:
            logger.info(f"开始处理技能: '{user_query}'")

            # 1. 生成技能描述
            skill_description = await self.generate_skill_description(
                user_query=user_query,
                tool_chain=tool_chain,
                final_result=final_result,
                model_name=model_name,
            )

            if not skill_description or not skill_description.strip():
                logger.warning("技能描述生成失败，跳过保存")
                return None

            # 2. 生成技能详情
            skill_detail = await self.generate_skill_detail(
                user_query=user_query,
                skill_description=skill_description,
                tool_chain=tool_chain,
                final_result=final_result,
                model_name=model_name,
            )

            if not skill_detail or not skill_detail.strip():
                logger.warning("技能详情生成失败，跳过保存")
                return None

            # 3. 技能召回（用于合并）
            # 3.1 按照新技能描述进行召回
            recall_results_desc = await self.first_stage_recall(
                query=skill_description,
                n_candidates=5,
                user_name=user_name,
            )

            # 3.2 按照技能内容（详情）进行召回
            # 注意：这里我们直接用详情文本去查询详情文档
            # 为了复用 second_stage_recall，我们需要构造假的 first_stage_candidates 或者直接查询
            # 但 second_stage_recall 依赖 first_stage_candidates 的 parent_id
            # 所以这里直接使用 vector_db.query 查询详情文档更合适

            recall_results_detail = []
            try:
                detail_query_results = self.vector_db.query(
                    collection_name=self.collection_name,
                    query_texts=[skill_detail],
                    n_results=5,
                    where={
                        "is_description": False,
                        **({"user_name": user_name} if user_name else {}),
                    },
                )

                for i in range(len(detail_query_results["documents"][0])):
                    metadata = detail_query_results["metadatas"][0][i]
                    distance = detail_query_results["distances"][0][i]
                    similarity_score = 1.0 - distance if distance <= 1.0 else 0.0

                    recall_results_detail.append(
                        {
                            "document": detail_query_results["documents"][0][i],
                            "metadata": metadata,
                            "distance": distance,
                            "similarity_score": similarity_score,
                            "id": detail_query_results["ids"][0][i],
                            "recall_stage": "content_recall",
                        }
                    )
            except Exception as e:
                logger.error(f"内容召回失败: {e}")

            # 3.3 合并召回结果并去重
            # 我们需要的是详情文档（包含完整信息），first_stage_recall 返回的是描述文档
            # 所以对于 recall_results_desc，我们需要找到对应的详情文档

            candidate_skills = {}  # parent_id -> skill_info

            # 处理描述召回结果
            for res in recall_results_desc:
                if res["similarity_score"] < self.similarity_threshold:
                    continue
                parent_id = res["metadata"]["parent_id"]
                # 这里我们暂时只有描述信息，详情信息需要额外获取，或者在合并时再获取
                # 为了简化，我们假设如果描述相似，就值得合并。
                # 但为了合并，我们需要详情内容。
                # 我们可以先记录下来，后面统一获取详情。
                candidate_skills[parent_id] = {
                    "score": res["similarity_score"],
                    "parent_id": parent_id,
                    "source": "description",
                }

            # 处理详情召回结果
            for res in recall_results_detail:
                if res["similarity_score"] < self.similarity_threshold:
                    continue
                parent_id = res["metadata"]["parent_id"]
                score = res["similarity_score"]

                if parent_id in candidate_skills:
                    # 如果已经存在，取最高分
                    candidate_skills[parent_id]["score"] = max(
                        candidate_skills[parent_id]["score"], score
                    )
                    candidate_skills[parent_id]["source"] = "both"
                    # 如果是详情召回，我们直接有详情内容
                    candidate_skills[parent_id]["detail_content"] = res["document"]
                    candidate_skills[parent_id]["metadata"] = res["metadata"]
                else:
                    candidate_skills[parent_id] = {
                        "score": score,
                        "parent_id": parent_id,
                        "source": "detail",
                        "detail_content": res["document"],
                        "metadata": res["metadata"],
                    }

            # 3.4 获取缺失的详情内容（针对仅通过描述召回的技能）
            # 如果有必要，可以去数据库查。但为了性能，我们可以只处理那些已经有详情的（通过详情召回的），
            # 或者如果 candidate_skills 中有缺失详情的，我们需要去查一下。
            # 鉴于 vector_db 接口限制，我们可能需要通过 ID 获取。

            ids_to_fetch = [
                f"{info['parent_id']}_detail"
                for info in candidate_skills.values()
                if "detail_content" not in info
            ]

            if ids_to_fetch:
                try:
                    fetched = self.vector_db.get_documents(
                        collection_name=self.collection_name, ids=ids_to_fetch
                    )
                    for i, doc_id in enumerate(fetched["ids"]):
                        parent_id = doc_id.replace("_detail", "")
                        if parent_id in candidate_skills:
                            candidate_skills[parent_id]["detail_content"] = fetched[
                                "documents"
                            ][i]
                            candidate_skills[parent_id]["metadata"] = fetched[
                                "metadatas"
                            ][i]
                except Exception as e:
                    logger.error(f"获取技能详情失败: {e}")

            # 3.5 排序并取前两名
            sorted_candidates = sorted(
                [s for s in candidate_skills.values() if "detail_content" in s],
                key=lambda x: x["score"],
                reverse=True,
            )

            top_candidates = sorted_candidates[:2]

            # 4. 技能合并
            ids_to_delete = []
            if top_candidates:
                logger.info(f"发现 {len(top_candidates)} 个相似技能，准备合并")

                # 准备相似技能列表供 merge_skills 使用
                similar_skills_for_merge = []
                for cand in top_candidates:
                    similar_skills_for_merge.append(
                        {
                            "metadata": cand["metadata"],
                            "document": cand["detail_content"],
                        }
                    )
                    ids_to_delete.append(f"{cand['parent_id']}_description")
                    ids_to_delete.append(f"{cand['parent_id']}_detail")

                # 执行合并
                merged_description, merged_detail = await self.merge_skills(
                    new_skill_description=skill_description,
                    new_skill_detail=skill_detail,
                    similar_skills=similar_skills_for_merge,
                    model_name=model_name,
                )

                if merged_description and merged_detail:
                    skill_description = merged_description
                    skill_detail = merged_detail
                    logger.info("技能合并成功")
                else:
                    logger.warning("技能合并返回空，使用原始技能")

            # 5. 保存技能（合并后的或原始的）
            skill_id = await self.save_skill(
                skill_description=skill_description,
                skill_detail=skill_detail,
                user_query=user_query,
                tool_chain=tool_chain,
                final_result=final_result,
                user_name=user_name,
            )

            # 6. 删除旧技能（如果进行了合并）
            if ids_to_delete and skill_id:
                try:
                    self.vector_db.delete_documents(self.collection_name, ids_to_delete)
                    logger.info(f"已删除 {len(ids_to_delete)//2} 个被合并的旧技能")
                except Exception as e:
                    logger.error(f"删除旧技能失败: {e}")

            logger.info(
                f"技能处理完成: ID={skill_id}, 描述={skill_description[:50]}..."
            )
            return skill_id
        except Exception as e:
            logger.error(f"处理和保存技能失败: {e}", exc_info=True)
            return None

    @langfuse_wrapper.dynamic_observe()
    async def get_all_skills(self, user_name: str = None) -> List[Dict[str, Any]]:
        """
        获取所有技能（通过搜索空查询实现）。

        Args:
            user_name: 用户名

        Returns:
            List[Dict]: 所有技能列表
        """
        try:
            where_filter = {}
            if user_name:
                where_filter["user_name"] = user_name

            # 只获取详情文档（包含完整信息）
            where_filter["is_description"] = False

            results = self.vector_db.query(
                collection_name=self.collection_name,
                query_texts=[""],
                n_results=100,
                where=where_filter if where_filter else None,
            )

            formatted_results = []
            for i in range(len(results["documents"][0])):
                formatted_results.append(
                    {
                        "document": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i],
                        "id": results["ids"][0][i],
                    }
                )

            return formatted_results
        except Exception as e:
            logger.error(f"获取所有技能失败: {e}", exc_info=True)
            return []

    @langfuse_wrapper.dynamic_observe()
    async def clear_skills(self, user_name: str = None) -> bool:
        """
        清除指定条件的技能。

        Args:
            user_name: 用户名

        Returns:
            bool: 是否成功清除
        """
        try:
            # 获取要删除的技能
            skills = await self.get_all_skills(user_name)
            ids_to_delete = []

            for skill in skills:
                metadata = skill["metadata"]
                if user_name is None or metadata.get("user_name") == user_name:
                    # 删除详情文档和对应的描述文档
                    parent_id = metadata.get("parent_id")
                    ids_to_delete.append(f"{parent_id}_description")
                    ids_to_delete.append(f"{parent_id}_detail")

            if ids_to_delete:
                self.vector_db.delete_documents(self.collection_name, ids_to_delete)
                logger.info(
                    f"成功清除 {len(ids_to_delete)//2} 个技能 (user: {user_name or 'all'})"
                )
            else:
                logger.info("没有找到匹配的技能需要清除")

            return True
        except Exception as e:
            logger.error(f"清除技能失败: {e}", exc_info=True)
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

    def set_recall_config(
        self,
        first_stage_candidates: int = None,
        second_stage_results: int = None,
        similarity_threshold: float = None,
    ):
        """
        设置两级召回配置参数。

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
            f"两级召回配置已更新: 第一级候选={self.first_stage_candidates}, "
            f"第二级结果={self.second_stage_results}, 相似度阈值={self.similarity_threshold}"
        )

    def get_recall_config(self) -> Dict[str, Any]:
        """
        获取两级召回配置信息。

        Returns:
            Dict: 两级召回配置信息
        """
        return {
            "first_stage_candidates": self.first_stage_candidates,
            "second_stage_results": self.second_stage_results,
            "similarity_threshold": self.similarity_threshold,
            "collection_name": self.collection_name,
        }


from src.utils.dynamic_observer import auto_apply_here

auto_apply_here(
    globals(),
    include=None,
    exclude=[],
    only_in_module=True,
    verbose=False,
)
