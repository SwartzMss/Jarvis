from typing import List, Dict, Any
from agents import Agent, ModelSettings
import asyncio
from agent_lifecycle_hooks import default_hooks
from model_provider import model_provider, MODEL_NAME
from mcp_server_manager import mcp_server_manager

async def create_local_search_agent():
    # 获取 localSearch server
    local_search = mcp_server_manager.get_server("localSearch")
    if not local_search:
        raise RuntimeError("LocalSearch server 未初始化")
    
    agent = Agent(
        name="LocalSearch",
        instructions="""你是一个本地搜索服务助手，可以帮助用户搜索本地文件系统中的内容。
        你可以：
        1. 根据关键词搜索文件内容
        2. 根据文件路径搜索
        3. 根据文件类型搜索
        4. 组合多个条件进行搜索
        
        请根据用户的需求，选择合适的搜索方式并提供结果。
        
        注意：
        1. 搜索结果默认限制为前10条
        2. 如果结果超过10条，会自动保存到本地文件
        3. 可以使用 files_only 参数只搜索文件名
        4. 可以使用 glob 参数限制文件类型""",
        mcp_servers=[local_search],
        hooks=default_hooks,
        model=model_provider.get_model(MODEL_NAME),
        model_settings=ModelSettings(temperature=0.3, top_p=0.9),
    )
    return agent

# 创建工具
class LocalSearchTool:
    def __init__(self):
        self._tool = None
        
    async def get_tool(self):
        if self._tool is None:
            agent = await create_local_search_agent()
            self._tool = agent.as_tool(
                tool_name="local_search",
                tool_description="""在本地文件系统中搜索内容。可以按关键词、文件路径、文件类型等进行搜索，支持组合条件。
    
    参数说明：
    - query: 搜索关键词（必填）
    - path: 搜索路径（默认为当前目录）
    - files_only: 是否只搜索文件名（默认false）
    - glob: 文件类型过滤（如 ["*.py", "!*.log"]）
    - max_results: 最大返回结果数（默认10）
    - ignore_case: 是否忽略大小写（默认true）
    - fixed_strings: 是否使用固定字符串匹配（默认false）
    - word_regexp: 是否整词匹配（默认false）
    
    返回结果：
    - 成功：返回JSON格式的结果，包含：
      - total: 总结果数
      - results: 结果列表（最多10条），每个结果包含文件路径、行号和内容摘要
      - truncated: 是否被截断
      - result_file: 如果结果被截断，则包含保存完整结果的临时文件路径
    - 失败：返回错误信息
    
    注意事项：
    1. 结果默认限制为前10条，避免返回过多数据
    2. 如果结果超过10条，会自动保存到本地临时文件
    3. 可以使用 files_only 和 glob 参数来优化搜索
    4. 对于大量结果，建议分多次搜索，每次使用不同的条件"""
            )
        return self._tool

local_search_tool = LocalSearchTool()
