from mcp.server.fastmcp import FastMCP
import win32com.client
import pythoncom
from typing import List, Optional, Any, Dict
import uuid
import logging
import os
import sys
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# 日志配置
# ---------------------------------------------------------------------------
LOG_FMT = "%(asctime)s - %(levelname)s - %(message)s"
logger = logging.getLogger("excel_server")
logger.setLevel(logging.DEBUG)
logger.handlers.clear()

console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(LOG_FMT))
logger.addHandler(console_handler)

file_handler = logging.FileHandler("excel_server.log", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(LOG_FMT))
logger.addHandler(file_handler)

logger.propagate = False

# ---------------------------------------------------------------------------
# MCP 服务实例
# ---------------------------------------------------------------------------
server = FastMCP(
    name="Excel MCP Server",
    description="Provide Excel automation operations via MCP",
    dependencies=["pywin32"]
)

# ---------------------------------------------------------------------------
# Excel 实例管理
# ---------------------------------------------------------------------------
class ExcelManager:
    """Excel 管理器，管理 Excel 应用程序和工作簿"""
    def __init__(self):
        self.app = None  # Excel 应用程序实例
        self.workbooks: Dict[str, Any] = {}  # book_id -> workbook
        self.charts: Dict[str, Any] = {}     # chart_id -> chart
        self.pivots: Dict[str, Any] = {}     # pivot_id -> pivot

    def initialize(self, visible: bool = True) -> None:
        """初始化 Excel 应用程序"""
        try:
            if not self.app:
                pythoncom.CoInitialize()
                self.app = win32com.client.Dispatch("Excel.Application")
                self.app.Visible = visible
                logger.info("Excel 应用程序初始化成功")
        except Exception as e:
            logger.error(f"Excel 应用程序初始化失败: {str(e)}")
            raise

    def cleanup(self):
        """清理 Excel 应用程序"""
        try:
            if self.app:
                for workbook in self.workbooks.values():
                    workbook.Close(False)
                self.app.Quit()
                self.app = None
                self.workbooks.clear()
                self.charts.clear()
                self.pivots.clear()
                pythoncom.CoUninitialize()
                logger.info("Excel 应用程序清理成功")
        except Exception as e:
            logger.error(f"Excel 应用程序清理失败: {str(e)}")

# 全局 Excel 管理器
excel_manager = ExcelManager()

# ---------------------------------------------------------------------------
# MCP 工具函数
# ---------------------------------------------------------------------------

@server.tool()
def new_workbook(file_path: str, visible: bool = True) -> Dict[str, str]:
    """创建新的 Excel 文件
    
    参数：
        file_path: Excel 文件保存路径，如 "C:\\Users\\用户名\\Documents\\新建工作簿.xlsx"
        visible: 是否可见，默认为 True
    
    返回：
        {"book_id": "工作簿ID"} 或 {"error": "错误信息"}
    """
    logger.info(f"创建新工作簿 - 参数: file_path={file_path}, visible={visible}")
    try:
        # 自动初始化
        excel_manager.initialize(visible)
        
        # 确保文件路径使用正确的 Windows 格式
        file_path = file_path.replace("/", "\\")
        
        # 确保目标目录存在
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            logger.debug(f"创建目录: {directory}")
        
        workbook = excel_manager.app.Workbooks.Add()
        
        # 保存文件
        workbook.SaveAs(file_path)
        
        book_id = str(uuid.uuid4())
        excel_manager.workbooks[book_id] = workbook
        logger.info(f"创建新工作簿成功 - book_id={book_id}, file_path={file_path}")
        return {"book_id": book_id}
    except Exception as e:
        logger.error(f"创建新工作簿失败: {str(e)}")
        return {"error": str(e)}

@server.tool()
def open_workbook(path: str, visible: bool = True) -> Dict[str, str]:
    """打开工作簿
    
    参数：
        path: Excel 文件路径
        visible: 是否可见，默认为 True
    
    返回：
        {"book_id": "工作簿ID"} 或 {"error": "错误信息"}
    """
    logger.info(f"打开工作簿 - 参数: path={path}, visible={visible}")
    try:
        # 自动初始化
        excel_manager.initialize(visible)
        
        workbook = excel_manager.app.Workbooks.Open(path)
        book_id = str(uuid.uuid4())
        excel_manager.workbooks[book_id] = workbook
        logger.info(f"打开工作簿成功 - book_id={book_id}, path={path}")
        return {"book_id": book_id}
    except Exception as e:
        logger.error(f"打开工作簿失败: {str(e)}")
        return {"error": str(e)}

