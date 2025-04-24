import asyncio
from agents import Agent, ModelSettings, function_tool, AgentHooks
from agents.mcp import MCPServerStdio
from openai import AsyncOpenAI
import os

from model_provider import model_provider, MODEL_NAME, client  
from .mcp_server_manager import mcp_server_manager

class BrowserAgentHooks(AgentHooks):
    def __init__(self):
        self.visited_pages = []
        self.extracted_content = []

    async def on_start(self, context, agent):
        print(f"[浏览器代理] {agent.name} 开始执行...")

    async def on_end(self, context, agent, output):
        print(f"[浏览器代理] {agent.name} 完成执行...")

async def create_browser_agent():
    # 获取 playwright server
    playwright = mcp_server_manager.get_server("playwright")
    if not playwright:
        raise RuntimeError("Playwright server 未初始化")
    
    hooks = BrowserAgentHooks()
    agent = Agent(
        name="WebBrowser",
        instructions="你是一个智能网页浏览代理，可以帮助用户浏览和提取网页内容。你可以：\n"
                    "1. 访问指定的网页\n"
                    "2. 提取页面上的文本内容\n"
                    "3. 点击页面上的链接和按钮\n"
                    "4. 填写表单\n"
                    "5. 截图保存页面\n"
                    "6. 提取特定元素的内容",
        mcp_servers=[playwright],
        hooks=hooks,
        model=model_provider.get_model(MODEL_NAME),
        model_settings=ModelSettings(temperature=0.3, top_p=0.9),
    )
    return agent, playwright


