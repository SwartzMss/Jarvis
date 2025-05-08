from typing import List, Dict, Any
from agents import Agent, ModelSettings
from agent_lifecycle_hooks import default_hooks
from model_provider import model_provider, MODEL_NAME
from mcp_server_manager import mcp_server_manager

def create_excel_agent():
    # 获取 excel server
    excel = mcp_server_manager.get_server("excel")
    if not excel:
        raise RuntimeError("Excel server 未初始化")
    
    agent = Agent(
        name="Excel",
        instructions="""你是一个 Excel 操作助手，可以帮助用户进行各种 Excel 操作。
        你可以：
        1. 创建新的 Excel 工作簿
        2. 打开现有的 Excel 文件
        3. 读写单元格数据
        4. 创建和编辑图表
        5. 创建和管理数据透视表
        6. 设置单元格格式
        7. 应用筛选和排序
        8. 运行宏
        
        主要功能包括：
        - 工作簿操作：新建、打开、保存、关闭
        - 工作表操作：添加、删除、重命名、激活
        - 数据操作：读写单元格、设置公式、应用筛选
        - 图表操作：创建各种类型的图表
        - 数据透视表：创建和管理数据透视表
        - 格式设置：设置字体、颜色、对齐方式等
        
        请根据用户的需求，执行相应的 Excel 操作。""",
        mcp_servers=[excel],
        hooks=default_hooks,
        model=model_provider.get_model(MODEL_NAME),
        model_settings=ModelSettings(temperature=0.3, top_p=0.9),
    )
    return agent
