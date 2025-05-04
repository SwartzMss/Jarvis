import os
from pathlib import Path
import asyncio
import signal
from logger_config import logger
from wake_word_detector import WakeWordDetector
from speech_recognition import SpeechRecognizer
from config import WAKE_WORD

class VoiceAssistant:
    def __init__(self):
        self.wake_word_detector = None
        self.speech_recognizer = None
        self.is_running = False
        self.wake_word_task = None
        self.recognition_task = None

    async def start(self):
        """
        启动语音助手
        """
        try:
            logger.info("Starting model initialization...")
            self.speech_recognizer = SpeechRecognizer()
            logger.info("SenseVoice service initialized successfully")
            
            self.wake_word_detector = WakeWordDetector()
            self.is_running = True
            
            # 设置信号处理
            for sig in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, self.shutdown)
            
            logger.info(f"语音助手已启动，等待唤醒词 {WAKE_WORD}...")
            
            # 启动唤醒词检测任务
            self.wake_word_task = asyncio.create_task(self._detect_wake_word())
            await self.wake_word_task
            
        except Exception as e:
            logger.error(f"启动语音助手时发生错误: {str(e)}", exc_info=True)
            await self.stop()

    def shutdown(self, signum, frame):
        """
        处理终止信号
        """
        logger.info(f"收到终止信号 {signum}")
        asyncio.create_task(self.stop())

    async def stop(self):
        """
        停止语音助手
        """
        try:
            logger.info("正在停止语音助手...")
            self.is_running = False
            
            # 取消所有任务
            if self.wake_word_task:
                self.wake_word_task.cancel()
                try:
                    await self.wake_word_task
                except asyncio.CancelledError:
                    pass
            
            if self.recognition_task:
                self.recognition_task.cancel()
                try:
                    await self.recognition_task
                except asyncio.CancelledError:
                    pass
            
            # 释放资源
            if self.wake_word_detector:
                self.wake_word_detector.close()
            
            if self.speech_recognizer:
                self.speech_recognizer.close()
            
            logger.info("语音助手已停止")
        except Exception as e:
            logger.error(f"停止语音助手时发生错误: {str(e)}", exc_info=True)

    async def _detect_wake_word(self):
        """
        检测唤醒词
        """
        try:
            while self.is_running:
                # 音频处理在回调函数中进行，这里只需要保持循环运行
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info("唤醒词检测任务被取消")
        except Exception as e:
            logger.error(f"唤醒词检测过程中发生错误: {str(e)}", exc_info=True)

    async def _recognize_speech(self):
        """
        识别语音
        """
        try:
            text = self.speech_recognizer.recognize()
            if text:
                logger.info(f"识别结果: {text}")
                # TODO: 处理识别结果
        except Exception as e:
            logger.error(f"语音识别过程中发生错误: {str(e)}", exc_info=True)

async def main():
    assistant = VoiceAssistant()
    try:
        await assistant.start()
    except KeyboardInterrupt:
        logger.info("收到键盘中断信号")
    finally:
        await assistant.stop()

if __name__ == "__main__":
    # Set Windows event loop policy
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Run main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序已停止")
    except Exception as e:
        logger.error(f"程序异常退出: {e}")