"""Langfuse 初始化模块"""

import os
import logging
from pathlib import Path
from typing import Optional

from .langfuse_wrapper import langfuse_wrapper

logger = logging.getLogger(__name__)


def initialize_langfuse_config(
    config_file_path: Optional[str] = None,
    auto_reload: bool = False,
    register_custom_resolvers: bool = True,
) -> bool:
    """初始化 Langfuse 动态配置

    Args:
        config_file_path: 配置文件路径，如果为 None 则使用默认路径
        auto_reload: 是否启用配置文件自动重载
        register_custom_resolvers: 是否注册自定义字段解析器

    Returns:
        bool: 初始化是否成功
    """
    try:
        # 确定配置文件路径
        if config_file_path is None:
            # 尝试多个默认路径
            project_root = Path(__file__).parent.parent.parent
            possible_paths = [
                project_root / "config" / "langfuse_config.json",
                project_root / "langfuse_config.json",
                Path.cwd() / "config" / "langfuse_config.json",
                Path.cwd() / "langfuse_config.json",
            ]

            config_file_path = None
            for path in possible_paths:
                if path.exists():
                    config_file_path = str(path)
                    break

        # 加载配置文件
        if config_file_path and Path(config_file_path).exists():
            langfuse_wrapper.load_config_from_file(config_file_path, auto_reload)
            logger.info(f"Langfuse 配置已从文件加载: {config_file_path}")
        else:
            logger.info("未找到 Langfuse 配置文件，使用默认配置")

        # 注册自定义字段解析器
        if register_custom_resolvers:
            _register_custom_resolvers()

        # 根据环境变量更新全局配置
        _update_global_config_from_env()

        logger.info("Langfuse 动态配置初始化完成")
        return True

    except Exception as e:
        logger.error(f"Langfuse 配置初始化失败: {e}")
        return False


def _register_custom_resolvers():
    """注册自定义字段解析器"""
    import uuid
    import platform
    import socket
    from datetime import datetime

    # 请求ID生成器
    def generate_request_id():
        return str(uuid.uuid4())[:8]

    # 系统信息获取器
    def get_system_info():
        return f"{platform.system()}-{platform.machine()}"

    # 主机名获取器
    def get_hostname():
        return socket.gethostname()

    # 进程ID获取器
    def get_process_id():
        return str(os.getpid())

    # 格式化时间戳
    def get_formatted_timestamp():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ISO 时间戳
    def get_iso_timestamp():
        return datetime.now().isoformat()

    # Unix 时间戳
    def get_unix_timestamp():
        return str(int(datetime.now().timestamp()))

    # 注册解析器
    resolvers = {
        "request_id": generate_request_id,
        "system_info": get_system_info,
        "hostname": get_hostname,
        "process_id": get_process_id,
        "formatted_timestamp": get_formatted_timestamp,
        "iso_timestamp": get_iso_timestamp,
        "unix_timestamp": get_unix_timestamp,
    }

    for name, resolver in resolvers.items():
        langfuse_wrapper.register_field_resolver(name, resolver)

    logger.info(f"已注册 {len(resolvers)} 个自定义字段解析器")


def _update_global_config_from_env():
    """根据环境变量更新全局配置"""
    env_config = {}

    # 从环境变量读取配置
    env_mappings = {
        "APP_VERSION": "version",
        "ENVIRONMENT": "environment",
        "DEPLOYMENT_ID": "deployment_id",
        "SERVICE_NAME": "service_name",
        "LANGFUSE_SESSION_ID": "session_id",
        "LANGFUSE_USER_ID": "user_id",
        "LANGFUSE_RELEASE": "release",
    }

    metadata = {}
    for env_key, config_key in env_mappings.items():
        env_value = os.getenv(env_key)
        if env_value:
            if config_key in ["session_id", "user_id", "release", "version"]:
                env_config[config_key] = env_value
            else:
                metadata[config_key] = env_value

    if metadata:
        env_config["metadata"] = metadata

    # 添加默认标签
    default_tags = ["proteus-ai"]
    environment = os.getenv("ENVIRONMENT", "development")
    default_tags.append(environment)

    if os.getenv("SERVICE_NAME"):
        default_tags.append(os.getenv("SERVICE_NAME"))

    env_config["tags"] = default_tags

    # 更新全局配置
    if env_config:
        langfuse_wrapper.update_global_config(env_config)
        logger.info(f"已根据环境变量更新全局配置: {list(env_config.keys())}")


def setup_langfuse_for_production():
    """生产环境 Langfuse 配置设置"""
    production_config = {
        "capture_input": True,
        "capture_output": True,
        "metadata": {
            "service": "proteus-ai",
            "version": "${env:APP_VERSION}",
            "environment": "production",
            "deployment_id": "${env:DEPLOYMENT_ID}",
            "hostname": "${hostname}",
            "process_id": "${process_id}",
            "startup_time": "${iso_timestamp}",
        },
        "tags": ["proteus", "ai-agent", "production"],
    }

    langfuse_wrapper.update_global_config(production_config)
    logger.info("已设置生产环境 Langfuse 配置")


def setup_langfuse_for_development():
    """开发环境 Langfuse 配置设置"""
    development_config = {
        "capture_input": True,
        "capture_output": True,
        "metadata": {
            "service": "proteus-ai",
            "version": "dev",
            "environment": "development",
            "hostname": "${hostname}",
            "process_id": "${process_id}",
            "developer": os.getenv("USER", "unknown"),
        },
        "tags": ["proteus", "ai-agent", "development", "debug"],
    }

    langfuse_wrapper.update_global_config(development_config)
    logger.info("已设置开发环境 Langfuse 配置")


def get_runtime_config_api():
    """获取运行时配置 API 接口"""
    return {
        "update_function_config": langfuse_wrapper.update_function_config,
        "update_global_config": langfuse_wrapper.update_global_config,
        "register_field_resolver": langfuse_wrapper.register_field_resolver,
        "load_config_from_file": langfuse_wrapper.load_config_from_file,
    }


# 自动初始化（当模块被导入时）
def auto_initialize():
    """自动初始化配置"""
    # 检查是否禁用自动初始化
    if os.getenv("LANGFUSE_AUTO_INIT", "true").lower() == "false":
        return

    # 根据环境选择配置
    environment = os.getenv("ENVIRONMENT", "development").lower()

    if environment == "production":
        initialize_langfuse_config(auto_reload=False)
        setup_langfuse_for_production()
    elif environment == "development":
        initialize_langfuse_config(auto_reload=True)
        setup_langfuse_for_development()
    else:
        # 默认初始化
        initialize_langfuse_config()


# 模块导入时自动初始化
if __name__ != "__main__":
    auto_initialize()
