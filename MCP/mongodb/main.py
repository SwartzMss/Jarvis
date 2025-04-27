from mcp.server.fastmcp import FastMCP
import logging
from pymongo import MongoClient
from typing import Dict, Any, List, Optional
import json
from bson import ObjectId
from bson.json_util import dumps, loads
import sys
import os
import argparse

# 配置日志
logger = logging.getLogger("mongodb_server")
logger.setLevel(logging.DEBUG)

# 清除现有的处理器
logger.handlers = []

# 添加控制台处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# 添加文件处理器
file_handler = logging.FileHandler('mongodb_server.log')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# 确保日志不会被其他处理器捕获
logger.propagate = False

logger.info("Starting MongoDB MCP Server...")
logger.debug(f"Current working directory: {os.getcwd()}")
logger.debug(f"Environment variables: {dict(os.environ)}")

# 初始化 FastMCP 服务
mcp = FastMCP(
    name="MongoDB MCP Server",
    description="Tool for MongoDB database operations",
    dependencies=["pymongo"]
)

class MongoDBClient:
    def __init__(self, uri: str, read_only: bool = False):
        self.client = MongoClient(uri)
        self.read_only = read_only
        
    def get_database(self, db_name: str):
        return self.client[db_name]
        
    def get_collection(self, db_name: str, collection_name: str):
        return self.get_database(db_name)[collection_name]

# 全局 MongoDB 客户端实例
mongo_client: Optional[MongoDBClient] = None

@mcp.tool()
def connect(uri: str, read_only: bool = False) -> str:
    """
    连接到 MongoDB 数据库
    
    参数：
      - uri: MongoDB 连接字符串
      - read_only: 是否只读模式
    
    返回：
      连接状态
    """
    try:
        global mongo_client
        logger.info(f"Attempting to connect to MongoDB with URI: {uri}")
        mongo_client = MongoDBClient(uri, read_only)
        # 测试连接
        mongo_client.client.server_info()
        logger.info("Successfully connected to MongoDB")
        return "Successfully connected to MongoDB"
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}")
        mongo_client = None
        return f"Error: {str(e)}"

@mcp.tool()
def query(collection: str, filter: Dict = None, projection: Dict = None, 
         limit: int = None, skip: int = None, sort: Dict = None) -> str:
    """
    执行 MongoDB 查询
    
    参数：
      - collection: 集合名称
      - filter: 查询条件
      - projection: 投影
      - limit: 限制返回数量
      - skip: 跳过数量
      - sort: 排序条件
    
    返回：
      查询结果
    """
    try:
        if not mongo_client:
            return "Error: Not connected to MongoDB"
            
        db_name, collection_name = collection.split('.')
        coll = mongo_client.get_collection(db_name, collection_name)
        
        cursor = coll.find(filter or {}, projection or {})
        
        if sort:
            cursor = cursor.sort(sort)
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
            
        results = list(cursor)
        return dumps(results)
    except Exception as e:
        logger.exception("Failed to execute query")
        return f"Error: {str(e)}"

@mcp.tool()
def insert(collection: str, documents: List[Dict]) -> str:
    """
    插入文档
    
    参数：
      - collection: 集合名称
      - documents: 要插入的文档列表
    
    返回：
      插入结果
    """
    try:
        if not mongo_client:
            return "Error: Not connected to MongoDB"
        if mongo_client.read_only:
            return "Error: Server is in read-only mode"
            
        db_name, collection_name = collection.split('.')
        coll = mongo_client.get_collection(db_name, collection_name)
        
        result = coll.insert_many(documents)
        return f"Successfully inserted {len(result.inserted_ids)} documents"
    except Exception as e:
        logger.exception("Failed to insert documents")
        return f"Error: {str(e)}"

@mcp.tool()
def update(collection: str, filter: Dict, update: Dict, 
          upsert: bool = False, multi: bool = False) -> str:
    """
    更新文档
    
    参数：
      - collection: 集合名称
      - filter: 查询条件
      - update: 更新操作
      - upsert: 是否插入新文档
      - multi: 是否更新多个文档
    
    返回：
      更新结果
    """
    try:
        if not mongo_client:
            return "Error: Not connected to MongoDB"
        if mongo_client.read_only:
            return "Error: Server is in read-only mode"
            
        db_name, collection_name = collection.split('.')
        coll = mongo_client.get_collection(db_name, collection_name)
        
        result = coll.update_many(filter, update, upsert=upsert)
        return f"Matched {result.matched_count} documents, modified {result.modified_count} documents"
    except Exception as e:
        logger.exception("Failed to update documents")
        return f"Error: {str(e)}"

@mcp.tool()
def delete(collection: str, filter: Dict) -> str:
    """
    删除文档
    
    参数：
      - collection: 集合名称
      - filter: 查询条件
    
    返回：
      删除结果
    """
    try:
        if not mongo_client:
            return "Error: Not connected to MongoDB"
        if mongo_client.read_only:
            return "Error: Server is in read-only mode"
            
        db_name, collection_name = collection.split('.')
        coll = mongo_client.get_collection(db_name, collection_name)
        
        result = coll.delete_many(filter)
        return f"Successfully deleted {result.deleted_count} documents"
    except Exception as e:
        logger.exception("Failed to delete documents")
        return f"Error: {str(e)}"

@mcp.tool()
def aggregate(collection: str, pipeline: List[Dict]) -> str:
    """
    执行聚合操作
    
    参数：
      - collection: 集合名称
      - pipeline: 聚合管道
    
    返回：
      聚合结果
    """
    try:
        if not mongo_client:
            return "Error: Not connected to MongoDB"
            
        db_name, collection_name = collection.split('.')
        coll = mongo_client.get_collection(db_name, collection_name)
        
        results = list(coll.aggregate(pipeline))
        return dumps(results)
    except Exception as e:
        logger.exception("Failed to execute aggregation")
        return f"Error: {str(e)}"

# 在 mcp.run() 之前添加自动连接逻辑
# 从启动参数中获取 MongoDB 连接信息
parser = argparse.ArgumentParser(description='MongoDB MCP Server')
parser.add_argument('--uri', type=str, required=True, help='MongoDB connection URI')
parser.add_argument('--read-only', action='store_true', help='Enable read-only mode')
args = parser.parse_args()

uri = args.uri
read_only = args.read_only

logger.debug(f"MongoDB URI: {uri}")
logger.debug(f"Read-only mode: {read_only}")

logger.info(f"Received MongoDB URI: {uri}")
if read_only:
    logger.info("Read-only mode enabled")
# 自动连接
logger.info("Attempting to connect to MongoDB...")
try:
    result = connect(uri, read_only)
    logger.info(f"Connection result: {result}")
    if not result.startswith("Successfully"):
        logger.error("Failed to establish MongoDB connection")
        sys.exit(1)
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {str(e)}")
    sys.exit(1)

if __name__ == "__main__":
    logger.info("Starting MCP server...")
    try:
        mcp.run()
    except Exception as e:
        logger.error(f"Failed to start MCP server: {str(e)}")
        raise 