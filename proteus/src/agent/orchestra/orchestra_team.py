from src.agent.react_agent import ReactAgent
from src.agent.common.configuration import AgentConfiguration
import logging
from src.utils.langfuse_wrapper import langfuse_wrapper
from src.manager.multi_agent_manager import (
    TeamRole,
)
from typing import Dict, Any


logger = logging.getLogger(__name__)


class OrchestraTeam:

    @langfuse_wrapper.observe_decorator(
        name="__init__", capture_input=True, capture_output=True
    )
    def __init__(
        self,
        tools_config: Dict[str, Any] = None,
        team_rules: str = None,
        start_role: TeamRole = TeamRole.TEAM_LEADER,
        conversation_id: str = None,
        conversation_round: int = 5,
        user_name: str = None,
        sop_memory_enabled: bool = False,
        tool_memory_enabled: bool = False,
    ):
        """
        初始化五个角色的agent

        Args:
            tools_config: 各角色agent的配置，格式为:
                {
                    TeamRole.PLANNER: {
                        "tools": [tool1, tool2],
                        "prompt_template": PLANNER_PROMPT_TEMPLATES,
                        "model_name": "model_name",
                        "termination_conditions": [condition1],
                        "description": "角色描述"
                    },
                    ...
                }
            team_rules: 团队行为规范
            start_role: 启动角色
            conversation_id: 会话ID，用于获取历史迭代信息
            user_name: 用户名，用于工具记忆隔离
        """
        self.agents: Dict[TeamRole, ReactAgent] = {}
        self.team_rules = team_rules or "默认团队规范"
        self.conversation_id = conversation_id
        self.conversation_round = conversation_round
        self.user_name = user_name
        self._initialize_agents(tools_config or {})
        self.startRole = start_role
        self._event_loop_task = None  # 保存事件循环任务引用

    @langfuse_wrapper.observe_decorator(
        name="_initialize_agents", capture_input=True, capture_output=True
    )
    def _initialize_agents(self, tools_config: Dict[TeamRole, AgentConfiguration]):
        """初始化各个角色的agent实例"""
        # 组装team_description
        team_description = (
            "\n# 团队信息\n"
            + "## 团队规范\n"
            + self.team_rules
            + "\n## 团队成员\n"
            + "\n".join(
                f"{role.value}: {config.agent_description}\n"
                for role, config in tools_config.items()
            )
        )

        # 遍历所有角色，初始化agent（使用 ReactAgent 实现）
        for role, config in tools_config.items():
            # 获取agent_instruction的实际内容
            agent_instruction_content = config.agent_instruction
            # 拼接 instruction
            full_instruction = f"{team_description}\n" f"{agent_instruction_content}"
            self.agents[role] = ReactAgent(
                tools=(
                    {str(t): t for t in getattr(config, "tools", [])}
                    if isinstance(config.tools, (list, tuple))
                    else (config.tools or {})
                ),
                prompt_template=config.prompt_template,
                instruction=full_instruction,
                model_name=getattr(config, "model_name", None),
                termination_conditions=getattr(config, "termination_conditions", None),
                max_iterations=getattr(config, "max_iterations", None),
                llm_timeout=getattr(config, "llm_timeout", None),
                conversation_id=self.conversation_id,  # 传递会话ID
                conversation_round=self.conversation_round,
                role_type=role,
                scratchpad_items=getattr(config, "historical_scratchpad_items", None),
                user_name=self.user_name,  # 传递用户名
            )

    @langfuse_wrapper.observe_decorator(
        name="register_agents", capture_input=True, capture_output=True
    )
    async def register_agents(self, chat_id: str = None):
        """将所有agent注册并启动每个agent的 Redis 监听（不使用 MultiAgentManager）"""
        for role, agent in self.agents.items():
            # 直接让 agent 自行监听其专属队列
            await agent.setup_event_subscriptions(agent.agentcard.agentid)

            # 如果提供了 chat_id，则注册到 team agents 列表
            if chat_id:
                try:
                    # 直接调用 Redis 注册逻辑，避免循环导入
                    await self._register_team_agent_to_redis(
                        chat_id,
                        agent.agentcard.agentid,
                        role.value if hasattr(role, "value") else str(role),
                    )
                except Exception as e:
                    logger.error(f"注册 team agent 失败: {e}", exc_info=True)

        # 不再启动集中式事件循环
        self._event_loop_task = None

    async def _register_team_agent_to_redis(
        self, chat_id: str, agent_id: str, role_type: str
    ):
        """注册 team 中的 agent 到 Redis（内部实现）

        Args:
            chat_id: 聊天会话ID
            agent_id: agent ID
            role_type: agent 角色类型
        """
        try:
            from ..utils.redis_cache import RedisCache
            from datetime import datetime
            import json

            redis_cache = RedisCache()

            # 添加 agent 到 team agents 列表
            team_agents_key = f"team_agents:{chat_id}"
            agent_info = {
                "agent_id": agent_id,
                "role_type": role_type,
                "registered_at": datetime.now().isoformat(),
            }
            redis_cache.rpush(
                team_agents_key, json.dumps(agent_info, ensure_ascii=False)
            )

            # 设置过期时间 24 小时
            redis_cache.expire(team_agents_key, 24 * 3600)

            logger.info(f"[{chat_id}] 已注册 team agent: {agent_id} ({role_type})")

        except Exception as e:
            logger.error(f"[{chat_id}] 注册 team agent 失败: {str(e)}", exc_info=True)

    @langfuse_wrapper.observe_decorator(
        name="run", capture_input=True, capture_output=True
    )
    async def run(self, query: str, chat_id: str, stream: bool = True):
        """
        启动团队工作流程

        Args:
            query: 用户输入的问题/任务
            chat_id: 会话ID
            stream: 是否启用流式输出，默认为True
        """
        logger.info(
            f"[{chat_id}] 启动团队工作流程，任务发起人为：{self.startRole.value}"
        )
        start_agent = self.agents[self.startRole]
        result = await start_agent.run(query, chat_id, stream)
        return result

    @langfuse_wrapper.observe_decorator(
        name="stop", capture_input=True, capture_output=True
    )
    async def stop(self):
        """停止所有agent（不再依赖 MultiAgentManager 的事件循环）"""
        # 先停止所有agent
        for agent in self.agents.values():
            await agent.stop()
        self._event_loop_task = None
        logger.info("团队已停止，所有agent监听已关闭")
