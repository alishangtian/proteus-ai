from typing import Dict, Any, Optional
import logging
import time
import os
import yaml
import asyncio
from .base import BaseNode
from ..manager.team_manager import TeamManager
from ..agent.pagentic_team import PagenticTeam
from ..agent.agent import AgentConfiguration
from ..manager.multi_agent_manager import TeamRole
from src.agent.terminition import ToolTerminationCondition

logger = logging.getLogger(__name__)


def get_or_create_team_role(role_name: str) -> TeamRole:
    """获取或创建团队角色
    
    Args:
        role_name (str): 角色名称
        
    Returns:
        TeamRole: 团队角色枚举实例
    """
    try:
        # 首先尝试获取预定义的角色
        return getattr(TeamRole, role_name)
    except AttributeError:
        # 如果角色不存在，动态创建
        logger.warning(f"角色 {role_name} 不在预定义的TeamRole中，动态创建新角色")
        role_value = role_name.lower()
        
        # 检查值是否已存在，避免重复创建
        for existing_role in TeamRole:
            if existing_role.value == role_value:
                logger.info(f"角色值 {role_value} 已存在，使用现有角色: {existing_role.name}")
                return existing_role
        
        # 使用正确的方式创建新的枚举成员
        new_role = object.__new__(TeamRole)
        new_role._name_ = role_name
        new_role._value_ = role_value
        
        # 将新角色添加到TeamRole枚举中
        setattr(TeamRole, role_name, new_role)
        # 更新TeamRole内部映射
        TeamRole._member_map_[role_name] = new_role
        TeamRole._value2member_map_[role_value] = new_role
        # 更新_member_names_列表
        if hasattr(TeamRole, '_member_names_'):
            TeamRole._member_names_.append(role_name)
        
        logger.info(f"成功创建新角色: {role_name} = {role_value}")
        return new_role


