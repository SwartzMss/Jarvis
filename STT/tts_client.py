import aiohttp
import threading
import queue
import asyncio
from typing import Optional, Dict, Any
from logger_config import logger

class TTSClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8001"):
        """
        初始化 TTS 客户端
        
        参数:
            base_url: TTS 服务器的基础 URL
        """
        self.base_url = base_url.rstrip('/')
        self.request_queue = queue.Queue()  # 请求队列
        self.worker_thread = None  # 工作线程
        self.is_running = True  # 运行状态标志
        logger.info(f"TTS 客户端初始化完成，服务器地址: {self.base_url}")
        
        # 启动工作线程
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info("TTS 工作线程已启动")

    def _worker_loop(self):
        """工作线程循环，处理TTS请求队列"""
        while self.is_running:
            try:
                # 从队列获取请求
                text, voice, rate, volume = self.request_queue.get(timeout=1.0)
                
                # 为每个请求创建新的事件循环
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # 执行HTTP请求
                try:
                    loop.run_until_complete(self._send_request(text, voice, rate, volume))
                except Exception as e:
                    logger.error(f"TTS 请求失败: {str(e)}")
                finally:
                    loop.close()
                
                # 标记任务完成
                self.request_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"TTS 工作线程错误: {str(e)}")
                continue

    async def _send_request(self, text: str, voice: str, rate: str, volume: str):
        """
        发送HTTP请求到TTS服务器
        
        参数:
            text: 要转换的文本
            voice: 语音角色
            rate: 语速
            volume: 音量
        """
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/tts"
            payload = {
                "text": text,
                "voice": voice,
                "rate": rate,
                "volume": volume
            }
            
            try:
                logger.info(f"发送 TTS 请求: text='{text[:50]}...', voice={voice}, rate={rate}, volume={volume}")
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info("TTS 请求成功")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"TTS 请求失败: HTTP {response.status}, {error_text}")
                        raise Exception(f"TTS 请求失败: HTTP {response.status}, {error_text}")
            except Exception as e:
                logger.error(f"TTS 请求失败: {str(e)}")
                raise

    def text_to_speech(
        self,
        text: str,
        voice: str = "zh-CN-XiaoxiaoNeural",
        rate: str = "+0%",
        volume: str = "+0%"
    ):
        """
        发送文本到 TTS 服务器进行语音合成和播放
        
        参数:
            text: 要转换的文本
            voice: 语音角色
            rate: 语速
            volume: 音量
        """
        try:
            # 将请求放入队列
            self.request_queue.put((text, voice, rate, volume))
            logger.info("TTS 请求已加入队列")
        except Exception as e:
            logger.error(f"添加 TTS 请求到队列失败: {str(e)}")

    def check_server_status(self) -> bool:
        """
        检查 TTS 服务器状态
        
        返回:
            bool: 服务器是否可用
        """
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._check_status())
            loop.close()
            return result
        except Exception as e:
            logger.error(f"检查服务器状态失败: {str(e)}")
            return False

    async def _check_status(self) -> bool:
        """异步检查服务器状态"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.base_url}/") as response:
                    return response.status == 200
            except Exception as e:
                logger.error(f"检查服务器状态失败: {str(e)}")
                return False

    def close(self):
        """关闭客户端，释放资源"""
        self.is_running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=1.0)
        logger.info("TTS 客户端已关闭")

# 使用示例
def example_usage():
    """TTS客户端使用示例"""
    tts = TTSClient()
    try:
        # 检查服务器状态
        if tts.check_server_status():
            # 发送文本进行语音合成和播放
            tts.text_to_speech("你好，这是一个测试")
        else:
            print("TTS 服务器不可用")
    finally:
        tts.close()

if __name__ == "__main__":
    example_usage() 