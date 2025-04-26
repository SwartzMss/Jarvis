from mcp.server.fastmcp import FastMCP
import os
import logging
import json
from pathlib import Path
import shutil
import re
from typing import List, Dict, Any
import base64

# 配置日志
logger = logging.getLogger("filesystem_server")

# 初始化 FastMCP 服务
mcp = FastMCP(
    name="FileSystem MCP Server",
    description="Tool for file system operations",
    dependencies=["pathlib"]
)

@mcp.tool()
def read_file(path: str) -> str:
    """
    读取文件内容。
    
    参数：
      - path: 文件路径
    
    返回：
      文件内容
    """
    try:
        file_path = Path(path)
        if not file_path.exists():
            return f"Error: File not found: {path}"
        if not file_path.is_file():
            return f"Error: Path is not a file: {path}"
        return file_path.read_text(encoding='utf-8')
    except Exception as e:
        logger.exception("Failed to read file")
        return f"Error: {str(e)}"

@mcp.tool()
def write_file(path: str, content: str) -> str:
    """
    写入文件内容。
    
    参数：
      - path: 文件路径
      - content: 要写入的内容
    
    返回：
      操作结果
    """
    try:
        file_path = Path(path)
        file_path.write_text(content, encoding='utf-8')
        return f"Successfully wrote to {path}"
    except Exception as e:
        logger.exception("Failed to write file")
        return f"Error: {str(e)}"

@mcp.tool()
def list_directory(path: str = ".") -> str:
    """
    列出目录内容。
    
    参数：
      - path: 目录路径，默认为当前目录
    
    返回：
      目录内容列表
    """
    try:
        dir_path = Path(path)
        if not dir_path.exists():
            return f"Error: Directory not found: {path}"
        if not dir_path.is_dir():
            return f"Error: Path is not a directory: {path}"
        
        entries = []
        for entry in dir_path.iterdir():
            entry_type = "[DIR]" if entry.is_dir() else "[FILE]"
            entries.append(f"{entry_type} {entry.name}")
        
        return "\n".join(entries)
    except Exception as e:
        logger.exception("Failed to list directory")
        return f"Error: {str(e)}"

@mcp.tool()
def create_directory(path: str) -> str:
    """
    创建目录。
    
    参数：
      - path: 要创建的目录路径
    
    返回：
      操作结果
    """
    try:
        dir_path = Path(path)
        dir_path.mkdir(parents=True, exist_ok=True)
        return f"Successfully created directory: {path}"
    except Exception as e:
        logger.exception("Failed to create directory")
        return f"Error: {str(e)}"

@mcp.tool()
def move_file(source: str, destination: str) -> str:
    """
    移动文件或目录。
    
    参数：
      - source: 源路径
      - destination: 目标路径
    
    返回：
      操作结果
    """
    try:
        source_path = Path(source)
        dest_path = Path(destination)
        
        if not source_path.exists():
            return f"Error: Source not found: {source}"
            
        if source_path.is_file():
            shutil.move(str(source_path), str(dest_path))
        else:
            shutil.move(str(source_path), str(dest_path))
            
        return f"Successfully moved {source} to {destination}"
    except Exception as e:
        logger.exception("Failed to move file")
        return f"Error: {str(e)}"

@mcp.tool()
def read_file_bytes(path: str):
    """
    以二进制形式读取文件内容（原生bytes，不做base64编码）。

    参数：
      - path: 文件路径

    返回：
      文件的二进制内容（bytes）
    """
    try:
        file_path = Path(path)
        if not file_path.exists():
            return f"Error: File not found: {path}"
        if not file_path.is_file():
            return f"Error: Path is not a file: {path}"
        return file_path.read_bytes()
    except Exception as e:
        logger.exception("Failed to read file in binary mode")
        return f"Error: {str(e)}"

@mcp.tool()
def get_file_info(path: str) -> str:
    """
    获取文件信息。
    
    参数：
      - path: 文件路径
    
    返回：
      文件信息
    """
    try:
        file_path = Path(path)
        if not file_path.exists():
            return f"Error: File not found: {path}"
            
        stats = file_path.stat()
        info = {
            "name": file_path.name,
            "size": stats.st_size,
            "created": stats.st_ctime,
            "modified": stats.st_mtime,
            "is_file": file_path.is_file(),
            "is_dir": file_path.is_dir()
        }
        
        return json.dumps(info, indent=2)
    except Exception as e:
        logger.exception("Failed to get file info")
        return f"Error: {str(e)}"

@mcp.tool()
def read_file_binary(path: str) -> str:
    """
    以二进制形式读取文件内容。
    
    参数：
      - path: 文件路径
    
    返回：
      文件的二进制内容（Base64编码）
    """
    try:
        file_path = Path(path)
        if not file_path.exists():
            return f"Error: File not found: {path}"
        if not file_path.is_file():
            return f"Error: Path is not a file: {path}"
            
        # 读取二进制内容
        binary_content = file_path.read_bytes()
        # 将二进制内容转换为Base64编码
        base64_content = base64.b64encode(binary_content).decode('utf-8')
        return base64_content
    except Exception as e:
        logger.exception("Failed to read file in binary mode")
        return f"Error: {str(e)}"

if __name__ == "__main__":
    mcp.run()
