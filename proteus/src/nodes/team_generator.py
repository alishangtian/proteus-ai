from typing import Dict, Any, Optional
import logging
import time
import os
from .base import BaseNode
from ..manager.team_manager import TeamManager

logger = logging.getLogger(__name__)


class TeamGeneratorNode(BaseNode):
    """团队生成节点 - 根据用户输入生成团队配置的节点

    参数:
        user_input (str): 用户输入的团队需求描述
        save_to_file (bool, optional): 是否将生成的配置保存到文件，默认为False
        file_name (str, optional): 保存的文件名，如果save_to_file为True则必须提供

    返回:
        dict: 包含执行状态、错误信息和生成的团队配置
    """

    def __init__(self):
        super().__init__()
        self.team_manager = TeamManager()

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        user_input = str(params.get("user_input", "")).strip()
        save_to_file = bool(params.get("save_to_file", False))
        file_name = params.get("file_name", "")

        if not user_input:
            raise ValueError("user_input参数不能为空")

        if save_to_file and not file_name:
            raise ValueError("当save_to_file为True时，必须提供file_name参数")

        logger.info(f"开始生成团队配置，用户输入: {user_input[:50]}...")

        try:
            # 生成请求ID用于日志追踪
            request_id = f"team_gen_{int(time.time())}"
            
            # 调用team_manager生成团队配置
            team_config = await self.team_manager.generate_team_config(user_input, request_id)
            
            # 如果需要保存到文件
            if save_to_file:
                file_path = self.team_manager.save_team_config(team_config, file_name)
                logger.info(f"团队配置已保存到文件: {file_path}")
            
            end_time = time.time()
            execution_time = end_time - start_time
            logger.info(f"团队配置生成成功，耗时: {execution_time:.2f} 秒")
            
            return {
                "success": True, 
                "error": None, 
                "team_config": team_config,
                "file_path": file_path if save_to_file else None
            }
            
        except Exception as e:
            end_time = time.time()
            execution_time = end_time - start_time
            error_msg = f"生成团队配置失败: {str(e)}"
            logger.error(f"{error_msg}, 耗时: {execution_time:.2f} 秒")
            
            return {
                "success": False,
                "error": error_msg,
                "team_config": None,
                "file_path": None
            }

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        execution_result = await self.execute(params)
        
        if execution_result["success"]:
            # 格式化团队配置为可读字符串
            import yaml
            team_config_str = yaml.dump(
                execution_result["team_config"], 
                allow_unicode=True, 
                sort_keys=False
            )
            
            result_message = "团队配置生成成功！\n\n"
            if execution_result.get("file_path"):
                result_message += f"配置已保存到: {execution_result['file_path']}\n\n"
            
            result_message += "团队配置详情:\n```yaml\n" + team_config_str + "\n```"
            return {"result": result_message}
        else:
            return {"result": f"团队配置生成失败: {execution_result['error']}"}