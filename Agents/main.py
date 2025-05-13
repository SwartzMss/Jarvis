import asyncio
import os
from chat_session import ChatSession
from http_server import start_server
from mcp_server_manager import mcp_server_manager

async def initialize_services():
    """初始化所有服务"""
    # 初始化 MCP 服务器
    await mcp_server_manager.initialize_servers()
    
    # 启动 HTTP 服务器
    server_thread = start_server()
    return server_thread

async def main():
    # 设置 Windows 事件循环策略
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # 初始化所有服务
    server_thread = await initialize_services()
    
    session = ChatSession()
    await session.initialize()
    
    # 打印欢迎信息
    print("""
        欢迎使用 AI 助手！ 输入 'quit' 或 'exit' 可以退出程序。
    """)
    
    try:        
        while True:
            try:
                user_input = input("You: ").strip().lower()
                if user_input in ["quit", "exit"]:
                    print("Exiting...")
                    break
                    
                response = await session.process_message(user_input)
                print(f"Answer: {response}")
            except KeyboardInterrupt:
                print("Exiting...")
                break
    finally:
        await session.close()
        # 关闭 MCP 服务器
        await mcp_server_manager.close()
        # 等待 HTTP 服务器线程结束
        server_thread.join()

if __name__ == "__main__":
    asyncio.run(main()) 