@server.tool()
def close_workbook(book_id: str, save: bool = True) -> Dict[str, str]:
    """关闭工作簿
    
    参数：
        book_id: 工作簿ID
        save: 是否保存，默认为 True
    
    返回：
        {"status": "ok"} 或 {"error": "错误信息"}
    """
    logger.info(f"关闭工作簿 - 参数: book_id={book_id}, save={save}")
    try:
        if not excel_manager.app:
            logger.error("Excel 应用程序未初始化")
            return {"error": "Excel 应用程序未初始化"}
        
        if book_id in excel_manager.workbooks:
            workbook = excel_manager.workbooks[book_id]
            if save:
                workbook.Save()
                logger.debug(f"保存工作簿: book_id={book_id}")
            workbook.Close()
            del excel_manager.workbooks[book_id]
            logger.info(f"关闭工作簿成功 - book_id={book_id}")
            return {"status": "ok"}
        logger.error(f"未找到工作簿: book_id={book_id}")
        return {"error": f"未找到工作簿 ID: {book_id}"}
    except Exception as e:
        logger.error(f"关闭工作簿失败: {str(e)}")
        return {"error": str(e)}

@server.tool()
def write_range(book_id: str, sheet: str, address: str, data: List[List]) -> Dict[str, str]:
    """写入单元格范围
    
    参数：
        book_id: 工作簿ID
        sheet: 工作表名称
        address: 单元格地址，如 "A1"
        data: 二维数据列表
    
    返回：
        {"status": "ok"} 或 {"error": "错误信息"}
    """
    logger.info(f"写入单元格范围 - 参数: book_id={book_id}, sheet={sheet}, address={address}, data_size={len(data)}")
    try:
        if not excel_manager.app:
            logger.error("Excel 应用程序未初始化")
            return {"error": "Excel 应用程序未初始化"}
        
        if book_id in excel_manager.workbooks:
            workbook = excel_manager.workbooks[book_id]
            worksheet = workbook.Sheets(sheet)
            range_obj = worksheet.Range(address)
            
            for i, row in enumerate(data):
                for j, value in enumerate(row):
                    range_obj.Cells(i + 1, j + 1).Value = value
            logger.info(f"写入单元格范围成功 - book_id={book_id}, sheet={sheet}, address={address}")
            return {"status": "ok"}
        logger.error(f"未找到工作簿: book_id={book_id}")
        return {"error": f"未找到工作簿 ID: {book_id}"}
    except Exception as e:
        logger.error(f"写入单元格范围失败: {str(e)}")
        return {"error": str(e)}

@server.tool()
def read_range(book_id: str, sheet: str, address: Optional[str] = None) -> Dict[str, Any]:
    """读取单元格范围
    
    参数：
        book_id: 工作簿ID
        sheet: 工作表名称
        address: 单元格地址，如 "A1:C10"，默认为 None（读取已使用区域）
    
    返回：
        {"data": [[单元格值]]} 或 {"error": "错误信息"}
    """
    logger.info(f"读取单元格范围 - 参数: book_id={book_id}, sheet={sheet}, address={address}")
    try:
        if not excel_manager.app:
            logger.error("Excel 应用程序未初始化")
            return {"error": "Excel 应用程序未初始化"}
        
        if book_id in excel_manager.workbooks:
            workbook = excel_manager.workbooks[book_id]
            worksheet = workbook.Sheets(sheet)
            if address:
                range_obj = worksheet.Range(address)
            else:
                range_obj = worksheet.UsedRange
            
            data = []
            for row in range_obj.Rows:
                row_data = []
                for cell in row.Cells:
                    row_data.append(cell.Value)
                data.append(row_data)
            logger.info(f"读取单元格范围成功 - book_id={book_id}, sheet={sheet}, address={address}, data_size={len(data)}")
            return {"data": data}
        logger.error(f"未找到工作簿: book_id={book_id}")
        return {"error": f"未找到工作簿 ID: {book_id}"}
    except Exception as e:
        logger.error(f"读取单元格范围失败: {str(e)}")
        return {"error": str(e)}

