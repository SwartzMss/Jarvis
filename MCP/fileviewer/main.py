from mcp.server.fastmcp import FastMCP
import os
import logging
import json
from pathlib import Path
import subprocess
import psutil
import datetime
import time
import win32con
import win32process
import win32com.shell.shell as shell
import win32com.shell.shellcon as shellcon
import win32api

# 配置日志
logger = logging.getLogger("fileviewer_server")
logger.setLevel(logging.INFO)

# 创建文件处理器，使用当前日期作为文件名
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"fileviewer_{datetime.datetime.now().strftime('%Y%m%d')}.log")
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

# 添加初始日志
logger.info("FileViewer MCP 服务启动")
logger.info(f"日志文件路径: {log_file}")

# 初始化 FileViewer MCP 服务
mcp = FastMCP(
    name="FileViewer MCP Server",
    description="Tool for opening and viewing files with default applications",
    dependencies=["pathlib", "psutil", "pywin32"]
)

def _err(msg: str, file_path: Path):
    """生成错误响应"""
    logger.error(msg)
    return json.dumps({
        "success": False,
        "message": msg,
        "process_id": None,
        "file_path": str(file_path)
    })

@mcp.tool()
def open_file(path: str) -> str:
    """
    使用系统默认程序打开文件。
    
    参数：
      - path: 文件路径
    
    返回：
      JSON格式的响应，包含：
      - success: 是否成功
      - message: 操作结果或错误信息
      - process_id: 进程ID（如果成功打开）
      - file_path: 文件路径
    """
    logger.info(f"开始打开文件: {path}")
    try:
        file_path = Path(path)
        logger.debug(f"解析后的文件路径: {file_path}")
        
        if not file_path.exists():
            return _err(f"错误：文件不存在: {path}", file_path)
            
        if not file_path.is_file():
            return _err(f"错误：路径不是文件: {path}", file_path)
            
        # 使用 ShellExecuteEx 打开文件并获取进程信息
        proc_info = shell.ShellExecuteEx(
            fMask=shellcon.SEE_MASK_NOCLOSEPROCESS,
            lpVerb="open",
            lpFile=str(file_path),
            lpParameters="",
            nShow=win32con.SW_SHOWNORMAL
        )
        
        # 获取进程句柄和PID
        h_process = proc_info["hProcess"]
        pid = win32process.GetProcessId(h_process)
        
        # 关闭进程句柄，避免泄漏
        win32api.CloseHandle(h_process)
        
        logger.info(f"文件已打开，进程ID: {pid}")
        return json.dumps({
            "success": True,
            "message": f"成功打开文件: {path}",
            "process_id": pid,
            "file_path": str(file_path)
        })
            
    except Exception as e:
        logger.exception(f"打开文件失败: {str(e)}")
        return _err(f"错误：{str(e)}", file_path)

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
    logger.info(f"开始关闭进程: process_id={process_id}")
    try:
        if not isinstance(process_id, int):
            logger.error(f"进程ID必须是整数，当前值: {process_id}")
            return json.dumps({
                "success": False,
                "message": f"错误：进程ID必须是整数，当前值: {process_id}",
                "process_id": process_id
            })
            
        # 检查进程是否存在
        if not psutil.pid_exists(process_id):
            logger.error(f"进程不存在，进程ID: {process_id}")
            return json.dumps({
                "success": False,
                "message": f"错误：进程不存在，进程ID: {process_id}",
                "process_id": process_id
            })
            
        # 获取进程对象
        process = psutil.Process(process_id)
        logger.debug(f"进程信息: {process.name()} (PID: {process.pid})")
        
        # 终止进程及其子进程
        children = process.children(recursive=True)
        logger.debug(f"找到 {len(children)} 个子进程")
        for child in children:
            logger.debug(f"终止子进程: {child.name()} (PID: {child.pid})")
            child.terminate()
        process.terminate()
        logger.info(f"进程 {process_id} 已终止")
        
        return json.dumps({
            "success": True,
            "message": f"成功关闭进程，进程ID: {process_id}",
            "process_id": process_id
        })
            
    except psutil.NoSuchProcess:
        logger.error(f"进程不存在，进程ID: {process_id}")
        return json.dumps({
            "success": False,
            "message": f"错误：进程不存在，进程ID: {process_id}",
            "process_id": process_id
        })
    except psutil.AccessDenied:
        logger.error(f"没有权限关闭进程，进程ID: {process_id}")
        return json.dumps({
            "success": False,
            "message": f"错误：没有权限关闭进程，进程ID: {process_id}",
            "process_id": process_id
        })
    except Exception as e:
        logger.exception(f"关闭进程失败: {str(e)}")
        return json.dumps({
            "success": False,
            "message": f"错误：{str(e)}",
            "process_id": process_id
        })

if __name__ == "__main__":
    logger.info("FileViewer MCP 服务正在启动...")
    mcp.run()
    logger.info("FileViewer MCP 服务已停止") 