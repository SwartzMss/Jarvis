import asyncio
from agents import Runner, TResponseInputItem
from dispatcher_agent import create_dispatcher_agent

class ChatSession:
    def __init__(self):
        self.dispatcher_agent = None
        self.inputs = []
        
    async def initialize(self):
        """初始化会话"""
        self.dispatcher_agent = await create_dispatcher_agent()
        
    async def process_message(self, message: str) -> str:
        """处理用户消息"""
        if not message.strip():
            return "请输入有效消息"
            
        self.inputs.append({"role": "user", "content": message})
        
        result = await Runner.run(self.dispatcher_agent, self.inputs)
        self.inputs = result.to_input_list()
        
        return result.final_output
        
    async def close(self):
        """清理资源"""
        pass  # 如果需要清理资源，可以在这里添加 