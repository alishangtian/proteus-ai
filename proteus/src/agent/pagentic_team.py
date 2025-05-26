"""多Agent团队实现，包含五个不同角色的agent"""

import asyncio
from typing import Dict, Any
from ..manager.multi_agent_manager import TeamRole, get_multi_agent_manager
from .agent import Agent, AgentConfiguration
import logging

logger = logging.getLogger(__name__)


class PagenticTeam:
    """包含五个角色的Agent团队"""

    def __init__(
        self,
        tools_config: Dict[str, Any] = None,
        team_rules: str = None,
        start_role: TeamRole = TeamRole.TEAM_LEADER,
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
        """
        self.agents: Dict[TeamRole, Agent] = {}
        self.team_rules = team_rules or "默认团队规范"
        self._initialize_agents(tools_config or {})
        self.startRole = start_role
        self._event_loop_task = None  # 保存事件循环任务引用

    def _initialize_agents(self, tools_config: Dict[TeamRole, AgentConfiguration]):
        """初始化各个角色的agent实例"""
        # 组装team_description
        team_description = (
            "\n#团队信息\n\n"
            + "##团队规范\n\n"
            + self.team_rules
            + "\n##团队成员\n\n"
            + "\n".join(
                f"{role.value}: {config.role_description}\n"
                for role, config in tools_config.items()
            )
        )

        # 遍历所有角色，初始化agent
        for role, config in tools_config.items():
            self.agents[role] = Agent(
                tools=config.tools,
                prompt_template=config.prompt_template,
                role_type=role,
                model_name=config.model_name,
                termination_conditions=config.termination_conditions,
                team_description=team_description,
                description=config.agent_description,
                max_iterations=config.max_iterations,
                llm_timeout=config.llm_timeout,
            )

    async def register_agents(self):
        """将所有agent注册到MultiAgentManager"""
        manager = get_multi_agent_manager()

        for role, agent in self.agents.items():
            manager.register_agent(agent.agentcard.agentid, agent)
            await agent.setup_event_subscriptions(agent.agentcard.agentid)

        # 启动事件循环并保存任务引用
        self._event_loop_task = asyncio.create_task(manager.start_event_loop())

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
        await start_agent.run(query, chat_id, stream)

    async def stop(self):
        """停止所有agent和事件循环"""
        # 先停止所有agent
        for agent in self.agents.values():
            await agent.stop()

        # 停止事件循环
        manager = get_multi_agent_manager()
        await manager.stop_event_loop()

        # 取消事件循环任务
        if self._event_loop_task is not None and not self._event_loop_task.done():
            self._event_loop_task.cancel()
            try:
                await asyncio.wait_for(self._event_loop_task, timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                logger.warning("取消事件循环任务超时或已被取消")

        self._event_loop_task = None
        logger.info("团队和事件循环已停止")