@server.tool()
def create_chart(book_id: str, sheet: str, src: str, type: str, left: int, top: int, 
                width: int, height: int, title: Optional[str] = None, 
                x_title: Optional[str] = None, y_title: Optional[str] = None) -> Dict[str, str]:
    """创建图表
    
    参数：
        book_id: 工作簿ID
        sheet: 工作表名称
        src: 数据源范围，如 "A1:C10"
        type: 图表类型，如 "xlColumnClustered"
        left: 左侧位置
        top: 顶部位置
        width: 宽度
        height: 高度
        title: 图表标题
        x_title: X轴标题
        y_title: Y轴标题
    
    返回：
        {"chart_id": "图表ID"} 或 {"error": "错误信息"}
    """
    try:
        if not excel_manager.app:
            return {"error": "Excel 应用程序未初始化"}
        
        if book_id in excel_manager.workbooks:
            workbook = excel_manager.workbooks[book_id]
            worksheet = workbook.Sheets(sheet)
            
            chart = worksheet.Shapes.AddChart2().Chart
            chart.SetSourceData(worksheet.Range(src))
            chart.ChartType = getattr(win32com.client.constants, type)
            
            chart.Left = left
            chart.Top = top
            chart.Width = width
            chart.Height = height
            
            if title:
                chart.HasTitle = True
                chart.ChartTitle.Text = title
            
            if x_title:
                chart.Axes(1).HasTitle = True
                chart.Axes(1).AxisTitle.Text = x_title
            
            if y_title:
                chart.Axes(2).HasTitle = True
                chart.Axes(2).AxisTitle.Text = y_title
            
            chart_id = str(uuid.uuid4())
            excel_manager.charts[chart_id] = chart
            return {"chart_id": chart_id}
        return {"error": f"未找到工作簿 ID: {book_id}"}
    except Exception as e:
        logger.error(f"创建图表失败: {str(e)}")
        return {"error": str(e)}

@server.tool()
def create_pivot(book_id: str, sheet: str, src: str, dst: str, 
                rows: List[str], cols: List[str], values: List[str], 
                filters: Optional[List[str]] = None) -> Dict[str, str]:
    """创建数据透视表
    
    参数：
        book_id: 工作簿ID
        sheet: 工作表名称
        src: 数据源范围，如 "A1:C10"
        dst: 目标位置，如 "E1"
        rows: 行字段列表
        cols: 列字段列表
        values: 值字段列表
        filters: 筛选字段列表
    
    返回：
        {"pivot_id": "透视表ID"} 或 {"error": "错误信息"}
    """
    try:
        if not excel_manager.app:
            return {"error": "Excel 应用程序未初始化"}
        
        if book_id in excel_manager.workbooks:
            workbook = excel_manager.workbooks[book_id]
            worksheet = workbook.Sheets(sheet)
            
            pivot_cache = workbook.PivotCaches().Create(1, worksheet.Range(src))
            pivot_table = pivot_cache.CreatePivotTable(worksheet.Range(dst))
            
            for field in rows:
                pivot_table.PivotFields(field).Orientation = 1  # xlRowField
            
            for field in cols:
                pivot_table.PivotFields(field).Orientation = 2  # xlColumnField
            
            for field in values:
                pivot_table.PivotFields(field).Orientation = 4  # xlDataField
            
            if filters:
                for field in filters:
                    pivot_table.PivotFields(field).Orientation = 3  # xlPageField
            
            pivot_id = str(uuid.uuid4())
            excel_manager.pivots[pivot_id] = pivot_table
            return {"pivot_id": pivot_id}
        return {"error": f"未找到工作簿 ID: {book_id}"}
    except Exception as e:
        logger.error(f"创建数据透视表失败: {str(e)}")
        return {"error": str(e)}

@server.tool()
def save_workbook(book_id: str) -> Dict[str, str]:
    """保存工作簿
    
    参数：
        book_id: 工作簿ID
    
    返回：
        {"status": "ok"} 或 {"error": "错误信息"}
    """
    try:
        if not excel_manager.app:
            return {"error": "Excel 应用程序未初始化"}
        
        if book_id in excel_manager.workbooks:
            workbook = excel_manager.workbooks[book_id]
            workbook.Save()
            return {"status": "ok"}
        return {"error": f"未找到工作簿 ID: {book_id}"}
    except Exception as e:
        logger.error(f"保存工作簿失败: {str(e)}")
        return {"error": str(e)}

