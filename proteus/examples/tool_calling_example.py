"""
工具调用示例
演示如何使用 call_llm_api_with_tools 和 call_llm_api_with_tools_stream
"""

import asyncio
import json
from src.api.llm_api import call_llm_api_with_tools, call_llm_api_with_tools_stream


# 定义工具
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather of a location, the user should supply a location first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. San Francisco, CA",
                    }
                },
                "required": ["location"]
            },
        }
    },
]


async def example_non_streaming():
    """非流式工具调用示例"""
    print("=" * 50)
    print("非流式工具调用示例")
    print("=" * 50)
    
    # 第一轮对话：用户提问
    messages = [{"role": "user", "content": "How's the weather in Hangzhou, Zhejiang?"}]
    print(f"User>\t {messages[0]['content']}")
    
    # 调用 API，模型会返回工具调用
    message, usage = await call_llm_api_with_tools(
        messages=messages,
        tools=tools,
        request_id="example-001",
        model_name="deepseek-chat"
    )
    
    print(f"\n模型响应:")
    print(f"  Content: {message.get('content')}")
    print(f"  Tool Calls: {message.get('tool_calls')}")
    print(f"  Usage: {usage}")
    
    # 如果模型调用了工具
    if message.get('tool_calls'):
        tool_call = message['tool_calls'][0]
        print(f"\n工具调用详情:")
        print(f"  ID: {tool_call['id']}")
        print(f"  Function: {tool_call['function']['name']}")
        print(f"  Arguments: {tool_call['function']['arguments']}")
        
        # 将模型的响应添加到消息历史
        messages.append(message)
        
        # 模拟工具执行结果
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call['id'],
            "content": "24℃"
        })
        
        # 第二轮对话：发送工具执行结果
        message, usage = await call_llm_api_with_tools(
            messages=messages,
            tools=tools,
            request_id="example-002",
            model_name="deepseek-chat"
        )
        
        print(f"\nModel>\t {message.get('content')}")
        print(f"Usage: {usage}")


async def example_streaming():
    """流式工具调用示例"""
    print("\n" + "=" * 50)
    print("流式工具调用示例")
    print("=" * 50)
    
    # 第一轮对话：用户提问
    messages = [{"role": "user", "content": "What's the weather like in Beijing?"}]
    print(f"User>\t {messages[0]['content']}")
    
    print("\n模型响应（流式）:")
    
    # 用于收集完整的响应
    full_content = ""
    tool_calls = None
    usage = None
    
    # 调用流式 API
    async for chunk in call_llm_api_with_tools_stream(
        messages=messages,
        tools=tools,
        request_id="example-stream-001",
        model_name="deepseek-chat"
    ):
        chunk_type = chunk.get("type")
        
        if chunk_type == "content":
            content = chunk.get("content", "")
            full_content += content
            print(content, end="", flush=True)
        
        elif chunk_type == "tool_calls":
            tool_calls = chunk.get("tool_calls")
            print(f"\n\n工具调用: {json.dumps(tool_calls, ensure_ascii=False, indent=2)}")
        
        elif chunk_type == "usage":
            usage = chunk.get("usage")
            print(f"\nUsage: {usage}")
        
        elif chunk_type == "error":
            print(f"\n错误: {chunk.get('error')}")
    
    # 如果模型调用了工具
    if tool_calls:
        tool_call = tool_calls[0]
        
        # 构建完整的消息对象
        assistant_message = {
            "role": "assistant",
            "content": full_content if full_content else None,
            "tool_calls": tool_calls
        }
        messages.append(assistant_message)
        
        # 模拟工具执行结果
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call['id'],
            "content": "15℃, 晴天"
        })
        
        # 第二轮对话：发送工具执行结果
        print("\n\n第二轮响应（流式）:")
        print("Model>\t ", end="")
        
        async for chunk in call_llm_api_with_tools_stream(
            messages=messages,
            tools=tools,
            request_id="example-stream-002",
            model_name="deepseek-chat"
        ):
            chunk_type = chunk.get("type")
            
            if chunk_type == "content":
                print(chunk.get("content", ""), end="", flush=True)
            
            elif chunk_type == "usage":
                print(f"\n\nUsage: {chunk.get('usage')}")
            
            elif chunk_type == "error":
                print(f"\n错误: {chunk.get('error')}")
        
        print()  # 换行


async def main():
    """主函数"""
    try:
        # 运行非流式示例
        await example_non_streaming()
        
        # 运行流式示例
        await example_streaming()
        
    except Exception as e:
        print(f"\n发生错误: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())