class TeamRunnerNode(BaseNode):
    """团队运行节点 - 接收配置文件地址，装配team并运行
    
    参数:
        config_path (str): 团队配置文件路径，相对于conf目录
        query (str): 用户输入的任务描述
        chat_id (str, optional): 会话ID，如果不提供则自动生成
        max_iterations (int, optional): 最大迭代次数，默认为5
        conversation_id (str, optional): 会话ID，用于获取历史迭代信息
    
    返回:
        dict: 包含执行状态、错误信息和执行结果
    """
    
    def __init__(self):
        super().__init__()
        self.team = None
    
    def _find_config_dir(self, filename):
        """递归查找配置文件目录"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        while True:
            conf_path = os.path.join(current_dir, "conf", filename)
            if os.path.exists(conf_path):
                return conf_path
            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir:  # 到达根目录
                break
            current_dir = parent_dir
        return None
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        config_path = str(params.get("config_path", "")).strip()
        query = str(params.get("query", "")).strip()
        chat_id = params.get("chat_id", f"chat-{int(time.time())}")
        max_iterations = int(params.get("max_iterations", 5))
        conversation_id = params.get("conversation_id")  # 新增会话ID参数
        
        if not config_path:
            raise ValueError("config_path参数不能为空")
        
        if not query:
            raise ValueError("query参数不能为空")
            
        logger.info(f"[{chat_id}] 开始装配并运行团队，配置文件: {config_path}")
        
        try:
            # 查找配置文件
            full_config_path = self._find_config_dir(config_path)
            if not full_config_path:
                raise FileNotFoundError(f"找不到配置文件: {config_path}")
            
            logger.info(f"[{chat_id}] 找到配置文件: {full_config_path}")
            
            # 加载YAML配置
            with open(full_config_path, "r", encoding="utf-8") as f:
                team_config = yaml.safe_load(f)
            
            # 构建tools_config字典
            tools_config = {}
            termination_map = {
                'ToolTerminationCondition': ToolTerminationCondition
            }
            
            # 导入所需的prompt模板
            from src.agent.prompt.deep_research.coordinator import COORDINATOR_PROMPT_TEMPLATES
            from src.agent.prompt.deep_research.planner import PLANNER_PROMPT_TEMPLATES
            from src.agent.prompt.deep_research.researcher import RESEARCHER_PROMPT_TEMPLATES
            from src.agent.prompt.deep_research.coder import CODER_PROMPT_TEMPLATES
            from src.agent.prompt.deep_research.reporter import REPORTER_PROMPT_TEMPLATES
            
            # 创建一个prompt模板映射，用于动态获取prompt模板
            prompt_templates = {
                "COORDINATOR_PROMPT_TEMPLATES": COORDINATOR_PROMPT_TEMPLATES,
                "PLANNER_PROMPT_TEMPLATES": PLANNER_PROMPT_TEMPLATES,
                "RESEARCHER_PROMPT_TEMPLATES": RESEARCHER_PROMPT_TEMPLATES,
                "CODER_PROMPT_TEMPLATES": CODER_PROMPT_TEMPLATES,
                "REPORTER_PROMPT_TEMPLATES": REPORTER_PROMPT_TEMPLATES
            }
            
            for role_name, config in team_config["roles"].items():
                termination_conditions = []
                for tc in config["termination_conditions"]:
                    tc_class = termination_map[tc["type"]]
                    termination_conditions.append(tc_class(**{k: v for k, v in tc.items() if k != "type"}))
                
                # 从映射中获取prompt模板
                prompt_template = prompt_templates.get(config["prompt_template"])
                if not prompt_template:
                    raise ValueError(f"未找到prompt模板: {config['prompt_template']}")
                
                # 获取或创建角色枚举
                role_enum = get_or_create_team_role(role_name)
                tools_config[role_enum] = AgentConfiguration(
                    tools=config["tools"],
                    prompt_template=prompt_template,
                    agent_description=config["agent_description"],
                    role_description=config["role_description"],
                    termination_conditions=termination_conditions,
                    model_name=config["model_name"],
                    max_iterations=max_iterations,
                    llm_timeout=config.get("llm_timeout", None)
                )
            
            # 创建团队实例
            # 获取或创建起始角色
            start_role_name = team_config["start_role"]
            start_role_enum = get_or_create_team_role(start_role_name)
            
            self.team = PagenticTeam(
                team_rules=team_config["team_rules"],
                tools_config=tools_config,
                start_role=start_role_enum,
                conversation_id=conversation_id  # 传递会话ID
            )
            
            logger.info(f"[{chat_id}] 配置PagenticTeam角色工具")
            await self.team.register_agents()
            
            logger.info(f"[{chat_id}] PagenticTeam开始运行")
            await self.team.run(query, chat_id)
            
            end_time = time.time()
            execution_time = end_time - start_time
            logger.info(f"[{chat_id}] 团队运行完成，耗时: {execution_time:.2f} 秒")
            
            return {
                "success": True,
                "error": None,
                "chat_id": chat_id,
                "execution_time": execution_time
            }
            
        except Exception as e:
            end_time = time.time()
            execution_time = end_time - start_time
            error_msg = f"团队运行失败: {str(e)}"
            logger.error(f"[{chat_id}] {error_msg}, 耗时: {execution_time:.2f} 秒", exc_info=True)
            
            # 如果team已创建，尝试停止它
            if self.team is not None:
                try:
                    await self.team.stop()
                except Exception as stop_error:
                    logger.error(f"[{chat_id}] 停止团队失败: {str(stop_error)}", exc_info=True)
            
            return {
                "success": False,
                "error": error_msg,
                "chat_id": chat_id,
                "execution_time": execution_time
            }
    
    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        execution_result = await self.execute(params)
        
        if execution_result["success"]:
            result_message = f"团队运行成功！\n\n"
            result_message += f"会话ID: {execution_result['chat_id']}\n"
            result_message += f"执行时间: {execution_result['execution_time']:.2f} 秒"
            return {"result": result_message}
        else:
            return {"result": f"团队运行失败: {execution_result['error']}"}
    
    async def stop(self):
        """停止团队运行"""
        if self.team is not None:
            await self.team.stop()
            self.team = None