"""
工具转换器使用示例
演示如何将 YAML 节点配置转换为 OpenAI 工具格式
"""

import json
import asyncio
from pathlib import Path
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.tool_converter import ToolConverter, load_tools_from_yaml
from src.api.llm_api import call_llm_api_with_tools, call_llm_api_with_tools_stream


def example_convert_all_tools():
    """示例1: 转换所有节点为工具"""
    print("=" * 60)
    print("示例1: 转换所有节点为工具")
    print("=" * 60)
    
    # 创建转换器
    converter = ToolConverter()
    
    # 转换所有节点
    tools = converter.convert_all_nodes_to_tools()
    
    print(f"\n成功转换 {len(tools)} 个工具")
    print("\n前3个工具示例:")
    for i, tool in enumerate(tools[:3], 1):
        print(f"\n工具 {i}: {tool['function']['name']}")
        print(json.dumps(tool, ensure_ascii=False, indent=2))


def example_convert_specific_tools():
    """示例2: 转换指定的节点为工具"""
    print("\n" + "=" * 60)
    print("示例2: 转换指定的节点为工具")
    print("=" * 60)
    
    # 指定要转换的节点
    node_names = ["SerperSearchNode", "WeatherForecastNode", "FileReadNode"]
    
    # 使用便捷函数转换
    tools = load_tools_from_yaml(node_names=node_names)
    
    print(f"\n成功转换 {len(tools)} 个指定工具:")
    for tool in tools:
        print(f"  - {tool['function']['name']}: {tool['function']['description'][:50]}...")


def example_exclude_tools():
    """示例3: 排除某些节点"""
    print("\n" + "=" * 60)
    print("示例3: 排除某些节点")
    print("=" * 60)
    
    # 排除一些不需要的节点
    exclude_nodes = ["UserInputNode", "HandoffNode", "BrowserAgentNode"]
    
    tools = load_tools_from_yaml(exclude_nodes=exclude_nodes)
    
    print(f"\n转换了 {len(tools)} 个工具（排除了 {len(exclude_nodes)} 个节点）")


def example_get_single_tool():
    """示例4: 获取单个工具定义"""
    print("\n" + "=" * 60)
    print("示例4: 获取单个工具定义")
    print("=" * 60)
    
    converter = ToolConverter()
    
    # 根据函数名获取工具
    tool = converter.get_tool_by_name("serper_search")
    
    if tool:
        print("\n获取到的工具定义:")
        print(json.dumps(tool, ensure_ascii=False, indent=2))
    else:
        print("\n未找到指定的工具")


async def example_use_with_llm():
    """示例5: 结合 LLM API 使用工具"""
    print("\n" + "=" * 60)
    print("示例5: 结合 LLM API 使用工具")
    print("=" * 60)
    
    # 只转换搜索和天气相关的工具
    tools = load_tools_from_yaml(
        node_names=["SerperSearchNode", "WeatherForecastNode"]
    )
    
    print(f"\n加载了 {len(tools)} 个工具:")
    for tool in tools:
        print(f"  - {tool['function']['name']}")
    
    # 准备消息
    messages = [
        {"role": "user", "content": "帮我搜索一下北京今天的天气"}
    ]
    
    print("\n用户问题:", messages[0]["content"])
    print("\n调用 LLM API...")
    
    try:
        # 调用 API（非流式）
        message, usage = await call_llm_api_with_tools(
            messages=messages,
            tools=tools,
            request_id="tool-converter-example",
            model_name="deepseek-chat"
        )
        
        print("\n模型响应:")
        if message.get("content"):
            print(f"  内容: {message['content']}")
        
        if message.get("tool_calls"):
            print(f"  工具调用:")
            for tool_call in message["tool_calls"]:
                print(f"    - 函数: {tool_call['function']['name']}")
                print(f"      参数: {tool_call['function']['arguments']}")
        
        print(f"\nToken 使用: {usage}")
        
    except Exception as e:
        print(f"\n调用失败: {str(e)}")
        print("提示: 请确保已正确配置 API key 和模型")


async def example_streaming_with_tools():
    """示例6: 流式调用与工具"""
    print("\n" + "=" * 60)
    print("示例6: 流式调用与工具")
    print("=" * 60)
    
    # 加载工具
    tools = load_tools_from_yaml(
        node_names=["SerperSearchNode", "ArxivSearchNode"]
    )
    
    messages = [
        {"role": "user", "content": "搜索最新的深度学习论文"}
    ]
    
    print("\n用户问题:", messages[0]["content"])
    print("\n模型响应（流式）:")
    
    try:
        async for chunk in call_llm_api_with_tools_stream(
            messages=messages,
            tools=tools,
            request_id="streaming-example",
            model_name="deepseek-chat"
        ):
            chunk_type = chunk.get("type")
            
            if chunk_type == "content":
                print(chunk.get("content", ""), end="", flush=True)
            
            elif chunk_type == "tool_calls":
                print("\n\n工具调用:")
                for tool_call in chunk.get("tool_calls", []):
                    print(f"  - {tool_call['function']['name']}")
                    print(f"    参数: {tool_call['function']['arguments']}")
            
            elif chunk_type == "usage":
                print(f"\n\nToken 使用: {chunk.get('usage')}")
            
            elif chunk_type == "error":
                print(f"\n错误: {chunk.get('error')}")
        
        print()
        
    except Exception as e:
        print(f"\n调用失败: {str(e)}")


def example_save_tools_to_file():
    """示例7: 将工具定义保存到文件"""
    print("\n" + "=" * 60)
    print("示例7: 将工具定义保存到文件")
    print("=" * 60)
    
    # 转换常用的工具
    common_tools = [
        "SerperSearchNode",
        "WeatherForecastNode",
        "FileReadNode",
        "FileWriteNode",
        "PythonExecuteNode"
    ]
    
    tools = load_tools_from_yaml(node_names=common_tools)
    
    # 保存到文件
    output_file = Path(__file__).parent / "common_tools.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(tools, f, ensure_ascii=False, indent=2)
    
    print(f"\n已将 {len(tools)} 个工具定义保存到: {output_file}")
    print("\n工具列表:")
    for tool in tools:
        print(f"  - {tool['function']['name']}")


def main():
    """主函数"""
    print("\n工具转换器使用示例\n")
    
    # 运行同步示例
    example_convert_all_tools()
    example_convert_specific_tools()
    example_exclude_tools()
    example_get_single_tool()
    example_save_tools_to_file()
    
    # 运行异步示例
    print("\n" + "=" * 60)
    print("运行异步示例（需要 API 配置）")
    print("=" * 60)
    
    try:
        asyncio.run(example_use_with_llm())
        asyncio.run(example_streaming_with_tools())
    except Exception as e:
        print(f"\n异步示例跳过: {str(e)}")
        print("提示: 如需运行异步示例，请确保已正确配置 API")


if __name__ == "__main__":
    main()