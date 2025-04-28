from mcp.server.fastmcp import FastMCP
from pymongo import MongoClient
from bson.json_util import dumps
from typing import Dict, List, Optional, Any 
import argparse
import logging
import os
import sys
import json
from gridfs import GridFS
from datetime import datetime
from bson import ObjectId

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
        logger.info(f"初始化 MongoDBClient: uri={uri}, read_only={read_only}")
        self.client = MongoClient(uri, uuidRepresentation="standard")
        self.read_only = read_only
        # 解析库名；没有就默认 admin
        self.db_name = (uri.split("/", 3)[-1].split("?", 1)[0] or "admin")
        logger.info(f"数据库名称: {self.db_name}")
        # 初始化 GridFS
        self.fs = GridFS(self._db())

    # -- helpers ------------------------------------------------------------
    def _db(self):
        return self.client[self.db_name]

    def _coll(self, name: Optional[str]):
        if name:
            logger.info(f"使用指定集合: {name}")
            return self._db()[name]

        # 未指定集合 → 第一个集合
        names = self._db().list_collection_names()
        if not names:
            raise ValueError("Database contains no collections")
        logger.info(f"使用第一个集合: {names[0]}")
        return self._db()[names[0]]

# 全局客户端
mongo_client: Optional[MongoDBClient] = None

# ---------------------------------------------------------------------------
# MCP TOOLS
# ---------------------------------------------------------------------------
@mcp.tool()
def connect(uri: str, read_only: bool = False) -> str:
    """连接到 MongoDB 数据库。用于建立数据库连接，必须在执行其他操作前调用。
    
    参数说明：
    - uri: MongoDB 连接字符串，必填参数，格式如 "mongodb://localhost:27017/dbname"
    - read_only: 是否只读模式，默认为 False，设置为 True 时禁止写入操作
    
    返回值:
    - 成功: "Successfully connected"
    - 失败: "Error: {具体错误信息}"
    """
    global mongo_client
    try:
        logger.info(f"连接参数: uri={uri}, read_only={read_only}")
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
    """断开 MongoDB 数据库连接。用于清理资源，建议在完成所有操作后调用。
    
    返回值:
    - 已断开: "Disconnected"
    - 未连接: "Not connected"
    """
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
    """查询 MongoDB 中的普通文档数据。用于查询非文件类型的结构化数据，如用户信息、配置信息等。
    
    参数说明：
    - collection: 集合名称，默认为 None，表示使用默认集合
    - filter: 查询条件，默认为 None，如 {"age": {"$gt": 18}}
    - projection: 返回字段，默认为 None，如 {"name": 1, "age": 1}
    - limit: 返回结果数量限制，默认为 None
    - skip: 跳过指定数量的结果，默认为 None
    - sort: 排序条件，默认为 None，如 {"age": 1}
    
    返回值:
    - 成功: JSON 字符串，包含查询结果数组
    - 未连接: "Error: Not connected"
    - 失败: "Error: {具体错误信息}"
    
    示例：
    >>> query(collection="users", filter={"age": {"$gt": 18}})
    >>> query(collection="users", projection={"name": 1}, sort={"age": 1}, limit=10)
    """
    logger.info(f"查询参数: collection={collection}, filter={json.dumps(filter, ensure_ascii=False)}, "
                f"projection={json.dumps(projection, ensure_ascii=False)}, limit={limit}, "
                f"skip={skip}, sort={json.dumps(sort, ensure_ascii=False)}")
    
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

        result = dumps(list(cursor))
        logger.info(f"查询结果: {result}")
        return result
    except Exception as exc:
        logger.exception("Query failed")
        return f"Error: {exc}"