@server.tool()
def list_sheets(book_id: str) -> Dict[str, Any]:
    """列出工作簿中的所有工作表
    
    参数：
        book_id: 工作簿ID
    
    返回：
        {"sheets": ["Sheet1", "Sheet2", ...]} 或 {"error": "错误信息"}
    """
    try:
        if not excel_manager.app:
            return {"error": "Excel 应用程序未初始化"}
        
        if book_id in excel_manager.workbooks:
            workbook = excel_manager.workbooks[book_id]
            sheets = [sheet.Name for sheet in workbook.Sheets]
            return {"sheets": sheets}
        return {"error": f"未找到工作簿 ID: {book_id}"}
    except Exception as e:
        logger.error(f"列出工作表失败: {str(e)}")
        return {"error": str(e)}

@server.tool()
def add_sheet(book_id: str, name: str) -> Dict[str, str]:
    """添加新工作表
    
    参数：
        book_id: 工作簿ID
        name: 新工作表名称
    
    返回：
        {"status": "ok"} 或 {"error": "错误信息"}
    """
    try:
        if not excel_manager.app:
            return {"error": "Excel 应用程序未初始化"}
        
        if book_id in excel_manager.workbooks:
            workbook = excel_manager.workbooks[book_id]
            workbook.Sheets.Add().Name = name
            return {"status": "ok"}
        return {"error": f"未找到工作簿 ID: {book_id}"}
    except Exception as e:
        logger.error(f"添加工作表失败: {str(e)}")
        return {"error": str(e)}

@server.tool()
def delete_sheet(book_id: str, sheet: str) -> Dict[str, str]:
    """删除工作表
    
    参数：
        book_id: 工作簿ID
        sheet: 工作表名称
    
    返回：
        {"status": "ok"} 或 {"error": "错误信息"}
    """
    try:
        if not excel_manager.app:
            return {"error": "Excel 应用程序未初始化"}
        
        if book_id in excel_manager.workbooks:
            workbook = excel_manager.workbooks[book_id]
            workbook.Sheets(sheet).Delete()
            return {"status": "ok"}
        return {"error": f"未找到工作簿 ID: {book_id}"}
    except Exception as e:
        logger.error(f"删除工作表失败: {str(e)}")
        return {"error": str(e)}

@server.tool()
def rename_sheet(book_id: str, old_name: str, new_name: str) -> Dict[str, str]:
    """重命名工作表
    
    参数：
        book_id: 工作簿ID
        old_name: 原工作表名称
        new_name: 新工作表名称
    
    返回：
        {"status": "ok"} 或 {"error": "错误信息"}
    """
    try:
        if not excel_manager.app:
            return {"error": "Excel 应用程序未初始化"}
        
        if book_id in excel_manager.workbooks:
            workbook = excel_manager.workbooks[book_id]
            workbook.Sheets(old_name).Name = new_name
            return {"status": "ok"}
        return {"error": f"未找到工作簿 ID: {book_id}"}
    except Exception as e:
        logger.error(f"重命名工作表失败: {str(e)}")
        return {"error": str(e)}

@server.tool()
def activate_sheet(book_id: str, sheet: str) -> Dict[str, str]:
    """激活工作表
    
    参数：
        book_id: 工作簿ID
        sheet: 工作表名称
    
    返回：
        {"status": "ok"} 或 {"error": "错误信息"}
    """
    try:
        if not excel_manager.app:
            return {"error": "Excel 应用程序未初始化"}
        
        if book_id in excel_manager.workbooks:
            workbook = excel_manager.workbooks[book_id]
            workbook.Sheets(sheet).Activate()
            return {"status": "ok"}
        return {"error": f"未找到工作簿 ID: {book_id}"}
    except Exception as e:
        logger.error(f"激活工作表失败: {str(e)}")
        return {"error": str(e)}

