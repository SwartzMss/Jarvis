from typing import List, Dict, Any
import asyncio
from agents import Agent, ModelSettings
from agent_lifecycle_hooks import default_hooks
from model_provider import model_provider, MODEL_NAME
from mcp_server_manager import mcp_server_manager

async def create_filesystem_agent():
    # 获取 filesystem server
    filesystem = mcp_server_manager.get_server("filesystem")
    if not filesystem:
        raise RuntimeError("Filesystem server 未初始化")
    
    agent = Agent(
        name="Filesystem",
        instructions="""你是一个文件系统服务助手，可以帮助用户管理文件系统中的文件和目录。
        你可以：
        1. 列出目录内容
        2. 创建/删除文件或目录
        3. 读取/写入文件内容
        4. 移动/复制文件或目录
        
        请根据用户的需求，执行相应的文件操作。""",
        mcp_servers=[filesystem],
        hooks=default_hooks,
        model=model_provider.get_model(MODEL_NAME),
        model_settings=ModelSettings(temperature=0.3, top_p=0.9),
    )
    return agent

# 创建工具
class FilesystemTool:
    def __init__(self):
        self._tool = None
        
    async def get_tool(self):
        if self._tool is None:
            agent = await create_filesystem_agent()
            self._tool = agent.as_tool(
                tool_name="filesystem",
                tool_description="管理本地文件系统的工具。可以执行文件/目录的创建、删除、读取、写入等操作。支持列出目录内容、读取文件内容、写入文件内容、创建目录、删除文件或目录等操作。"
            )
        return self._tool

filesystem_tool = FilesystemTool()