@mcp.tool()
def insert(collection: str = None, documents: List[Dict] = None) -> str:
    """插入普通文档数据。用于添加非文件类型的结构化数据，如用户信息、配置信息等。
    
    参数说明：
    - collection: 集合名称，必填参数
    - documents: 要插入的文档列表，必填参数，如 [{"name": "张三", "age": 18}]
    
    返回值:
    - 成功: "Inserted {插入的文档数量} documents"
    - 未连接: "Error: Not connected"
    - 只读模式: "Error: server is read-only"
    - 无文档: "Error: no documents provided"
    - 失败: "Error: {具体错误信息}"
    
    示例：
    >>> insert(collection="users", documents=[{"name": "张三", "age": 18}])
    """
    logger.info(f"插入参数: collection={collection}, documents={json.dumps(documents, ensure_ascii=False)}")
    
    if not mongo_client:
        return "Error: Not connected"
    if mongo_client.read_only:
        return "Error: server is read-only"
    if not documents:
        return "Error: no documents provided"

    try:
        res = mongo_client._coll(collection).insert_many(documents)
        logger.info(f"插入结果: {len(res.inserted_ids)} 个文档")
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
    """更新普通文档数据。用于修改非文件类型的结构化数据，如用户信息、配置信息等。
    
    参数说明：
    - collection: 集合名称，必填参数
    - filter: 更新条件，必填参数，如 {"name": "张三"}
    - update: 更新操作，必填参数，如 {"$set": {"age": 19}}
    - upsert: 是否在文档不存在时插入，默认为 False
    - multi: 是否更新多个文档，默认为 False
    
    返回值:
    - 成功: "matched={匹配的文档数}, modified={修改的文档数}, upserted_id={插入的文档ID}"
    - 未连接: "Error: Not connected"
    - 只读模式: "Error: server is read-only"
    - 缺少参数: "Error: filter & update required"
    - 失败: "Error: {具体错误信息}"
    
    示例：
    >>> update(collection="users", filter={"name": "张三"}, update={"$set": {"age": 19}})
    >>> update(collection="users", filter={"age": {"$lt": 18}}, update={"$set": {"status": "未成年"}}, multi=True)
    """
    logger.info(f"更新参数: collection={collection}, filter={json.dumps(filter, ensure_ascii=False)}, "
                f"update={json.dumps(update, ensure_ascii=False)}, upsert={upsert}, multi={multi}")
    
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
        logger.info(f"更新结果: matched={res.matched_count}, modified={res.modified_count}, "
                   f"upserted_id={res.upserted_id}")
        return f"matched={res.matched_count}, modified={res.modified_count}, upserted_id={res.upserted_id}"
    except Exception as exc:
        logger.exception("Update failed")
        return f"Error: {exc}"

@mcp.tool()
def delete(collection: str = None, filter: Dict = None) -> str:
    """删除普通文档数据。用于移除非文件类型的结构化数据，如用户信息、配置信息等。
    
    参数说明：
    - collection: 集合名称，必填参数
    - filter: 删除条件，必填参数，如 {"name": "张三"}
    
    返回值:
    - 成功: "Deleted {删除的文档数} documents"
    - 未连接: "Error: Not connected"
    - 只读模式: "Error: server is read-only"
    - 缺少参数: "Error: filter required"
    - 失败: "Error: {具体错误信息}"
    
    示例：
    >>> delete(collection="users", filter={"name": "张三"})
    """
    logger.info(f"删除参数: collection={collection}, filter={json.dumps(filter, ensure_ascii=False)}")
    
    if not mongo_client:
        return "Error: Not connected"
    if mongo_client.read_only:
        return "Error: server is read-only"
    if not filter:
        return "Error: filter required"

    try:
        res = mongo_client._coll(collection).delete_many(filter)
        logger.info(f"删除结果: {res.deleted_count} 个文档")
        return f"Deleted {res.deleted_count} documents"
    except Exception as exc:
        logger.exception("Delete failed")
        return f"Error: {exc}"

@mcp.tool()
def aggregate(collection: str = None, pipeline: List[Dict] = None) -> str:
    """执行聚合查询。用于对普通文档数据进行复杂的统计和分析。
    
    参数说明：
    - collection: 集合名称，必填参数
    - pipeline: 聚合管道，必填参数，如 [{"$match": {"age": {"$gt": 18}}}, {"$group": {"_id": "$city", "count": {"$sum": 1}}}]
    
    返回值:
    - 成功: JSON 字符串，包含聚合结果数组
    - 未连接: "Error: Not connected"
    - 缺少参数: "Error: pipeline required"
    - 失败: "Error: {具体错误信息}"
    
    示例：
    >>> aggregate(collection="users", pipeline=[{"$group": {"_id": "$city", "count": {"$sum": 1}}}])
    """
    logger.info(f"聚合参数: collection={collection}, pipeline={json.dumps(pipeline, ensure_ascii=False)}")
    
    if not mongo_client:
        return "Error: Not connected"
    if not pipeline:
        return "Error: pipeline required"

    try:
        res = mongo_client._coll(collection).aggregate(pipeline)
        result = dumps(list(res))
        logger.info(f"聚合结果长度: {len(result)}")
        return result
    except Exception as exc:
        logger.exception("Aggregate failed")
        return f"Error: {exc}"

@mcp.tool()
def status() -> str:
    """获取当前 MongoDB 连接状态。用于检查数据库是否已连接，以及连接的具体信息。
    
    返回值:
    - 未连接: "未连接"
    - 连接正常: "已连接 (数据库: {数据库名}, 只读模式: {是否只读})"
    - 连接断开: "连接已断开: {具体错误信息}"
    """
    if not mongo_client:
        return "未连接"
    
    try:
        # 尝试执行 ping 命令来验证连接是否仍然有效
        mongo_client.client.admin.command("ping")
        return f"已连接 (数据库: {mongo_client.db_name}, 只读模式: {mongo_client.read_only})"
    except Exception as exc:
        logger.exception("状态检查失败")
        return f"连接已断开: {exc}"

