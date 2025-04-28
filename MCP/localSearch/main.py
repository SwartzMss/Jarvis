from mcp.server.fastmcp import FastMCP
import psutil  # search_rg 中会用到
from rg_search import RGSearchParams, build_rg_command, run_command
import logging
from typing import List, Dict, Any
import json
import os
import tempfile
from datetime import datetime

mcp = FastMCP(
    name="rg.exe File Search Service",
    description="MCP service for comprehensive file search based on ripgrep (rg.exe).",
    dependencies=["psutil"]
)

def truncate_text(text: str, max_length: int = 200) -> str:
    """截断文本，保留关键信息"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."

def format_search_result(line: str, max_context: int = 3) -> Dict[str, Any]:
    """格式化搜索结果，提取关键信息"""
    parts = line.split(":", 2)
    if len(parts) < 3:
        return {"file": line, "line": 0, "content": line}
    
    file_path, line_num, content = parts
    return {
        "file": file_path,
        "line": int(line_num),
        "content": truncate_text(content.strip())
    }

def save_results_to_file(results: List[str], query: str) -> str:
    """将搜索结果保存到临时文件"""
    # 创建临时目录
    temp_dir = os.path.join(tempfile.gettempdir(), "rg_search_results")
    os.makedirs(temp_dir, exist_ok=True)
    
    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_query = "".join(c for c in query if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_query = safe_query[:50]  # 限制文件名长度
    filename = f"search_results_{safe_query}_{timestamp}.txt"
    filepath = os.path.join(temp_dir, filename)
    
    # 写入文件
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(results))
    
    return filepath

@mcp.tool()
def search_rg(params: dict, timeout: int = 30, max_results: int = 10) -> str:
    """
    使用 rg.exe 进行通用文本或文件名搜索的服务。

    [主要用途]
    1. **内容搜索**：
       - 通过 `query` 指定要搜索的文本（支持正则、固定字符串、整词等）
       - 常用于在多个文件中查找关键字、分析日志异常、批量检索信息

    2. **文件名搜索**：
       - 当 `files_only=True` 时，将在指定路径下按文件名匹配 `query`
       - 例如查询带有 "config" 字样的文件，可设置 `{"query": "config", "files_only": true}`
       - 若要只匹配特定后缀（如 *.yaml），可结合 `glob` 参数

    [关键参数说明]
    - `path`: 搜索起始路径（默认为当前目录）。若结果为空且为默认 "."，则自动遍历本地所有磁盘。
    - `query`: 待搜索的内容或文件名关键词（必填）
    - `max_results`: 最大返回结果数（默认10）
    - `glob`: 进一步过滤文件，类似 `-g` 参数（可使用 `["*.py", "!*.log"]` 等）
    - `ignore_case`: 是否忽略大小写（默认 True），`case_sensitive` 则强制区分大小写
    - `fixed_strings`: 是否视 `query` 为固定字符串（关闭正则解析）
    - `word_regexp`: 是否整词匹配（相当于自动加 `\b` 边界）
    - `files_only`: 是否只搜索文件名（而不搜索内容）
    - `hidden`: 是否包含隐藏文件
    - `max_filesize`: 跳过大于指定大小的文件（如 "50M"）
    - `threads`: 自定义搜索线程数

    [返回结果]
    - 成功：返回JSON格式的结果，包含：
      - total: 总结果数
      - results: 结果列表，每个结果包含文件路径、行号和内容摘要
      - truncated: 是否被截断
      - result_file: 如果结果被截断，则包含保存完整结果的临时文件路径
    - 失败：返回错误信息
    """
    try:
        logging.getLogger("rg_search").info("Parsing input parameters...")
        # Validate and parse input parameters using RGSearchParams model
        rg_params = RGSearchParams(**params)
        cmd = build_rg_command(rg_params)
        logging.getLogger("rg_search").info("Starting search...")
        output = run_command(cmd, timeout=timeout)

        # 处理结果
        results = []
        all_lines = output.strip().split("\n")
        total_results = len(all_lines)
        
        # 只处理前 max_results 条结果
        for line in all_lines[:max_results]:
            results.append(format_search_result(line))

        # 当输出为空且路径为默认 '.' 时，尝试对所有本地盘符搜索
        if not results and (not rg_params.path or rg_params.path.strip() == "."):
            logging.getLogger("rg_search").info("No result from initial search; searching all local drives...")
            drives = [p.device for p in psutil.disk_partitions() if p.fstype and p.device[0].isalpha()]
            if not drives:
                logging.getLogger("rg_search").error("No local disks detected.")
                return json.dumps({
                    "total": 0,
                    "results": [],
                    "truncated": False,
                    "error": "No local disks detected."
                })

            for drive in drives:
                if not drive.endswith("\\"):
                    drive = drive + "\\"
                logging.getLogger("rg_search").info(f"Searching drive {drive}...")
                rg_params.path = drive
                cmd = build_rg_command(rg_params)
                drive_output = run_command(cmd, timeout=timeout)
                drive_lines = drive_output.strip().split("\n")
                all_lines.extend(drive_lines)
                
                # 添加新结果，但不超过 max_results
                remaining = max_results - len(results)
                if remaining <= 0:
                    break
                    
                for line in drive_lines[:remaining]:
                    results.append(format_search_result(line))
                total_results += len(drive_lines)

        # 如果结果超过限制，保存到文件
        result_file = None
        if total_results > max_results:
            result_file = save_results_to_file(all_lines, params.get("query", "unknown"))

        logging.getLogger("rg_search").info("Search complete.")
        return json.dumps({
            "total": total_results,
            "results": results,
            "truncated": total_results > max_results,
            "result_file": result_file
        })
    except Exception as ex:
        logging.getLogger("rg_search").error(f"Error during search: {str(ex)}")
        return json.dumps({
            "total": 0,
            "results": [],
            "truncated": False,
            "error": str(ex)
        })

if __name__ == "__main__":
    mcp.run()
