#!/usr/bin/env python3
"""
智能体历史信息功能示例

这个示例展示了如何使用带有历史迭代信息的Agent功能。
Agent会从Redis中读取最近5轮的历史信息，并在每次迭代时将新的信息保存到Redis中。
"""

import asyncio
import sys
import os

# 添加项目根目录到sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.agent.agent import Agent, AgentConfiguration
from src.agent.base_agent import ScratchpadItem
from src.manager.multi_agent_manager import TeamRole
from src.nodes.node_config import NodeConfigManager

async def main():
    print("=== 智能体历史信息功能示例 ===\n")
    
    # 初始化节点配置管理器
    config_manager = NodeConfigManager.get_instance()
    tools = config_manager.get_tools()
    
    # 模拟一个简单的提示模板
    prompt_template = """
你是一个智能助手。请根据以下信息完成任务：

当前时间：$CURRENT_TIME
任务：$query
上下文：$context

可用工具：
$tools

工具名称：$tool_names

请使用XML格式返回你的思考和行动：
<thinking>你的思考过程</thinking>
<tool>
<name>工具名称</name>
<params>工具参数</params>
</tool>
"""
    
    # 创建Agent配置
    config = AgentConfiguration(
        role_type=TeamRole.PLANNER,
        role_description="规划助手",
        agent_description="负责制定计划的智能助手",
        prompt_template=prompt_template,
        model_name="deepseek-chat",
        termination_conditions=[],
        tools=["chat"],  # 使用基础的chat工具
        max_iterations=3,
        llm_timeout=30,
        conversation_id="example_conversation_001",  # 关键：指定会话ID
        historical_scratchpad_items=[]  # 历史信息会自动从Redis加载
    )
    
    print(f"创建Agent配置，会话ID：{config.conversation_id}")
    print(f"历史信息参数已配置：{len(config.historical_scratchpad_items)} 条\n")
    
    # 创建Agent实例
    agent = Agent(
        tools=config.tools,
        prompt_template=config.prompt_template,
        role_type=config.role_type,
        model_name=config.model_name,
        termination_conditions=config.termination_conditions,
        description=config.agent_description,
        max_iterations=config.max_iterations,
        llm_timeout=config.llm_timeout,
        conversation_id=config.conversation_id  # 传递会话ID
    )
    
    print(f"Agent创建成功！")
    print(f"- Agent ID: {agent.agentcard.agentid}")
    print(f"- 模型: {agent.model_name}")
    print(f"- 会话ID: {agent.conversation_id}")
    print(f"- 初始化时加载的历史信息条数: {len(agent.scratchpad_items)}")
    
    # 显示加载的历史信息
    if agent.scratchpad_items:
        print("\n=== 从Redis加载的历史信息 ===")
        for i, item in enumerate(agent.scratchpad_items):
            print(f"{i+1}. 思考: {item.thought}")
            print(f"   操作: {item.action}")
            print(f"   结果: {item.observation}")
            print(f"   是原始查询: {item.is_origin_query}")
            print()
    else:
        print("\n=== 没有找到历史信息，这是第一次对话 ===\n")
    
    # 执行任务
    try:
        print("=== 开始执行任务 ===")
        query = "请帮我制定一个学习Python的计划"
        chat_id = "example_chat_001"
        
        print(f"任务: {query}")
        print(f"聊天ID: {chat_id}")
        print(f"会话ID: {agent.conversation_id}")
        print()
        
        # 运行Agent（注意：这里需要有效的LLM配置）
        # result = await agent.run(query, chat_id, stream=False)
        # print(f"执行结果: {result}")
        
        print("注意：实际执行需要配置有效的LLM服务")
        print("这个示例主要展示了历史信息功能的配置和使用方式")
        
        # 模拟保存一些数据到Redis
        from src.utils.redis_cache import RedisCache
        import json
        
        try:
            redis_cache = RedisCache()
            
            # 模拟保存一些历史数据
            sample_items = [
                ScratchpadItem(
                    thought="用户询问如何学习Python",
                    action="chat",
                    observation="我理解了用户的需求，准备制定学习计划",
                    is_origin_query=True
                ),
                ScratchpadItem(
                    thought="分析用户的技术水平和学习目标",
                    action="chat", 
                    observation="建议从基础语法开始，逐步进阶到项目实践"
                )
            ]
            
            redis_key = f"conversation_history:{config.conversation_id}"
            for item in sample_items:
                item_json = json.dumps(item.to_dict(), ensure_ascii=False)
                redis_cache.lpush(redis_key, item_json)
                
            print(f"\n=== 示例数据已保存到Redis ===")
            print(f"Redis键: {redis_key}")
            print(f"保存了 {len(sample_items)} 条示例数据")
            
            # 读取验证
            saved_data = redis_cache.lrange(redis_key, 0, 4)
            print(f"验证：从Redis读取到 {len(saved_data)} 条数据")
            
        except Exception as e:
            print(f"Redis操作失败（这是正常的，如果没有配置Redis）: {e}")
        
    except Exception as e:
        print(f"执行失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== 示例完成 ===")
    
    print("""
=== 功能总结 ===

1. Agent初始化时会自动从Redis加载历史信息：
   - 使用conversation_id作为Redis键的标识符
   - 从Redis列表中获取最近5轮的历史记录
   - 将历史数据转换为ScratchpadItem对象

2. Agent运行时会自动保存迭代信息：
   - 每次思考和操作都会保存到Redis
   - 初始查询也会被保存
   - 错误信息也会被记录

3. 使用方式：
   - 创建Agent时传递conversation_id参数
   - Redis存储格式：conversation_history:{conversation_id}
   - 数据按时间顺序存储，最新的在前面

4. 配置要求：
   - 需要配置Redis连接信息
   - REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD等环境变量
""")

if __name__ == "__main__":
    asyncio.run(main())