import asyncio
import os
from chat_session import ChatSession

async def main():
    # 设置 Windows 事件循环策略
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    session = ChatSession()
    await session.initialize()
    
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