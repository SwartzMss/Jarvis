import aiohttp
import asyncio
from logger_config import logger

class TTSClient:
    def __init__(self, host="127.0.0.1", port=8001):
        self.base_url = f"http://{host}:{port}"
        self.session = None

    async def ensure_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def play_text(self, text: str, voice: str = "zh-CN-XiaoxiaoNeural"):
        try:
            await self.ensure_session()
            url = f"{self.base_url}/tts/play"
            data = {
                "text": text,
                "voice": voice,
                "rate": "+0%",
                "volume": "+0%"
            }
            
            async with self.session.post(url, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"TTS播放成功: {result}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"TTS播放失败: {error_text}")
                    return False
        except Exception as e:
            logger.error(f"TTS服务调用出错: {str(e)}", exc_info=True)
            return False

# 创建全局TTS客户端实例
tts_client = TTSClient() 