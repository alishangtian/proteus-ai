"""
Team Manager模块
用于根据用户输入生成team配置
"""

import logging
import yaml
import os
from typing import Dict, Any, List
from string import Template

from ..api.llm_api import call_llm_api
from ..manager.multi_agent_manager import TeamRole
from ..agent.prompt.team_config import TEAM_CONFIG_PROMPT
from ..nodes.node_config import NodeConfigManager

# 配置日志记录
logger = logging.getLogger(__name__)


class TeamManager:
    """
    团队配置管理器
    根据用户输入生成team配置
    """

    def __init__(self):
        """
        初始化TeamManager
        """
        self.default_roles = [
            TeamRole.COORDINATOR,
            TeamRole.PLANNER,
            TeamRole.RESEARCHER,
            TeamRole.CODER,
            TeamRole.REPORTER,
        ]
        self.conf_dir = self._get_conf_dir()
        self.node_config_manager = NodeConfigManager.get_instance()

    def _get_conf_dir(self) -> str:
        """
        获取配置文件目录路径
        逐级向上搜索，直到找到第一个conf目录

        Returns:
            配置文件目录的绝对路径
        """
        # 获取当前文件所在目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 从当前目录开始向上搜索
        search_dir = current_dir

        # 记录项目根目录作为备用方案
        project_root = os.path.abspath(os.path.join(current_dir, "../.."))

        # 向上搜索，直到找到conf目录或达到文件系统根目录
        while True:
            # 检查当前目录下是否有conf目录
            potential_conf_dir = os.path.join(search_dir, "conf")
            if os.path.isdir(potential_conf_dir):
                logger.info(f"找到配置目录: {potential_conf_dir}")
                return potential_conf_dir

            # 获取上一级目录
            parent_dir = os.path.dirname(search_dir)

            # 如果已经到达根目录（上一级目录与当前目录相同），则停止搜索
            if parent_dir == search_dir:
                break

            # 继续向上一级搜索
            search_dir = parent_dir

        # 如果未找到任何conf目录，则在项目根目录下创建一个
        default_conf_dir = os.path.join(project_root, "conf")
        logger.info(f"未找到现有配置目录，将在项目根目录创建: {default_conf_dir}")
        os.makedirs(default_conf_dir, exist_ok=True)

        return default_conf_dir

    def _construct_prompt(self, user_input: str) -> str:
        """
        构造提示词模板

        Args:
            user_input: 用户输入的需求描述

        Returns:
            构造好的提示词
        """
        # 获取可用工具列表
        available_tools = self._get_available_tools()
        tools_description = self._format_tools_description(available_tools)

        # 构建提示词变量
        values = {"tools_description": tools_description, "user_input": user_input}

        # 使用Template替换变量
        prompt_template = Template(TEAM_CONFIG_PROMPT)
        prompt = prompt_template.safe_substitute(values)

        return prompt

    def _get_available_tools(self) -> List[Dict[str, Any]]:
        """
        获取所有可用工具

        Returns:
            工具列表
        """
        try:
            all_tools = self.node_config_manager.get_tools()
            tool_info = []

            for tool in all_tools:
                tool_info.append({"name": tool.name, "description": tool.description})

            return tool_info
        except Exception as e:
            logger.warning(f"获取可用工具失败: {str(e)}")
            # 返回默认工具列表
            return [
                {"name": "handoff", "description": "将任务交接给其他角色"},
                {
                    "name": "web_crawler",
                    "description": "网络爬虫工具，用于获取网页内容",
                },
                {"name": "serper_search", "description": "搜索引擎工具，用于搜索信息"},
                {
                    "name": "python_execute",
                    "description": "Python代码执行工具，用于数据处理和分析",
                },
                {
                    "name": "arxiv_search",
                    "description": "论文搜索工具，用于搜索学术论文",
                },
                {
                    "name": "file_write",
                    "description": "文件写入工具，用于生成报告或保存结果",
                },
                {"name": "final_answer", "description": "提供最终答案的工具"},
            ]

    def _format_tools_description(self, tools: List[Dict[str, Any]]) -> str:
        """
        格式化工具描述

        Args:
            tools: 工具列表

        Returns:
            格式化后的工具描述字符串
        """
        descriptions = []
        for tool in tools:
            descriptions.append(f"- {tool['name']}: {tool['description']}")

        return "\n".join(descriptions)

    async def generate_team_config(
        self, user_input: str, request_id: str = None
    ) -> Dict[str, Any]:
        """
        根据用户输入生成team配置

        Args:
            user_input: 用户输入的团队需求描述
            request_id: 请求ID，用于日志追踪

        Returns:
            生成的团队配置字典
        """
        logger.info(f"[{request_id}] 开始生成团队配置")

        # 调用LLM生成团队配置
        team_config_yaml = await self._generate_team_config_with_llm(
            user_input, request_id
        )

        # 解析YAML格式的团队配置
        try:
            team_config = yaml.safe_load(team_config_yaml)

            # 验证和规范化配置
            team_config = self._validate_and_normalize_config(team_config)

            logger.info(f"[{request_id}] 成功生成团队配置")
            return team_config
        except Exception as e:
            logger.error(f"[{request_id}] 解析团队配置失败: {str(e)}")
            raise ValueError(f"解析团队配置失败: {str(e)}")

    def _validate_and_normalize_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证和规范化团队配置

        Args:
            config: 原始团队配置

        Returns:
            规范化后的团队配置
        """
        if not config:
            raise ValueError("团队配置为空")

        if "team_rules" not in config:
            config["team_rules"] = "你们是一个高效的AI团队，协作完成任务"

        if "start_role" not in config:
            config["start_role"] = "COORDINATOR"

        if "roles" not in config:
            raise ValueError("团队配置缺少roles部分")

        # 规范化角色配置
        normalized_roles = {}
        for role_name, role_config in config["roles"].items():
            # 确保角色名是TeamRole枚举值
            try:
                role_enum = TeamRole(role_name.lower())
                role_name = role_enum.name
            except ValueError:
                logger.warning(
                    f"角色名 {role_name} 不是有效的TeamRole枚举值，将使用原始名称"
                )

            # 确保必要的配置项存在
            if "tools" not in role_config:
                role_config["tools"] = ["handoff"]

            if "prompt_template" not in role_config:
                role_config["prompt_template"] = f"{role_name}_PROMPT_TEMPLATES"

            if "agent_description" not in role_config:
                role_config["agent_description"] = f"{role_name} 角色"

            if "role_description" not in role_config:
                role_config["role_description"] = f"{role_name} 角色描述"

            if "termination_conditions" not in role_config:
                role_config["termination_conditions"] = [
                    {"type": "ToolTerminationCondition", "tool_names": ["final_answer"]}
                ]

            if "model_name" not in role_config:
                role_config["model_name"] = "deepseek-chat"

            if "max_iterations" not in role_config:
                role_config["max_iterations"] = 5

            normalized_roles[role_name] = role_config

        config["roles"] = normalized_roles
        return config

    async def _generate_team_config_with_llm(
        self, user_input: str, request_id: str = None
    ) -> str:
        """
        使用LLM生成团队配置

        Args:
            user_input: 用户输入的团队需求描述
            request_id: 请求ID，用于日志追踪

        Returns:
            YAML格式的团队配置字符串
        """
        # 构建提示词
        prompt = self._construct_prompt(user_input)

        # 构建消息列表
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_input},
        ]

        # 调用LLM API
        try:
            response = await call_llm_api(
                messages=messages,
                request_id=request_id,
                temperature=0.2,
                output_json=False,
            )

            # 提取YAML内容
            yaml_content = self._extract_yaml_content(response)
            return yaml_content

        except Exception as e:
            logger.error(f"[{request_id}] 调用LLM API生成团队配置失败: {str(e)}")
            raise ValueError(f"生成团队配置失败: {str(e)}")

    def _extract_yaml_content(self, response: str) -> str:
        """
        从LLM响应中提取YAML内容

        Args:
            response: LLM的响应文本

        Returns:
            提取的YAML内容
        """
        # 如果响应中包含```yaml和```标记，则提取其中的内容
        if "```yaml" in response and "```" in response.split("```yaml", 1)[1]:
            return response.split("```yaml", 1)[1].split("```", 1)[0].strip()
        # 如果响应中包含```和```标记，则提取其中的内容
        elif "```" in response and "```" in response.split("```", 1)[1]:
            return response.split("```", 1)[1].split("```", 1)[0].strip()
        # 否则返回原始响应
        return response.strip()

    def save_team_config(self, team_config: Dict[str, Any], file_name: str) -> str:
        """
        将团队配置保存到YAML文件

        Args:
            team_config: 团队配置字典
            file_name: 文件名（不包含路径）

        Returns:
            保存的文件路径
        """
        # 确保文件名以.yaml结尾
        if not file_name.endswith(".yaml"):
            file_name += ".yaml"

        # 构建完整的文件路径
        file_path = os.path.join(self.conf_dir, file_name)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                yaml.dump(team_config, f, allow_unicode=True, sort_keys=False)
            logger.info(f"团队配置已保存到: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"保存团队配置失败: {str(e)}")
            raise ValueError(f"保存团队配置失败: {str(e)}")

    def load_team_config(self, file_name: str) -> Dict[str, Any]:
        """
        从YAML文件加载团队配置

        Args:
            file_name: 文件名（不包含路径）

        Returns:
            加载的团队配置字典
        """
        # 确保文件名以.yaml结尾
        if not file_name.endswith(".yaml"):
            file_name += ".yaml"

        # 构建完整的文件路径
        file_path = os.path.join(self.conf_dir, file_name)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                team_config = yaml.safe_load(f)
            logger.info(f"已从{file_path}加载团队配置")
            return team_config
        except Exception as e:
            logger.error(f"加载团队配置失败: {str(e)}")
            raise ValueError(f"加载团队配置失败: {str(e)}")

    def list_team_configs(self) -> List[str]:
        """
        列出所有可用的团队配置文件

        Returns:
            团队配置文件名列表
        """
        try:
            yaml_files = [f for f in os.listdir(self.conf_dir) if f.endswith(".yaml")]
            return yaml_files
        except Exception as e:
            logger.error(f"列出团队配置文件失败: {str(e)}")
            return []


async def generate_team_config(
    user_input: str, request_id: str = None
) -> Dict[str, Any]:
    """
    根据用户输入生成team配置的便捷函数

    Args:
        user_input: 用户输入的团队需求描述
        request_id: 请求ID，用于日志追踪

    Returns:
        生成的团队配置字典
    """
    team_manager = TeamManager()
    return await team_manager.generate_team_config(user_input, request_id)


async def save_team_config_to_file(
    user_input: str, file_name: str, request_id: str = None
) -> Dict[str, Any]:
    """
    根据用户输入生成team配置并保存到文件

    Args:
        user_input: 用户输入的团队需求描述
        file_name: 保存的文件名（不包含路径）
        request_id: 请求ID，用于日志追踪

    Returns:
        生成的团队配置字典
    """
    team_manager = TeamManager()
    team_config = await team_manager.generate_team_config(user_input, request_id)
    team_manager.save_team_config(team_config, file_name)
    return team_config
