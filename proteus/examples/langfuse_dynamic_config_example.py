"""Langfuse 动态配置使用示例"""

import os
import sys
import asyncio
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.langfuse_wrapper import langfuse_wrapper
from src.utils.langfuse_config import config_manager


def example_basic_usage():
    """基本使用示例"""
    print("=== 基本使用示例 ===")
    
    # 1. 使用默认动态配置
    @langfuse_wrapper.observe_decorator()
    def process_data(data: str, user_id: str = "anonymous"):
        """处理数据的示例函数"""
        result = f"Processed: {data} for user {user_id}"
        print(f"执行结果: {result}")
        return result
    
    # 调用函数
    result = process_data("test data", user_id="user123")
    print(f"返回结果: {result}\n")


def example_custom_dynamic_config():
    """自定义动态配置示例"""
    print("=== 自定义动态配置示例 ===")
    
    # 2. 使用自定义动态配置
    @langfuse_wrapper.dynamic_observe(
        name="custom-data-processor",
        capture_input=True,
        capture_output=True
    )
    def custom_process_data(data: str, model_name: str = "default"):
        """自定义处理数据的示例函数"""
        result = f"Custom processed: {data} with model {model_name}"
        print(f"执行结果: {result}")
        return result
    
    # 调用函数
    result = custom_process_data("custom data", model_name="gpt-4")
    print(f"返回结果: {result}\n")


def example_runtime_config_update():
    """运行时配置更新示例"""
    print("=== 运行时配置更新示例 ===")
    
    # 3. 运行时更新配置
    @langfuse_wrapper.observe_decorator()
    def dynamic_function(input_data: str):
        """动态配置的函数"""
        result = f"Dynamic result: {input_data}"
        print(f"执行结果: {result}")
        return result
    
    # 第一次调用（使用默认配置）
    print("第一次调用（默认配置）:")
    result1 = dynamic_function("first call")
    
    # 更新函数配置
    langfuse_wrapper.update_function_config("dynamic_function", {
        "name": "updated-dynamic-function",
        "metadata": {
            "version": "2.0",
            "updated_at": "${timestamp}",
            "custom_field": "runtime_updated"
        },
        "tags": ["updated", "runtime", "dynamic"]
    })
    
    print("第二次调用（更新后配置）:")
    result2 = dynamic_function("second call")
    print(f"返回结果: {result2}\n")


def example_field_resolver():
    """自定义字段解析器示例"""
    print("=== 自定义字段解析器示例 ===")
    
    # 4. 注册自定义字段解析器
    def get_request_id():
        """生成请求ID"""
        import uuid
        return str(uuid.uuid4())[:8]
    
    def get_system_info():
        """获取系统信息"""
        import platform
        return f"{platform.system()}-{platform.machine()}"
    
    # 注册解析器
    langfuse_wrapper.register_field_resolver("request_id", get_request_id)
    langfuse_wrapper.register_field_resolver("system_info", get_system_info)
    
    # 更新配置使用自定义解析器
    langfuse_wrapper.update_function_config("resolver_example", {
        "name": "resolver-demo-${request_id}",
        "metadata": {
            "request_id": "${request_id}",
            "system": "${system_info}",
            "timestamp": "${timestamp}"
        },
        "tags": ["resolver", "custom"]
    })
    
    @langfuse_wrapper.observe_decorator()
    def resolver_example(data: str):
        """使用自定义解析器的函数"""
        result = f"Resolver example: {data}"
        print(f"执行结果: {result}")
        return result
    
    # 调用函数
    result = resolver_example("resolver test")
    print(f"返回结果: {result}\n")


def example_config_file_loading():
    """配置文件加载示例"""
    print("=== 配置文件加载示例 ===")
    
    # 5. 从文件加载配置
    config_file = project_root / "config" / "langfuse_config.json"
    if config_file.exists():
        langfuse_wrapper.load_config_from_file(str(config_file))
        print(f"已从文件加载配置: {config_file}")
        
        @langfuse_wrapper.observe_decorator()
        def chat_agent_run(text: str, model_name: str = "deepseek-chat", 
                          chat_id: str = "test-chat", enable_tools: bool = True):
            """模拟 chat_agent_run 函数"""
            result = f"Chat response for: {text}"
            print(f"执行结果: {result}")
            return result
        
        # 调用函数（会使用配置文件中的设置）
        result = chat_agent_run("Hello", model_name="gpt-4", chat_id="chat-123")
        print(f"返回结果: {result}")
    else:
        print(f"配置文件不存在: {config_file}")
    
    print()


async def example_async_function():
    """异步函数示例"""
    print("=== 异步函数示例 ===")
    
    @langfuse_wrapper.dynamic_observe(
        name="async-processor",
        metadata={"type": "async", "timestamp": "${timestamp}"}
    )
    async def async_process(data: str, delay: float = 0.1):
        """异步处理函数"""
        await asyncio.sleep(delay)
        result = f"Async processed: {data}"
        print(f"异步执行结果: {result}")
        return result
    
    # 调用异步函数
    result = await async_process("async data", delay=0.05)
    print(f"异步返回结果: {result}\n")


def example_global_config_update():
    """全局配置更新示例"""
    print("=== 全局配置更新示例 ===")
    
    # 6. 更新全局配置
    langfuse_wrapper.update_global_config({
        "metadata": {
            "service": "proteus-ai-demo",
            "version": "1.0.0",
            "environment": "development",
            "global_timestamp": "${timestamp}"
        },
        "tags": ["demo", "global-config"],
        "capture_input": True,
        "capture_output": True
    })
    
    @langfuse_wrapper.observe_decorator()
    def global_config_example(input_value: str):
        """使用全局配置的函数"""
        result = f"Global config result: {input_value}"
        print(f"执行结果: {result}")
        return result
    
    # 调用函数
    result = global_config_example("global test")
    print(f"返回结果: {result}\n")


def main():
    """主函数"""
    print("Langfuse 动态配置示例\n")
    
    # 设置环境变量（模拟）
    os.environ["APP_VERSION"] = "1.0.0"
    os.environ["ENVIRONMENT"] = "development"
    os.environ["DEPLOYMENT_ID"] = "demo-deployment"
    
    try:
        # 运行各种示例
        example_basic_usage()
        example_custom_dynamic_config()
        example_runtime_config_update()
        example_field_resolver()
        example_config_file_loading()
        example_global_config_update()
        
        # 运行异步示例
        asyncio.run(example_async_function())
        
        print("所有示例执行完成！")
        
    except Exception as e:
        print(f"示例执行出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()