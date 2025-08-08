from dataclasses import dataclass
from typing import Optional, List, Any
from ...agent.base_agent import AgentCard, ScratchpadItem, TerminationCondition
from ...manager.multi_agent_manager import TeamRole
from ...api.stream_manager import StreamManager


@dataclass
class AgentConfig:
    tools: List[Any]
    prompt_template: str
    role_type: TeamRole
    model_name: Optional[str] = None
    reasoner_model_name: Optional[str] = None
    instruction: str = ""
    description: str = ""
    team_description: str = ""
    timeout: int = 120
    llm_timeout: int = 60
    max_iterations: int = 10
    iteration_retry_delay: int = 60
    memory_size: int = 10
    cache_size: int = 100
    cache_ttl: int = 3600
    context: Optional[str] = None
    agentcard: Optional[AgentCard] = None
    scratchpad_items: Optional[List[ScratchpadItem]] = None
    termination_conditions: Optional[List[TerminationCondition]] = None
    conversation_id: Optional[str] = None
    stream_manager: Optional[StreamManager] = None
    langfuse_trace: Optional[Any] = None

    def validate(self):
        """验证配置参数的有效性"""
        if not self.prompt_template:
            raise ValueError("prompt_template cannot be empty")
        if not self.role_type:
            raise ValueError("role_type must be specified")
        if not self.model_name and not self.reasoner_model_name:
            raise ValueError("At least one model name must be provided")
        return self
