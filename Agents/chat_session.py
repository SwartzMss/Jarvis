import asyncio
from agents import Runner, TResponseInputItem, Agent
from dispatcher_agent import create_dispatcher_agent
from mcp_server_manager import mcp_server_manager

class ChatSession:
    def __init__(self):
        self._initialized = False
        self.inputs = []
        self.dispatcher_agent = None
        self.current_agent = None  # 当前活跃的 agent

    async def initialize(self):
        """初始化会话"""
        if not self._initialized:
            # 确保 MCP server 已初始化
            await mcp_server_manager.initialize_servers()
            self.dispatcher_agent = await create_dispatcher_agent()
            self.current_agent = self.dispatcher_agent  # 初始时使用 dispatcher
            self._initialized = True
        
    async def process_message(self, message: str) -> str:
        """处理用户消息"""
        if not self._initialized:
            raise RuntimeError("Session not initialized")
            
        if not message.strip():
            return "请输入有效消息"
            
        self.inputs.append({"role": "user", "content": message})
        
        try:
            # 使用当前活跃的 agent 处理消息
            result = await Runner.run(self.current_agent, self.inputs, context=self)
            self.inputs = result.to_input_list()
            
            # 格式化响应
            response = result.final_output
            if isinstance(response, dict):
                # 如果是字典类型的响应（比如数据库查询结果），进行格式化
                formatted_response = "查询结果：\n"
                for key, value in response.items():
                    formatted_response += f"{key}: {value}\n"
                return formatted_response
            return response
        except Exception as e:
            return f"处理消息时出错：{str(e)}"
        
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

    async def handoff_to(self, agent: Agent):
        """切换到指定的 agent"""
        self.current_agent = agent
        print(f"已切换到 {agent.name} 处理后续消息") 