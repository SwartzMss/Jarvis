from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from chat_session import ChatSession
import asyncio
import os
import threading

app = FastAPI(title="AI Assistant API")

class Message(BaseModel):
    content: str

@app.on_event("startup")
async def startup_event():
    # 设置 Windows 事件循环策略
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

@app.post("/chat")
async def chat(message: Message):
    try:
        session = ChatSession()
        await session.initialize()
        response = await session.process_message(message.content)
        await session.close()
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def start_server(host: str = "127.0.0.1", port: int = 8002):
    """在单独的线程中启动服务器"""
    def run_server():
        uvicorn.run(app, host=host, port=port)
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    return server_thread 