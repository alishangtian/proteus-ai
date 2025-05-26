"""智能体管理器模块"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from uuid import uuid4
from dataclasses import dataclass, asdict


@dataclass
class AgentData:
    """智能体数据类"""

    id: str
    name: str
    description: str
    system_prompt: str
    tools: List[dict]
    config: dict
    created_at: str
    updated_at: str


class AgentManager:
    """智能体管理器"""

    _instance = None
    _agents: Dict[str, AgentData] = {}
    _storage_path = "data/agents.json"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentManager, cls).__new__(cls)
            cls._instance._load_agents()
        return cls._instance

    def _load_agents(self):
        """从文件加载智能体数据"""
        try:
            Path(self._storage_path).parent.mkdir(parents=True, exist_ok=True)
            if Path(self._storage_path).exists():
                with open(self._storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._agents = {
                        agent_id: AgentData(**agent_data)
                        for agent_id, agent_data in data.items()
                    }
        except Exception as e:
            print(f"加载智能体数据失败: {e}")
            self._agents = {}

    def _save_agents(self):
        """保存智能体数据到文件"""
        try:
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(
                    {k: asdict(v) for k, v in self._agents.items()},
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
        except Exception as e:
            print(f"保存智能体数据失败: {e}")

    def create_agent(
        self,
        name: str,
        description: str,
        system_prompt: str,
        tools: List[dict],
        config: dict,
    ) -> AgentData:
        """创建新智能体"""
        agent_id = str(uuid4())
        now = datetime.now().isoformat()
        agent = AgentData(
            id=agent_id,
            name=name,
            description=description,
            system_prompt=system_prompt,
            tools=tools,
            config=config,
            created_at=now,
            updated_at=now,
        )
        self._agents[agent_id] = agent
        self._save_agents()
        return agent

    def update_agent(self, agent_id: str, **kwargs) -> Optional[AgentData]:
        """更新智能体"""
        if agent_id not in self._agents:
            return None

        agent = self._agents[agent_id]
        for key, value in kwargs.items():
            if hasattr(agent, key):
                setattr(agent, key, value)

        agent.updated_at = datetime.now().isoformat()
        self._save_agents()
        return agent

    def delete_agent(self, agent_id: str) -> bool:
        """删除智能体"""
        if agent_id in self._agents:
            del self._agents[agent_id]
            self._save_agents()
            return True
        return False

    def get_agent(self, agent_id: str) -> Optional[AgentData]:
        """获取单个智能体"""
        return self._agents.get(agent_id)

    def list_agents(self) -> List[AgentData]:
        """获取智能体列表"""
        return list(self._agents.values())

    def search_agents(self, query: str) -> List[AgentData]:
        """搜索智能体"""
        query = query.lower()
        return [
            agent
            for agent in self._agents.values()
            if query in agent.name.lower() or query in agent.description.lower()
        ]
