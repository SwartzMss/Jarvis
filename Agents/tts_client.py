import aiohttp
import threading
import queue
import asyncio
from typing import Optional, Dict, Any
import os
import sys

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
        self.loop = None  # 事件循环
        self.status_ready = threading.Event()  # 用于同步状态检查
        self.server_available = False  # 服务器状态
        print(f"TTS 客户端初始化完成，服务器地址: {self.base_url}")
        
        # 启动工作线程
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        print("TTS 工作线程已启动")

    def _worker_loop(self):
        """工作线程循环，处理TTS请求队列"""
        # 为工作线程创建新的事件循环
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # 初始检查服务器状态
        self.server_available = self.loop.run_until_complete(self._check_status())
        self.status_ready.set()
        
        while self.is_running:
            try:
                # 从队列获取请求
                text, voice, rate, volume = self.request_queue.get(timeout=1.0)
                
                # 执行HTTP请求
                try:
                    self.loop.run_until_complete(self._send_request(text, voice, rate, volume))
                except Exception as e:
                    print(f"TTS 请求失败: {str(e)}")
                
                # 标记任务完成
                self.request_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"TTS 工作线程错误: {str(e)}")
                continue
        
        # 关闭事件循环
        self.loop.close()

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
                print(f"发送 TTS 请求: text='{text[:50]}...', voice={voice}, rate={rate}, volume={volume}")
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        print("TTS 请求成功")
                        return result
                    else:
                        error_text = await response.text()
                        print(f"TTS 请求失败: HTTP {response.status}, {error_text}")
                        raise Exception(f"TTS 请求失败: HTTP {response.status}, {error_text}")
            except Exception as e:
                print(f"TTS 请求失败: {str(e)}")
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
            print("TTS 请求已加入队列")
        except Exception as e:
            print(f"添加 TTS 请求到队列失败: {str(e)}")

    def check_server_status(self) -> bool:
        """
        检查 TTS 服务器状态
        
        返回:
            bool: 服务器是否可用
        """
        # 等待初始状态检查完成
        self.status_ready.wait()
        return self.server_available

    async def _check_status(self) -> bool:
        """异步检查服务器状态"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.base_url}/") as response:
                    return response.status == 200
            except Exception as e:
                print(f"检查服务器状态失败: {str(e)}")
                return False

    def close(self):
        """关闭客户端，释放资源"""
        self.is_running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=1.0)
        print("TTS 客户端已关闭")
