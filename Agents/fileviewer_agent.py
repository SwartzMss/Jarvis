from typing import List, Dict, Any
import asyncio
from agents import Agent, ModelSettings
from agent_lifecycle_hooks import default_hooks
from model_provider import model_provider, MODEL_NAME
from mcp_server_manager import mcp_server_manager

async def create_fileviewer_agent():
    # 获取 fileviewer server
    fileviewer = mcp_server_manager.get_server("fileviewer")
    if not fileviewer:
        raise RuntimeError("FileViewer server 未初始化")
    
    agent = Agent(
        name="FileViewer",
        instructions="""你是一个文件查看助手，可以帮助用户使用系统默认程序打开和查看各种类型的文件。
        你可以：
        1. 使用系统默认程序打开文件，使用open_file工具
        2. 关闭已打开的文件窗口，使用close_file工具
        3. 支持的文件类型包括：
           - 文本文件（.txt, .md, .py等）
           - 图片文件（.jpg, .png, .gif等）
           - 视频文件（.mp4, .avi等）
           - 文档文件（.pdf, .doc, .docx等）
        
        请根据用户的需求，执行相应的文件查看操作。""",
        mcp_servers=[fileviewer],
        hooks=default_hooks,
        model=model_provider.get_model(MODEL_NAME),
        model_settings=ModelSettings(temperature=0.3, top_p=0.9),
    )
    return agent

# 创建工具
class FileViewerTool:
    def __init__(self):
        self._tool = None
        
    async def get_tool(self):
        if self._tool is None:
            agent = await create_fileviewer_agent()
            self._tool = agent.as_tool(
                tool_name="fileviewer",
                tool_description="使用系统默认程序打开和查看文件的工具。支持打开各种类型的文件，包括文本文件、图片、视频、文档等，并可以关闭已打开的文件窗口。"
            )
        return self._tool

fileviewer_tool = FileViewerTool() 