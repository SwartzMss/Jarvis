import asyncio
from agents import Agent, ModelSettings, function_tool, AgentHooks
import os

from model_provider import model_provider, MODEL_NAME, client  
from mcp_server_manager import mcp_server_manager


async def create_dispatcher_agent():
    # 获取所有工具
    tools_list = await mcp_server_manager.get_all_tools()
    
    # 构造 Agent
    agent = Agent(
        name="AI Assistant",
        instructions="你是一个智能助手",
        model=model_provider.get_model(MODEL_NAME),
        model_settings=ModelSettings(temperature=0.3, top_p=0.9),
        tools=tools_list,
    )
    return agent