@server.tool()
def get_cell(book_id: str, sheet: str, address: str) -> Dict[str, Any]:
    """获取单元格的值
    
    参数：
        book_id: 工作簿ID
        sheet: 工作表名称
        address: 单元格地址，如 "A1"
    
    返回：
        {"value": value} 或 {"error": "错误信息"}
    """
    try:
        if not excel_manager.app:
            return {"error": "Excel 应用程序未初始化"}
        
        if book_id in excel_manager.workbooks:
            workbook = excel_manager.workbooks[book_id]
            value = workbook.Sheets(sheet).Range(address).Value
            return {"value": value}
        return {"error": f"未找到工作簿 ID: {book_id}"}
    except Exception as e:
        logger.error(f"获取单元格值失败: {str(e)}")
        return {"error": str(e)}

@server.tool()
def set_cell(book_id: str, sheet: str, address: str, value: Any) -> Dict[str, str]:
    """设置单元格的值
    
    参数：
        book_id: 工作簿ID
        sheet: 工作表名称
        address: 单元格地址，如 "A1"
        value: 要设置的值
    
    返回：
        {"status": "ok"} 或 {"error": "错误信息"}
    """
    try:
        if not excel_manager.app:
            return {"error": "Excel 应用程序未初始化"}
        
        if book_id in excel_manager.workbooks:
            workbook = excel_manager.workbooks[book_id]
            workbook.Sheets(sheet).Range(address).Value = value
            return {"status": "ok"}
        return {"error": f"未找到工作簿 ID: {book_id}"}
    except Exception as e:
        logger.error(f"设置单元格值失败: {str(e)}")
        return {"error": str(e)}

@server.tool()
def set_formula(book_id: str, sheet: str, address: str, formula: str) -> Dict[str, str]:
    """设置单元格的公式
    
    参数：
        book_id: 工作簿ID
        sheet: 工作表名称
        address: 单元格地址，如 "A1"
        formula: 要设置的公式，如 "=SUM(A1:A10)"
    
    返回：
        {"status": "ok"} 或 {"error": "错误信息"}
    """
    try:
        if not excel_manager.app:
            return {"error": "Excel 应用程序未初始化"}
        
        if book_id in excel_manager.workbooks:
            workbook = excel_manager.workbooks[book_id]
            workbook.Sheets(sheet).Range(address).Formula = formula
            return {"status": "ok"}
        return {"error": f"未找到工作簿 ID: {book_id}"}
    except Exception as e:
        logger.error(f"设置单元格公式失败: {str(e)}")
        return {"error": str(e)}

@server.tool()
def apply_filter(book_id: str, sheet: str, range_str: str, criteria: Dict[str, Any]) -> Dict[str, str]:
    """应用筛选条件
    
    参数：
        book_id: 工作簿ID
        sheet: 工作表名称
        range_str: 要筛选的范围，如 "A1:D10"
        criteria: 筛选条件，格式为 {"列索引": "筛选值"}，如 {"1": ">100", "2": "=Test"}
    
    返回：
        {"status": "ok"} 或 {"error": "错误信息"}
    """
    try:
        if not excel_manager.app:
            return {"error": "Excel 应用程序未初始化"}
        
        if book_id in excel_manager.workbooks:
            workbook = excel_manager.workbooks[book_id]
            worksheet = workbook.Sheets(sheet)
            filter_range = worksheet.Range(range_str)
            
            # 如果还没有筛选，先添加筛选
            if not worksheet.AutoFilterMode:
                filter_range.AutoFilter()
            
            # 应用筛选条件
            for col_index, criterion in criteria.items():
                filter_range.AutoFilter(Field=int(col_index), Criteria1=criterion)
            
            return {"status": "ok"}
        return {"error": f"未找到工作簿 ID: {book_id}"}
    except Exception as e:
        logger.error(f"应用筛选条件失败: {str(e)}")
        return {"error": str(e)}

@server.tool()
def clear_filter(book_id: str, sheet: str) -> Dict[str, str]:
    """清除筛选条件
    
    参数：
        book_id: 工作簿ID
        sheet: 工作表名称
    
    返回：
        {"status": "ok"} 或 {"error": "错误信息"}
    """
    try:
        if not excel_manager.app:
            return {"error": "Excel 应用程序未初始化"}
        
        if book_id in excel_manager.workbooks:
            workbook = excel_manager.workbooks[book_id]
            worksheet = workbook.Sheets(sheet)
            
            if worksheet.AutoFilterMode:
                worksheet.ShowAllData()
                worksheet.AutoFilterMode = False
            
            return {"status": "ok"}
        return {"error": f"未找到工作簿 ID: {book_id}"}
    except Exception as e:
        logger.error(f"清除筛选条件失败: {str(e)}")
        return {"error": str(e)}

