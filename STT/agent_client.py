import aiohttp
import json
from logger_config import logger

class AgentClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 8002):
        """
        初始化Agent客户端
        
        Args:
            host: Agent服务器主机地址
            port: Agent服务器端口
        """
        self.api_url = f"http://{host}:{port}/chat"
        logger.info(f"Agent客户端初始化完成，API地址: {self.api_url}")

    async def send_message(self, content: str) -> str:
        """
        发送消息到Agent并获取响应
        
        Args:
            content: 要发送的消息内容
            
        Returns:
            str: Agent的响应内容
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json={"content": content}
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"Agent响应: {result['response']}")
                        return result['response']
                    else:
                        error_msg = f"发送到Agent失败: {response.status}"
                        logger.error(error_msg)
                        return error_msg
        except Exception as e:
            error_msg = f"发送到Agent时出错: {str(e)}"
            logger.error(error_msg)
            return error_msg

    async def close(self):
        """关闭客户端连接"""
        try:
            logger.info("关闭Agent客户端连接")
        except Exception as e:
            logger.error(f"关闭Agent客户端连接时出错: {str(e)}") 