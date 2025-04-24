import asyncio
from agents import Runner, TResponseInputItem
from dispatcher_agent import create_dispatcher_agent
from mcp_server_manager import mcp_server_manager

class ChatSession:
    def __init__(self):
        self.dispatcher_agent = None
        self.inputs = []
        self._initialized = False
        
    async def initialize(self):
        """初始化会话"""
        if not self._initialized:
            # 确保 MCP server 已初始化
            await mcp_server_manager.initialize_servers()
            self.dispatcher_agent = await create_dispatcher_agent()
            self._initialized = True
        
    async def process_message(self, message: str) -> str:
        """处理用户消息"""
        if not self._initialized:
            raise RuntimeError("Session not initialized")
            
        if not message.strip():
            return "请输入有效消息"
            
        self.inputs.append({"role": "user", "content": message})
        
        result = await Runner.run(self.dispatcher_agent, self.inputs)
        self.inputs = result.to_input_list()
        
        return result.final_output
        
    async def close(self):
        """清理资源"""
        if self._initialized:
            try:
                await mcp_server_manager.close()
            except Exception as e:
                print(f"Error closing session: {e}")
            finally:
                self._initialized = False
                self.dispatcher_agent = None
                self.inputs = [] 