@server.tool()
def copy_visible(book_id: str, sheet: str, range_str: str) -> Dict[str, Any]:
    """复制可见单元格的数据
    
    参数：
        book_id: 工作簿ID
        sheet: 工作表名称
        range_str: 要复制的范围，如 "A1:D10"
    
    返回：
        {"data": [[value, ...], ...]} 或 {"error": "错误信息"}
    """
    try:
        if not excel_manager.app:
            return {"error": "Excel 应用程序未初始化"}
        
        if book_id in excel_manager.workbooks:
            workbook = excel_manager.workbooks[book_id]
            worksheet = workbook.Sheets(sheet)
            
            # 获取可见单元格
            visible_range = worksheet.Range(range_str).SpecialCells(12)  # xlCellTypeVisible = 12
            
            # 将可见单元格的值转换为二维列表
            data = []
            for row in visible_range.Rows:
                row_data = []
                for cell in row.Cells:
                    row_data.append(cell.Value)
                data.append(row_data)
            
            return {"data": data}
        return {"error": f"未找到工作簿 ID: {book_id}"}
    except Exception as e:
        logger.error(f"复制可见单元格失败: {str(e)}")
        return {"error": str(e)}

@server.tool()
def delete_chart(book_id: str, chart_id: str) -> Dict[str, str]:
    """删除图表
    
    参数：
        book_id: 工作簿ID
        chart_id: 图表ID
    
    返回：
        {"status": "ok"} 或 {"error": "错误信息"}
    """
    try:
        if not excel_manager.app:
            return {"error": "Excel 应用程序未初始化"}
        
        if book_id in excel_manager.workbooks:
            if chart_id in excel_manager.charts:
                chart = excel_manager.charts[chart_id]
                chart.Delete()
                del excel_manager.charts[chart_id]
                return {"status": "ok"}
            return {"error": f"未找到图表 ID: {chart_id}"}
        return {"error": f"未找到工作簿 ID: {book_id}"}
    except Exception as e:
        logger.error(f"删除图表失败: {str(e)}")
        return {"error": str(e)}

@server.tool()
def refresh_pivot(book_id: str, pivot_id: str) -> Dict[str, str]:
    """刷新数据透视表
    
    参数：
        book_id: 工作簿ID
        pivot_id: 数据透视表ID
    
    返回：
        {"status": "ok"} 或 {"error": "错误信息"}
    """
    try:
        if not excel_manager.app:
            return {"error": "Excel 应用程序未初始化"}
        
        if book_id in excel_manager.workbooks:
            if pivot_id in excel_manager.pivots:
                pivot = excel_manager.pivots[pivot_id]
                pivot.RefreshTable()
                return {"status": "ok"}
            return {"error": f"未找到数据透视表 ID: {pivot_id}"}
        return {"error": f"未找到工作簿 ID: {book_id}"}
    except Exception as e:
        logger.error(f"刷新数据透视表失败: {str(e)}")
        return {"error": str(e)}

@server.tool()
def delete_pivot(book_id: str, pivot_id: str) -> Dict[str, str]:
    """删除数据透视表
    
    参数：
        book_id: 工作簿ID
        pivot_id: 数据透视表ID
    
    返回：
        {"status": "ok"} 或 {"error": "错误信息"}
    """
    try:
        if not excel_manager.app:
            return {"error": "Excel 应用程序未初始化"}
        
        if book_id in excel_manager.workbooks:
            if pivot_id in excel_manager.pivots:
                pivot = excel_manager.pivots[pivot_id]
                pivot.TableRange2.Clear()
                del excel_manager.pivots[pivot_id]
                return {"status": "ok"}
            return {"error": f"未找到数据透视表 ID: {pivot_id}"}
        return {"error": f"未找到工作簿 ID: {book_id}"}
    except Exception as e:
        logger.error(f"删除数据透视表失败: {str(e)}")
        return {"error": str(e)}