@mcp.tool()
def store_file(
    file_path: str,
    tags: List[str] = None,
    metadata: Dict = None,
    collection: str = "fs"
) -> str:
    """将本地文件存储到 MongoDB GridFS。用于存储图片、视频等二进制文件。
    
    参数说明：
    - file_path: 本地文件路径，必填参数，如 "./photos/image.jpg"
    - tags: 文件标签列表，默认为 None，如 ["风景", "旅游"]
    - metadata: 额外的元数据，默认为 None，如 {"location": "北京", "拍摄时间": "2024-01-01"}
    - collection: GridFS 集合名称，默认为 "fs"
    
    返回值:
    - 成功: "文件存储成功，ID: {文件ID}"
    - 未连接: "Error: Not connected"
    - 只读模式: "Error: server is read-only"
    - 文件不存在: "Error: 文件不存在: {文件路径}"
    - 失败: "Error: {具体错误信息}"
    
    示例：
    >>> store_file(file_path="./photos/image.jpg", tags=["风景", "旅游"])
    >>> store_file(file_path="./videos/video.mp4", metadata={"拍摄时间": "2024-01-01"})
    """
    logger.info(f"存储文件参数: file_path={file_path}, tags={tags}, metadata={metadata}, collection={collection}")
    
    if not mongo_client:
        return "Error: Not connected"
    if mongo_client.read_only:
        return "Error: server is read-only"
    if not os.path.exists(file_path):
        return f"Error: 文件不存在: {file_path}"

    try:
        # 准备元数据
        file_metadata = {
            "filename": os.path.basename(file_path),
            "contentType": "application/octet-stream",  # 默认类型
            "uploadDate": datetime.utcnow(),
            "tags": tags or [],
            **(metadata or {})
        }

        # 根据文件扩展名设置 content type
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.jpg', '.jpeg']:
            file_metadata["contentType"] = "image/jpeg"
        elif ext == '.png':
            file_metadata["contentType"] = "image/png"
        elif ext == '.gif':
            file_metadata["contentType"] = "image/gif"
        elif ext in ['.mp4', '.mov']:
            file_metadata["contentType"] = "video/mp4"
        elif ext == '.pdf':
            file_metadata["contentType"] = "application/pdf"

        # 读取并存储文件
        with open(file_path, 'rb') as f:
            file_id = mongo_client.fs.put(
                f,
                **file_metadata
            )
        
        logger.info(f"文件存储成功: file_id={file_id}")
        return f"文件存储成功，ID: {file_id}"
    except Exception as exc:
        logger.exception("文件存储失败")
        return f"Error: {exc}"

@mcp.tool()
def find_files(
    tags: List[str] = None,
    output_dir: str = "./downloads",
    collection: str = "fs",
    limit: int = 1,
    fuzzy_match: bool = False
) -> str:
    """查询并下载 GridFS 中的文件。用于查找和获取图片、视频等二进制文件。
    
    参数说明：
    - tags: 文件标签列表，用于筛选文件，如 ["恩恩", "2024年"]。默认为 None，表示不按标签筛选。
      注意：只要文件包含任意一个标签就会返回，不需要全部匹配。
    - output_dir: 下载文件保存的目录，默认为 "./downloads"。
    - collection: GridFS 集合名称，默认为 "fs"。
    - limit: 返回文件数量限制，默认为 1。
    - fuzzy_match: 是否启用模糊匹配，默认为 False。如果为 True，则标签会作为正则表达式进行模糊匹配。
      例如：标签 "2024年" 会匹配 "2024年10月21日放学" 这样的标签。
    
    返回值:
    - 成功: JSON 字符串，包含文件信息数组，每个文件信息包含:
        - file_id: 文件ID
        - filename: 文件名
        - local_path: 本地保存路径
        - content_type: 文件类型
        - upload_date: 上传时间
        - length: 文件大小
        - tags: 文件标签
        - metadata: 其他元数据
    - 未找到文件: "未找到匹配的文件"
    - 未连接: "Error: Not connected"
    - 失败: "Error: {具体错误信息}"
    
    示例：
    >>> find_files(tags=["恩恩", "2024年"], fuzzy_match=True)  # 模糊查询包含"恩恩"和"2024年"的文件
    >>> find_files(tags=["恩恩"], limit=5)  # 精确查询包含"恩恩"标签的前5个文件
    """
    logger.info(f"查询文件参数: tags={tags}, output_dir={output_dir}, collection={collection}, limit={limit}, fuzzy_match={fuzzy_match}")
    
    if not mongo_client:
        return "Error: Not connected"

    try:
        # 确保输出目录存在，并转换为绝对路径
        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        # 构建查询条件
        query = {}
        if tags:
            if fuzzy_match:
                # 使用正则表达式进行模糊匹配
                query["metadata.tags"] = {
                    "$in": [{"$regex": tag, "$options": "i"} for tag in tags]
                }
            else:
                # 精确匹配
                query["metadata.tags"] = {"$in": tags}

        files = list(mongo_client.fs.find(query).limit(limit))
        result = []
        
        for file in files:
            # 生成输出文件路径（使用绝对路径）
            output_path = os.path.abspath(os.path.join(output_dir, f"{file._id}_{file.filename}"))
            
            # 下载文件
            with open(output_path, 'wb') as f:
                f.write(file.read())
            
            # 记录文件信息
            file_info = {
                "file_id": str(file._id),
                "filename": file.filename,
                "local_path": output_path,  # 使用绝对路径
                "content_type": file.content_type,
                "upload_date": file.upload_date.isoformat(),
                "length": file.length,
                "tags": file.metadata.get("tags", []) if file.metadata else [],  # 从 metadata 中获取标签
                "metadata": {k: v for k, v in (file.metadata or {}).items() 
                           if k not in ['filename', 'contentType', 'uploadDate', 'tags']}
            }
            result.append(file_info)
            logger.info(f"文件已下载到: {output_path}")
            logger.info(f"文件信息: {json.dumps(file_info, ensure_ascii=False, indent=2)}")
        
        if not result:
            logger.info("未找到匹配的文件")
            return "未找到匹配的文件"
            
        logger.info(f"找到并下载了 {len(result)} 个文件，详细信息：\n{json.dumps(result, ensure_ascii=False, indent=2)}")
        return f"找到 {len(result)} 个文件：\n{dumps(result)}"
    except Exception as exc:
        logger.exception("文件查询和下载失败")
        return f"Error: {exc}"

