from mcp.server.fastmcp import FastMCP
import os
import logging
import json
from pathlib import Path
import subprocess
import psutil
import datetime
import time

# 配置日志
logger = logging.getLogger("fileviewer_server")
logger.setLevel(logging.INFO)

# 创建文件处理器，使用当前日期作为文件名
log_file = f"fileviewer_{datetime.datetime.now().strftime('%Y%m%d')}.log"
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.INFO)

# 创建控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# 设置日志格式
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# 添加处理器到logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# 初始化 FileViewer MCP 服务
mcp = FastMCP(
    name="FileViewer MCP Server",
    description="Tool for opening and viewing files with default applications",
    dependencies=["pathlib", "psutil"]
)

@mcp.tool()
def open_file(path: str) -> str:
    """
    使用系统默认程序打开文件，并返回进程信息。
    
    参数：
      - path: 文件路径
    
    返回：
      JSON格式的响应，包含：
      - success: 是否成功
      - message: 操作结果或错误信息
      - process_id: 进程ID（如果成功打开）
      - file_path: 文件路径
    
    支持的文件类型：
      - 文本文件（.txt, .md, .py等）
      - 图片文件（.jpg, .png, .gif等）
      - 视频文件（.mp4, .avi等）
      - 文档文件（.pdf, .doc, .docx等）
    """
    try:
        file_path = Path(path)
        if not file_path.exists():
            return json.dumps({
                "success": False,
                "message": f"错误：文件不存在: {path}",
                "process_id": None,
                "file_path": str(file_path)
            })
            
        if not file_path.is_file():
            return json.dumps({
                "success": False,
                "message": f"错误：路径不是文件: {path}",
                "process_id": None,
                "file_path": str(file_path)
            })
            
        # 使用 os.startfile 打开文件
        os.startfile(str(file_path))
        
        # 获取文件扩展名
        ext = file_path.suffix.lower()
        
        # 等待一小段时间让程序启动
        time.sleep(0.5)
        
        # 获取当前所有进程
        current_processes = {p.pid: p for p in psutil.process_iter(['pid', 'name', 'create_time'])}
        
        # 根据文件类型查找可能的进程
        process_id = None
        if ext in ['.txt', '.md', '.py', '.json', '.xml', '.html', '.css', '.js']:
            # 文本文件通常用记事本或其他文本编辑器打开
            for pid, proc in current_processes.items():
                if proc.name().lower() in ['notepad.exe', 'code.exe', 'pycharm64.exe', 'idea64.exe']:
                    process_id = pid
                    break
        elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
            # 图片文件
            for pid, proc in current_processes.items():
                if proc.name().lower() in ['photos.exe', 'mspaint.exe', 'explorer.exe']:
                    process_id = pid
                    break
        elif ext in ['.pdf']:
            # PDF文件
            for pid, proc in current_processes.items():
                if proc.name().lower() in ['acrobat.exe', 'acrord32.exe', 'foxitreader.exe']:
                    process_id = pid
                    break
        elif ext in ['.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']:
            # Office文件
            for pid, proc in current_processes.items():
                if proc.name().lower() in ['winword.exe', 'excel.exe', 'powerpnt.exe']:
                    process_id = pid
                    break
        
        return json.dumps({
            "success": True,
            "message": f"成功打开文件: {path}",
            "process_id": process_id,
            "file_path": str(file_path)
        })
            
    except Exception as e:
        logger.exception("打开文件失败")
        return json.dumps({
            "success": False,
            "message": f"错误：{str(e)}",
            "process_id": None,
            "file_path": str(file_path)
        })

@mcp.tool()
def close_file(process_id: int) -> str:
    """
    关闭通过 open_file 打开的窗口。
    
    参数：
      - process_id: 进程ID（从 open_file 返回的 process_id）
    
    返回：
      JSON格式的响应，包含：
      - success: 是否成功
      - message: 操作结果或错误信息
      - process_id: 进程ID
    """
    try:
        if not isinstance(process_id, int):
            return json.dumps({
                "success": False,
                "message": f"错误：进程ID必须是整数，当前值: {process_id}",
                "process_id": process_id
            })
            
        # 检查进程是否存在
        if not psutil.pid_exists(process_id):
            return json.dumps({
                "success": False,
                "message": f"错误：进程不存在，进程ID: {process_id}",
                "process_id": process_id
            })
            
        # 获取进程对象
        process = psutil.Process(process_id)
        
        # 终止进程及其子进程
        for child in process.children(recursive=True):
            child.terminate()
        process.terminate()
        
        return json.dumps({
            "success": True,
            "message": f"成功关闭进程，进程ID: {process_id}",
            "process_id": process_id
        })
            
    except psutil.NoSuchProcess:
        return json.dumps({
            "success": False,
            "message": f"错误：进程不存在，进程ID: {process_id}",
            "process_id": process_id
        })
    except psutil.AccessDenied:
        return json.dumps({
            "success": False,
            "message": f"错误：没有权限关闭进程，进程ID: {process_id}",
            "process_id": process_id
        })
    except Exception as e:
        logger.exception("关闭进程失败")
        return json.dumps({
            "success": False,
            "message": f"错误：{str(e)}",
            "process_id": process_id
        })

if __name__ == "__main__":
    mcp.run() 