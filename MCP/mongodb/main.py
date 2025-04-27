from mcp.server.fastmcp import FastMCP
from pymongo import MongoClient
from bson.json_util import dumps
from typing import Dict, List, Optional, Any 
import argparse
import logging
import os
import sys

# ---------------------------------------------------------------------------
# 日志：全部写到 stderr / 文件，严禁写到 stdout
# ---------------------------------------------------------------------------
LOG_FMT = "%(asctime)s - %(levelname)s - %(message)s"
logger = logging.getLogger("mongodb_server")
logger.setLevel(logging.DEBUG)
logger.handlers.clear()

console_handler = logging.StreamHandler(sys.stderr)      # 关键：stderr
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(LOG_FMT))
logger.addHandler(console_handler)

file_handler = logging.FileHandler("mongodb_server.log", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - "
                                            "%(levelname)s - %(message)s"))
logger.addHandler(file_handler)

logger.propagate = False

# ---------------------------------------------------------------------------
# MCP 服务实例
# ---------------------------------------------------------------------------
mcp = FastMCP(
    name="MongoDB MCP Server",
    description="Provide CRUD & aggregation operations for a single MongoDB "
                "database via MCP",
    dependencies=["pymongo"]
)

# ---------------------------------------------------------------------------
# MongoDB Client 封装
# ---------------------------------------------------------------------------
class MongoDBClient:
    def __init__(self, uri: str, read_only: bool = False) -> None:
        self.client = MongoClient(uri, uuidRepresentation="standard")
        self.read_only = read_only
        # 解析库名；没有就默认 admin
        self.db_name = (uri.split("/", 3)[-1].split("?", 1)[0] or "admin")

    # -- helpers ------------------------------------------------------------
    def _db(self):
        return self.client[self.db_name]

    def _coll(self, name: Optional[str]):
        if name:
            return self._db()[name]

        # 未指定集合 → 第一个集合
        names = self._db().list_collection_names()
        if not names:
            raise ValueError("Database contains no collections")
        return self._db()[names[0]]

# 全局客户端
mongo_client: Optional[MongoDBClient] = None

# ---------------------------------------------------------------------------
# MCP TOOLS
# ---------------------------------------------------------------------------
@mcp.tool()
def connect(uri: str, read_only: bool = False) -> str:
    """连接到 MongoDB。"""
    global mongo_client
    try:
        logger.info("Connecting to %s (read_only=%s)", uri, read_only)
        mongo_client = MongoDBClient(uri, read_only)
        # 探活
        mongo_client.client.admin.command("ping")
        return "Successfully connected"
    except Exception as exc:
        mongo_client = None
        logger.exception("Connect failed")
        return f"Error: {exc}"

@mcp.tool()
def disconnect() -> str:
    """断开 MongoDB 连接。"""
    global mongo_client
    if mongo_client:
        mongo_client.client.close()
        mongo_client = None
        return "Disconnected"
    return "Not connected"

@mcp.tool()
def query(
    collection: Optional[str] = None,
    filter: Optional[Dict[str, Any]] = None,
    projection: Optional[Dict[str, int]] = None,
    limit: Optional[int] = None,
    skip: Optional[int] = None,
    sort: Optional[Dict[str, int]] = None
) -> str:
    """
    执行 MongoDB 查询
    """
    if not mongo_client:
        return "Error: Not connected"

    try:
        coll = mongo_client._coll(collection)
        cursor = coll.find(filter or {}, projection)

        if sort:
            cursor = cursor.sort(list(sort.items()))
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)

        return dumps(list(cursor))
    except Exception as exc:
        logger.exception("Query failed")
        return f"Error: {exc}"

@mcp.tool()
def insert(collection: str = None, documents: List[Dict] = None) -> str:
    """插入文档。"""
    if not mongo_client:
        return "Error: Not connected"
    if mongo_client.read_only:
        return "Error: server is read-only"
    if not documents:
        return "Error: no documents provided"

    try:
        res = mongo_client._coll(collection).insert_many(documents)
        return f"Inserted {len(res.inserted_ids)} documents"
    except Exception as exc:
        logger.exception("Insert failed")
        return f"Error: {exc}"

@mcp.tool()
def update(collection: str = None,
           filter: Dict = None,
           update: Dict = None,
           upsert: bool = False,
           multi: bool = False) -> str:
    """更新文档。"""
    if not mongo_client:
        return "Error: Not connected"
    if mongo_client.read_only:
        return "Error: server is read-only"
    if not (filter and update):
        return "Error: filter & update required"

    try:
        coll = mongo_client._coll(collection)
        if multi:
            res = coll.update_many(filter, update, upsert=upsert)
        else:
            res = coll.update_one(filter, update, upsert=upsert)
        return f"matched={res.matched_count}, modified={res.modified_count}, upserted_id={res.upserted_id}"
    except Exception as exc:
        logger.exception("Update failed")
        return f"Error: {exc}"

@mcp.tool()
def delete(collection: str = None, filter: Dict = None) -> str:
    """删除文档。"""
    if not mongo_client:
        return "Error: Not connected"
    if mongo_client.read_only:
        return "Error: server is read-only"
    if not filter:
        return "Error: filter required"

    try:
        res = mongo_client._coll(collection).delete_many(filter)
        return f"Deleted {res.deleted_count} documents"
    except Exception as exc:
        logger.exception("Delete failed")
        return f"Error: {exc}"

@mcp.tool()
def aggregate(collection: str = None, pipeline: List[Dict] = None) -> str:
    """聚合查询。"""
    if not mongo_client:
        return "Error: Not connected"
    if not pipeline:
        return "Error: pipeline required"

    try:
        res = mongo_client._coll(collection).aggregate(pipeline)
        return dumps(list(res))
    except Exception as exc:
        logger.exception("Aggregate failed")
        return f"Error: {exc}"

# ---------------------------------------------------------------------------
# 自动连接（读取启动参数）
# ---------------------------------------------------------------------------
def _auto_connect():
    parser = argparse.ArgumentParser(description="MongoDB MCP Server")
    parser.add_argument("--uri", default="mongodb://localhost:27017/family",
                        help="MongoDB URI (default: %(default)s)")
    parser.add_argument("--read-only", action="store_true",
                        help="Enable read-only mode")
    args, _ = parser.parse_known_args()

    logger.info("Auto-connecting with URI=%s  read_only=%s", args.uri, args.read_only)
    res = connect(args.uri, args.read_only)
    if not res.startswith("Successfully"):
        logger.error("Auto connect failed: %s", res)
        sys.exit(1)

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    _auto_connect()
    logger.info("MCP server started (pid=%s, cwd=%s)", os.getpid(), os.getcwd())
    try:
        mcp.run()        # FastMCP 会独占 stdout
    except Exception:
        logger.exception("MCP server stopped unexpectedly")
        raise