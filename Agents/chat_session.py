import asyncio
from agents import Runner, TResponseInputItem, Agent
from dispatcher_agent import create_dispatcher_agent
from mcp_server_manager import mcp_server_manager
from tts_client import TTSClient

class ChatSession:
    def __init__(self):
        self._initialized = False
        self.inputs = []
        self.dispatcher_agent = None
        self.current_agent = None  # 当前活跃的 agent
        self.tts_client = None

    async def initialize(self):
        """初始化会话"""
        if not self._initialized:
            self.dispatcher_agent = await create_dispatcher_agent()
            self.current_agent = self.dispatcher_agent  # 初始时使用 dispatcher
            # 初始化 TTS 客户端
            self.tts_client = TTSClient()
            if not self.tts_client.check_server_status():
                print("TTS 服务器不可用，语音功能将不可用")
            self._initialized = True
        
    async def process_message(self, message: str) -> str:
        """处理用户消息"""
        if not self._initialized:
            raise RuntimeError("Session not initialized")
            
        if not message.strip():
            return "请输入有效消息"
            
        self.inputs.append({"role": "user", "content": message})
            
        try:
            if self.current_agent is not self.dispatcher_agent:
                # 如果还没加过，就 append 一次
                if self.dispatcher_agent not in self.current_agent.handoffs:
                    self.current_agent.handoffs.append(self.dispatcher_agent)
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
                response = formatted_response
            
            # 使用 TTS 播放响应
            if self.tts_client and self.tts_client.check_server_status():
                self.tts_client.text_to_speech(response)
                
            return response
        except Exception as e:
            error_msg = f"处理消息时出错：{str(e)}"
            if self.tts_client and self.tts_client.check_server_status():
                self.tts_client.text_to_speech(error_msg)
            return error_msg
        
    async def close(self):
        """清理资源"""
        if self._initialized:
            try:
                # 不再需要在这里关闭 MCP 服务器，因为它现在由 main.py 统一管理
                if self.tts_client:
                    self.tts_client.close()
            except Exception as e:
                print(f"Error closing session: {e}")
            finally:
                self._initialized = False
                self.dispatcher_agent = None
                self.inputs = []
                self.tts_client = None

    async def handoff_to(self, agent: Agent):
        """切换到指定的 agent"""
        self.current_agent = agent
        message = f"已切换到 {agent.name} 处理后续消息"
        print(message)
        if self.tts_client and self.tts_client.check_server_status():
            self.tts_client.text_to_speech(message) 