@server.tool()
def run_macro(book_id: str, macro_name: str) -> Dict[str, str]:
    """运行宏
    
    参数：
        book_id: 工作簿ID
        macro_name: 宏名称
    
    返回：
        {"status": "ok"} 或 {"error": "错误信息"}
    """
    try:
        if not excel_manager.app:
            return {"error": "Excel 应用程序未初始化"}
        
        if book_id in excel_manager.workbooks:
            workbook = excel_manager.workbooks[book_id]
            workbook.Application.Run(macro_name)
            return {"status": "ok"}
        return {"error": f"未找到工作簿 ID: {book_id}"}
    except Exception as e:
        logger.error(f"运行宏失败: {str(e)}")
        return {"error": str(e)}

@server.tool()
def set_format(book_id: str, sheet: str, range_str: str, format_dict: Dict[str, Any]) -> Dict[str, str]:
    """设置单元格格式
    
    参数：
        book_id: 工作簿ID
        sheet: 工作表名称
        range_str: 要设置格式的范围，如 "A1:D10"
        format_dict: 格式设置字典，支持以下键：
            - font_name: 字体名称
            - font_size: 字体大小
            - font_bold: 是否加粗
            - font_italic: 是否斜体
            - font_color: 字体颜色（RGB值）
            - background_color: 背景颜色（RGB值）
            - number_format: 数字格式
            - horizontal_alignment: 水平对齐方式
            - vertical_alignment: 垂直对齐方式
            - border_style: 边框样式
            - border_color: 边框颜色（RGB值）
    
    返回：
        {"status": "ok"} 或 {"error": "错误信息"}
    """
    try:
        if not excel_manager.app:
            return {"error": "Excel 应用程序未初始化"}
        
        if book_id in excel_manager.workbooks:
            workbook = excel_manager.workbooks[book_id]
            range_obj = workbook.Sheets(sheet).Range(range_str)
            
            # 设置字体
            if "font_name" in format_dict:
                range_obj.Font.Name = format_dict["font_name"]
            if "font_size" in format_dict:
                range_obj.Font.Size = format_dict["font_size"]
            if "font_bold" in format_dict:
                range_obj.Font.Bold = format_dict["font_bold"]
            if "font_italic" in format_dict:
                range_obj.Font.Italic = format_dict["font_italic"]
            if "font_color" in format_dict:
                range_obj.Font.Color = format_dict["font_color"]
            
            # 设置背景色
            if "background_color" in format_dict:
                range_obj.Interior.Color = format_dict["background_color"]
            
            # 设置数字格式
            if "number_format" in format_dict:
                range_obj.NumberFormat = format_dict["number_format"]
            
            # 设置对齐方式
            if "horizontal_alignment" in format_dict:
                range_obj.HorizontalAlignment = format_dict["horizontal_alignment"]
            if "vertical_alignment" in format_dict:
                range_obj.VerticalAlignment = format_dict["vertical_alignment"]
            
            # 设置边框
            if "border_style" in format_dict:
                for border in range_obj.Borders:
                    border.LineStyle = format_dict["border_style"]
                    if "border_color" in format_dict:
                        border.Color = format_dict["border_color"]
            
            return {"status": "ok"}
        return {"error": f"未找到工作簿 ID: {book_id}"}
    except Exception as e:
        logger.error(f"设置单元格格式失败: {str(e)}")
        return {"error": str(e)}

@server.tool()
def merge_cells(book_id: str, sheet: str, range_str: str) -> Dict[str, str]:
    """合并单元格
    
    参数：
        book_id: 工作簿ID
        sheet: 工作表名称
        range_str: 要合并的单元格范围，如 "A1:D1"
    
    返回：
        {"status": "ok"} 或 {"error": "错误信息"}
    """
    try:
        if not excel_manager.app:
            return {"error": "Excel 应用程序未初始化"}
        
        if book_id in excel_manager.workbooks:
            workbook = excel_manager.workbooks[book_id]
            workbook.Sheets(sheet).Range(range_str).Merge()
            return {"status": "ok"}
        return {"error": f"未找到工作簿 ID: {book_id}"}
    except Exception as e:
        logger.error(f"合并单元格失败: {str(e)}")
        return {"error": str(e)}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("Excel MCP server started (pid=%s, cwd=%s)", os.getpid(), os.getcwd())
    try:
        server.run()
    except Exception:
        logger.exception("Excel MCP server stopped unexpectedly")
        raise
    finally:
        excel_manager.cleanup()

# 导出 server 变量
__all__ = ["server"] 