@mcp.tool()
def get_file(
    file_id: str,
    output_dir: str = "./downloads",
    collection: str = "fs"
) -> str:
    """根据文件ID获取并下载 GridFS 中的文件。用于获取特定的图片、视频等二进制文件。
    
    参数说明：
    - file_id: 文件ID（字符串格式的 ObjectId），必填参数，用于唯一标识要获取的文件。
    - output_dir: 下载文件保存的目录，默认为 "./downloads"。
    - collection: GridFS 集合名称，默认为 "fs"。
    
    返回值:
    - 成功: JSON 字符串，包含文件信息:
        - file_id: 文件ID
        - filename: 文件名
        - local_path: 本地保存路径
        - content_type: 文件类型
        - upload_date: 上传时间
        - length: 文件大小
        - tags: 文件标签
        - metadata: 其他元数据
    - 未连接: "Error: Not connected"
    - 无效ID: "Error: 无效的文件ID格式: {文件ID}"
    - 失败: "Error: {具体错误信息}"
    
    示例：
    >>> get_file(file_id="507f1f77bcf86cd799439011")  # 获取指定ID的文件
    >>> get_file(file_id="507f1f77bcf86cd799439011", output_dir="./photos")  # 指定下载目录
    """
    logger.info(f"获取文件参数: file_id={file_id}, output_dir={output_dir}, collection={collection}")
    
    if not mongo_client:
        return "Error: Not connected"

    try:
        # 确保输出目录存在，并转换为绝对路径
        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)
        
        # 将字符串 ID 转换为 ObjectId
        try:
            object_id = ObjectId(file_id)
        except Exception as e:
            logger.error(f"无效的文件ID格式: {file_id}")
            return f"Error: 无效的文件ID格式: {file_id}"
        
        # 获取文件
        file = mongo_client.fs.get(object_id)
        
        # 生成输出文件路径（使用绝对路径）
        output_path = os.path.abspath(os.path.join(output_dir, f"{file_id}_{file.filename}"))
        
        # 下载文件
        with open(output_path, 'wb') as f:
            f.write(file.read())
        
        # 返回文件信息
        result = {
            "file_id": str(file._id),
            "filename": file.filename,
            "local_path": output_path,  # 使用绝对路径
            "content_type": file.content_type,
            "upload_date": file.upload_date.isoformat(),
            "length": file.length,
            "tags": file.tags if hasattr(file, 'tags') else [],
            "metadata": {k: v for k, v in (file.metadata or {}).items() 
                       if k not in ['filename', 'contentType', 'uploadDate', 'tags']}
        }
        
        logger.info(f"文件已下载到: {output_path}")
        return dumps(result)
    except Exception as exc:
        logger.exception("获取文件失败")
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
    else:
        # 打印初始连接状态
        logger.info("初始连接状态: %s", status())

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