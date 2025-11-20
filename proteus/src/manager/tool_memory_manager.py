from typing import Dict, Any, Optional
import logging
import json

from src.api.llm_api import call_llm_api
from src.utils.redis_cache import get_redis_connection
from src.utils.langfuse_wrapper import langfuse_wrapper
from src.agent.prompt.tool_memory_prompt import TOOL_MEMORY_ANALYSIS_PROMPT

logger = logging.getLogger(__name__)


class ToolMemoryManager:
    """工具记忆管理器，负责工具执行经验的提取、存储和检索

    主要功能：
    - 分析工具执行结果，提取使用指导意见
    - 将工具记忆存储到Redis
    - 从Redis加载工具记忆
    - 支持用户隔离的工具记忆
    """

    def __init__(self, redis_manager=None):
        """初始化工具记忆管理器

        Args:
            redis_manager: Redis连接管理器，如果为None则使用默认连接
        """
        self._redis_manager = redis_manager
        self.logger = logger

    async def analyze_tool_execution(
        self,
        tool_name: str,
        action_input: Dict[str, Any],
        error_message: Optional[str] = None,
        observation: Optional[str] = None,
        is_error: bool = False,
        old_memory: Optional[str] = None,
        user_query: Optional[str] = None,
        model_name: str = None,
        chat_id: str = None,
    ) -> str:
        """
        调用LLM分析工具执行结果，提取工具使用方式的指导意见（限500字符）。
        只关注工具的正确使用方式，不关联具体任务内容。

        Args:
            tool_name: 工具名称
            action_input: 工具输入参数
            error_message: 错误信息（如果有）
            observation: 工具执行结果
            chat_id: 会话ID
            is_error: 是否为错误执行
            old_memory: 历史指导意见
            user_query: 用户原始查询，用于更好地理解工具使用场景
            model_name: 使用的模型名称

        Returns:
            str: 工具使用指导意见
        """
        # 构建上下文信息
        context_info = ""
        execution_status = "失败" if is_error else "成功"

        if error_message:
            context_info += f"- 错误信息: {error_message}\n"
        if observation:
            # 截取observation的前200字符，避免过长
            obs_preview = (
                observation[:1000] + "..." if len(observation) > 1000 else observation
            )
            context_info += f"- 工具输出: {obs_preview}\n"
        if old_memory:
            context_info += f"- 历史指导: {old_memory}\n"

        # 安全地获取参数类型信息，处理嵌套字典的情况
        def get_param_type(value):
            """递归获取参数类型描述"""
            if isinstance(value, dict):
                return "dict"
            elif isinstance(value, list):
                return "list"
            else:
                return type(value).__name__

        param_types = {k: get_param_type(v) for k, v in action_input.items()}

        # 使用提取的提示词模板
        prompt = TOOL_MEMORY_ANALYSIS_PROMPT.format(
            tool_name=tool_name,
            execution_status=execution_status,
            param_types=json.dumps(param_types, ensure_ascii=False),
            user_query=user_query or "未提供用户查询信息",
            context_info=context_info,
        )

        if not model_name:
            self.logger.error("没有可用的模型进行工具执行分析")
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

            self.logger.info(
                f"工具 '{tool_name}' ({execution_status}) 指导意见({len(result)}字符): {result}"
            )
            return result
        except Exception as e:
            self.logger.error(f"调用LLM分析工具执行结果时发生错误: {e}", exc_info=True)
            return ""

    async def save_tool_memory(
        self,
        tool_name: str,
        tool_memory: str,  # 工具执行总结（成功或失败的指导意见）
        expire_hours: int = 24,
        user_name: str = None,
    ) -> None:
        """
        将工具执行记忆（指导意见）存储到Redis中。
        以 key:value 形式存储，每次生成新记忆时进行覆盖。
        适用于成功和失败的执行结果。

        Args:
            tool_name: 工具名称
            tool_memory: 工具使用指导意见
            expire_hours: 过期时间（小时）
            user_name: 用户名，用于隔离不同用户的工具记忆
        """
        try:
            redis_cache = get_redis_connection()

            # 使用用户名隔离工具记忆
            if user_name:
                redis_key = f"tool_memory:{user_name}:{tool_name}"
            else:
                redis_key = f"tool_memory:{tool_name}"

            # 直接使用 SET 命令存储，覆盖旧记忆
            redis_cache.set(redis_key, tool_memory)
            self.logger.info(
                f"成功保存工具 '{tool_name}' 的执行记忆到Redis (user: {user_name or 'global'})"
            )
        except Exception as e:
            self.logger.error(
                f"保存工具 '{tool_name}' 执行记忆到Redis失败: {e}", exc_info=True
            )

    async def load_tool_memory(
        self, tool_name: str, user_name: str = None
    ) -> Optional[str]:
        """
        从Redis加载指定工具的最新执行记忆（指导意见）。

        Args:
            tool_name: 工具名称
            user_name: 用户名，用于加载用户专属的工具记忆

        Returns:
            Optional[str]: 工具使用指导意见，如果不存在则返回None
        """
        try:
            redis_cache = get_redis_connection()

            # 优先加载用户专属记忆，如果不存在则加载全局记忆
            if user_name:
                redis_key = f"tool_memory:{user_name}:{tool_name}"
                tool_memory = redis_cache.get(redis_key)
                if tool_memory:
                    self.logger.info(
                        f"成功从Redis加载工具 '{tool_name}' 的用户专属执行记忆 (user: {user_name})"
                    )
                    return tool_memory

            # 回退到全局记忆
            redis_key = f"tool_memory:{tool_name}"
            tool_memory = redis_cache.get(redis_key)
            if tool_memory:
                self.logger.info(f"成功从Redis加载工具 '{tool_name}' 的全局执行记忆")
                return tool_memory
            return None
        except Exception as e:
            self.logger.error(
                f"从Redis加载工具 '{tool_name}' 执行记忆失败: {e}", exc_info=True
            )
            return None

    @langfuse_wrapper.dynamic_observe()
    async def process_tool_memory(
        self,
        tool_name: str,
        action_input: Dict[str, Any],
        observation: Optional[str] = None,
        chat_id: str = None,
        is_error: bool = False,
        error_message: Optional[str] = None,
        user_query: Optional[str] = None,
        user_name: str = None,
        model_name: str = None,
        conversation_id: str = None,
    ) -> Optional[str]:
        """
        异步处理工具记忆提取和保存。
        从所有工具执行结果（成功或失败）中提取事实性指导意见（限500字符），用于优化后续工具调用。

        Args:
            tool_name: 工具名称
            action_input: 工具输入参数
            observation: 工具执行结果
            chat_id: 会话ID
            is_error: 是否为错误执行
            error_message: 错误信息（如果有）
            user_query: 当前会话的用户输入，将与历史会话一起传递给分析
            user_name: 用户名，用于记忆隔离
            model_name: 使用的模型名称
            conversation_id: 会话ID，用于加载历史对话

        Returns:
            Optional[str]: 生成的工具指导意见
        """
        try:
            execution_status = "失败" if is_error else "成功"
            self.logger.info(
                f"开始处理工具 '{tool_name}' 的记忆提取 (状态: {execution_status})"
            )

            # 加载历史记忆
            old_memory = await self.load_tool_memory(tool_name, user_name=user_name)

            # 组合用户输入：历史会话 + 当前会话
            combined_user_queries = user_query or "未提供用户查询信息"

            # 分析并提取指导意见（无论成功或失败都进行分析）
            tool_guidance = await self.analyze_tool_execution(
                tool_name=tool_name,
                action_input=action_input,
                error_message=error_message,
                observation=observation,
                chat_id=chat_id,
                is_error=is_error,
                old_memory=old_memory,
                user_query=combined_user_queries,
                model_name=model_name,
            )

            # 保存指导意见
            if tool_guidance is not None and tool_guidance.strip():
                await self.save_tool_memory(
                    tool_name=tool_name,
                    tool_memory=tool_guidance,
                    user_name=user_name,
                )
                self.logger.info(
                    f"工具 '{tool_name}' ({execution_status}) 指导意见已更新: {tool_guidance[:100]}..."
                )
            else:
                self.logger.info(
                    f"工具 '{tool_name}' ({execution_status}) 未生成新的指导意见"
                )
            return tool_guidance
        except Exception as e:
            self.logger.error(f"处理工具 '{tool_name}' 记忆失败: {e}", exc_info=True)
            return None

    async def clear_tool_memory(self, tool_name: str, user_name: str = None) -> bool:
        """
        清除指定工具的记忆

        Args:
            tool_name: 工具名称
            user_name: 用户名

        Returns:
            bool: 是否成功清除
        """
        try:
            redis_cache = get_redis_connection()

            if user_name:
                redis_key = f"tool_memory:{user_name}:{tool_name}"
            else:
                redis_key = f"tool_memory:{tool_name}"

            result = redis_cache.delete(redis_key)
            success = result > 0

            if success:
                self.logger.info(
                    f"成功清除工具 '{tool_name}' 的记忆 (user: {user_name or 'global'})"
                )
            else:
                self.logger.info(
                    f"工具 '{tool_name}' 的记忆不存在 (user: {user_name or 'global'})"
                )

            return success
        except Exception as e:
            self.logger.error(f"清除工具 '{tool_name}' 记忆失败: {e}", exc_info=True)
            return False

    async def get_all_tool_memories(self, user_name: str = None) -> Dict[str, str]:
        """
        获取所有工具的记忆

        Args:
            user_name: 用户名

        Returns:
            Dict[str, str]: 工具名称到记忆内容的映射
        """
        try:
            redis_cache = get_redis_connection()
            pattern = f"tool_memory:{user_name}:*" if user_name else "tool_memory:*"

            keys = redis_cache.keys(pattern)
            memories = {}

            for key in keys:
                tool_name = (
                    key.decode().split(":")[-1]
                    if user_name
                    else key.decode().split(":")[1]
                )
                memory = redis_cache.get(key)
                if memory:
                    memories[tool_name] = memory.decode()

            self.logger.info(f"成功加载 {len(memories)} 个工具的记忆")
            return memories
        except Exception as e:
            self.logger.error(f"获取所有工具记忆失败: {e}", exc_info=True)
            return {}


from src.utils.dynamic_observer import auto_apply_here

auto_apply_here(
    globals(),
    include=None,
    exclude=[],
    only_in_module=True,
    verbose=False,
)
