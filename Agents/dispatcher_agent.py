import asyncio
from agents import Agent, ModelSettings, function_tool, AgentHooks
import os

from model_provider import model_provider, MODEL_NAME, client  
from mcp_server_manager import mcp_server_manager
from agent_lifecycle_hooks import default_hooks
from browser_agent import browser_tool
from local_search_agent import local_search_tool
from filesystem_agent import filesystem_tool
from mongodb_agent import mongodb_tool
from fileviewer_agent import fileviewer_tool
from excel_agent import create_excel_agent

async def create_dispatcher_agent():
    # 获取所有工具
    tools = [
        await local_search_tool.get_tool(),
        await browser_tool.get_tool(),
        await filesystem_tool.get_tool(),
        await mongodb_tool.get_tool(),
        await fileviewer_tool.get_tool(),
    ]

    excel_agent = create_excel_agent()

    agent = Agent(
        name="AI Assistant",
        instructions="""你是一个专业的AI助手，具有以下特点：
            1. 角色定位：
            - 你是一个多功能的智能助手，能够处理各种任务和问题
            - 你具有专业的技术背景，能够理解和处理编程相关的问题
            - 你始终保持专业、友好和耐心的态度

            2. 交互方式：
            - 主动询问：当信息不完整时，主动询问用户以获取更多细节
            - 分步指导：对于复杂任务，提供分步骤的指导
            - 简洁回复：保持回复简洁明了，避免冗长
        """,
        model=model_provider.get_model(MODEL_NAME),
        model_settings=ModelSettings(temperature=0.3, top_p=0.9),
        hooks=default_hooks,
        handoffs=[excel_agent],
        tools=tools,
    )
    return agent