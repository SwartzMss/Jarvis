"""
sensevoice_demo_by_mic.py - 基于麦克风录音并转写示例
"""
import os
from pathlib import Path
import asyncio
import sys
import logging
import time
import numba


# 配置日志
logging.basicConfig(
    level=logging.INFO,  # 改为 INFO 级别
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # 改为 INFO 级别


from voice_input import VoiceInput

class VoiceAssistant:
    def __init__(self):
        self.voice_input = VoiceInput()
        
    async def process_text(self, text: str):
        """处理语音识别后的文本"""
        print(text)
    
    def on_text_received(self, text: str):
        """语音识别文本回调"""
        # 使用 asyncio 运行异步处理
        asyncio.run(self.process_text(text))
    
    def start(self):
        """启动语音助手"""
        self.voice_input.on_text_received = self.on_text_received
        self.voice_input.start()
        logger.info("语音助手已启动，按 Ctrl+C 停止...")
    
    def stop(self):
        """停止语音助手"""
        self.voice_input.stop()
        logger.info("语音助手已停止")

async def main():
    """主函数"""
    try:
        # 初始化语音助手
        assistant = VoiceAssistant()
        
        # 启动语音助手
        assistant.start()
        
        # 保持程序运行
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("正在停止语音助手...")
        assistant.stop()
    except Exception as e:
        logger.error(f"发生错误: {e}")
        if 'assistant' in locals():
            assistant.stop()

if __name__ == "__main__":
    # 设置 Windows 平台的事件循环策略
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # 运行主函数
    asyncio.run(main())