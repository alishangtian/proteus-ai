"""
TeamManager使用示例
"""

import asyncio
import sys
import os
import logging
import yaml

# 将项目根目录添加到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from proteus.src.manager.team_manager import TeamManager, generate_team_config, save_team_config_to_file

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def generate_team_config_example():
    """
    生成团队配置示例
    """
    # 示例用户输入
    user_input = """
    我需要一个能够进行数据分析和可视化的AI团队。
    团队需要能够处理大规模数据集，进行数据清洗、分析，并生成可视化报告。
    团队还应该能够使用Python进行数据处理和机器学习模型训练。
    """
    
    # 生成团队配置
    try:
        logger.info("开始生成团队配置...")
        team_config = await generate_team_config(user_input)
        
        # 打印生成的团队配置
        logger.info("生成的团队配置:")
        print(yaml.dump(team_config, allow_unicode=True, sort_keys=False))
        
        return team_config
    except Exception as e:
        logger.error(f"生成团队配置失败: {str(e)}")
        return None


async def save_team_config_example():
    """
    保存团队配置示例
    """
    # 示例用户输入
    user_input = """
    我需要一个能够进行深度研究的AI团队。
    团队需要能够搜索和分析最新的学术论文，从互联网收集相关信息，
    并能够使用Python进行数据处理和分析。
    最后，团队需要生成详细的研究报告。
    """
    
    # 生成并保存团队配置
    try:
        logger.info("开始生成并保存团队配置...")
        
        # 文件名使用描述性名称
        file_name = "deep_research_team_auto.yaml"
        
        # 生成并保存配置
        team_config = await save_team_config_to_file(user_input, file_name)
        
        logger.info(f"团队配置已保存到: {file_name}")
        return team_config
    except Exception as e:
        logger.error(f"生成并保存团队配置失败: {str(e)}")
        return None


async def list_team_configs_example():
    """
    列出所有团队配置示例
    """
    try:
        team_manager = TeamManager()
        config_files = team_manager.list_team_configs()
        
        logger.info("可用的团队配置文件:")
        for file_name in config_files:
            logger.info(f"- {file_name}")
        
        return config_files
    except Exception as e:
        logger.error(f"列出团队配置失败: {str(e)}")
        return []


async def load_team_config_example(file_name: str):
    """
    加载团队配置示例
    
    Args:
        file_name: 要加载的配置文件名
    """
    try:
        team_manager = TeamManager()
        team_config = team_manager.load_team_config(file_name)
        
        logger.info(f"从 {file_name} 加载的团队配置:")
        print(yaml.dump(team_config, allow_unicode=True, sort_keys=False))
        
        return team_config
    except Exception as e:
        logger.error(f"加载团队配置失败: {str(e)}")
        return None


async def main():
    """
    TeamManager使用示例的主函数
    """
    # 生成团队配置
    await generate_team_config_example()
    
    # 生成并保存团队配置
    await save_team_config_example()
    
    # 列出所有团队配置
    config_files = await list_team_configs_example()
    
    # 如果有配置文件，加载第一个
    if config_files:
        await load_team_config_example(config_files[0])


if __name__ == "__main__":
    asyncio.run(main())