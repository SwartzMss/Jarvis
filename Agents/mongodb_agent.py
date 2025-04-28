from typing import List, Dict, Any, Optional
from agents import Agent, Tool, ModelSettings
from agent_lifecycle_hooks import default_hooks
from model_provider import model_provider, MODEL_NAME
from mcp_server_manager import mcp_server_manager

async def create_mongodb_agent():
    # 获取 mongodb server
    mongodb = mcp_server_manager.get_server("mongodb")
    if not mongodb:
        raise RuntimeError("MongoDB server 未初始化")
    
    agent = Agent(
        name="MongoDB",
        instructions="""你是一个 MongoDB 数据库服务助手，可以帮助用户管理 MongoDB 数据库。
        你可以：
        1. 执行数据库查询
        2. 插入/更新/删除文档
        3. 创建/删除集合
        4. 执行聚合操作
        
        请根据用户的需求，执行相应的数据库操作。""",
        mcp_servers=[mongodb],
        hooks=default_hooks,
        model=model_provider.get_model(MODEL_NAME),
        model_settings=ModelSettings(temperature=0.3, top_p=0.9),
    )
    return agent

# 创建工具
class MongoDBTool:
    def __init__(self):
        self._tool = None
        
    async def get_tool(self):
        if self._tool is None:
            agent = await create_mongodb_agent()
            self._tool = agent.as_tool(
                tool_name="mongodb",
                tool_description="""MongoDB 数据库管理工具。可以执行数据库查询、插入/更新/删除文档、创建/删除集合、执行聚合操作等。

                数据库结构说明：
                1. 用户信息（users 集合）：
                - 存储用户基本信息
                - 字段结构：
                    - _id: ObjectId，主键
                    - 姓名: string
                    - 小名: string
                    - 电话: string
                    - 出生日期: string
                - 示例数据：
                    {'_id': ObjectId('680e3e0f695767c53af370fa'), '姓名': '史悦锋', '小名': '史帅', '电话': 'xxxx', '出生日期': 'xx'}

                2. 媒体文件（GridFS）：
                - 存储图片、视频等二进制文件
                - 文件信息存储在 fs.files 集合中
                - 文件内容分块存储在 fs.chunks 集合中
                - 示例文件信息：
                    {'_id': ObjectId('...'), 'filename': 'image.jpg', 'contentType': 'image/jpeg', 'length': 1024, 'uploadDate': ISODate('...')}

                使用说明：
                1. 查询用户信息：
                - 默认查询 users 集合
                - 如果未指定 collection 参数，将自动查询 users 集合
                - 如需查询其他集合，请明确指定 collection 参数

                2. 查询媒体文件：
                - 使用 find_files 函数：根据标签查询文件列表
                - 使用 get_file 函数：根据文件ID获取单个文件
                - 保存文件：使用 store_file 函数，需指定本地文件路径
                - 文件默认保存在 ./downloads 目录下
                - 支持的文件类型：jpg、png、mp4 等

                3. 其他集合可根据实际业务自定义字段。
                """
            )
        return self._tool

mongodb_tool = MongoDBTool()

