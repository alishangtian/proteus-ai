from typing import List, Any
from src.manager.multi_agent_manager import TeamRole
from src.agent.base_agent import ScratchpadItem
from src.agent.terminition import TerminationCondition


class AgentConfiguration:
    """Agent配置类，封装Agent的配置参数

    Attributes:
        role_type (TeamRole): Agent角色类型
        description (str): Agent描述
        prompt_template (str): 提示词模板
        model_name (str): 模型名称
        termination_conditions (List[TerminationCondition]): 终止条件列表
        tools (List[Any]): 工具列表
    """

    def __init__(
        self,
        role_type: TeamRole = None,
        agent_instruction: str = "",
        agent_description: str = "",
        prompt_template: str = "",
        model_name: str = "deepseek-chat",
        termination_conditions: List[TerminationCondition] = None,
        tools: List[Any] = None,
        team_description: str = None,
        max_iterations: int = 50,
        llm_timeout: int = 120,
        conversation_id: str = None,
        conversation_round: int = 5,
        historical_scratchpad_items: List[ScratchpadItem] = None,
    ):
        """初始化Agent配置

        Args:
            role_type: Agent角色类型
            role_description: Agent角色描述
            agent_description: Agent实例描述
            prompt_template: 提示词模板
            model_name: 模型名称
            termination_conditions: 终止条件列表，默认为空列表
            tools: 工具列表，默认为空列表
            team_description: 团队描述
            max_iterations: 最大迭代次数
            llm_timeout: LLM超时时间
            conversation_id: 会话ID，用于获取历史信息
            historical_scratchpad_items: 历史迭代信息，从Redis中获取
        """
        self.role_type = role_type
        self.agent_instruction = agent_instruction
        self.prompt_template = prompt_template
        self.model_name = model_name
        self.termination_conditions = termination_conditions or []
        self.tools = tools or []
        self.team_description = team_description
        self.agent_description = agent_description
        self.max_iterations = max_iterations
        self.llm_timeout = llm_timeout
        self.conversation_id = conversation_id
        self.historical_scratchpad_items = historical_scratchpad_items or []
        self.conversation_round = conversation_round
