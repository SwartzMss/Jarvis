import asyncio
import os
from chat_session import ChatSession

async def main():
    # 设置 Windows 事件循环策略
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    session = ChatSession()
    await session.initialize()
    
    # 打印欢迎信息
    print("""
        欢迎使用 AI 助手！我是你的智能助手，我可以帮助你完成以下任务：

        1. 本地文件搜索：可以在本地文件系统中搜索内容
        2. 文件系统操作：可以读取、写入和操作文件
        3. 数据库操作：可以进行 MongoDB 数据库的查询和操作
        4. 网络浏览：可以访问和获取网络信息

        你可以直接告诉我你的需求，我会尽力帮助你。
        如果信息不完整，我会主动询问你更多细节。
        对于复杂的任务，我会提供分步骤的指导。

        输入 'quit' 或 'exit' 可以退出程序。
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

if __name__ == "__main__":
    asyncio.run(main()) 