import numpy as np
import sounddevice as sd
from logger_config import logger
from config import SAMPLE_RATE, CHANNELS, CHUNK_SIZE, ASR_CONFIG
from sense_voice_service import SenseVoiceService

class SpeechRecognizer:
    def __init__(self):
        """
        初始化语音识别器
        """
        try:
            logger.info("正在初始化语音识别器...")
            self.sample_rate = SAMPLE_RATE
            self.channels = CHANNELS
            self.chunk_size = CHUNK_SIZE
            self.is_recording = False
            self.audio_queue = []
            
            # 初始化SenseVoice服务
            self.sense_voice = SenseVoiceService(
                model_path=ASR_CONFIG["model_path"],
                sample_rate=ASR_CONFIG["sample_rate"],
                language=ASR_CONFIG["language"]
            )
            
            logger.info("语音识别器初始化成功")
        except Exception as e:
            logger.error(f"语音识别器初始化失败: {str(e)}", exc_info=True)
            raise

    def start_recording(self):
        """
        开始录音
        """
        try:
            if not self.is_recording:
                self.is_recording = True
                self.audio_queue = []
                logger.info("开始录音...")
        except Exception as e:
            logger.error(f"开始录音时出错: {str(e)}", exc_info=True)
            raise

    def stop_recording(self):
        """
        停止录音
        """
        try:
            if self.is_recording:
                self.is_recording = False
                logger.info("停止录音...")
        except Exception as e:
            logger.error(f"停止录音时出错: {str(e)}", exc_info=True)
            raise

    def process_audio(self, audio_data):
        """
        处理音频数据
        :param audio_data: 音频数据
        """
        try:
            if self.is_recording:
                # 将音频数据添加到队列
                self.audio_queue.append(audio_data)
                logger.debug(f"收到音频数据，当前队列长度: {len(self.audio_queue)}")
        except Exception as e:
            logger.error(f"处理音频数据时出错: {str(e)}", exc_info=True)
            raise

    def recognize(self):
        """
        识别语音
        :return: 识别结果文本
        """
        try:
            if not self.audio_queue:
                logger.warning("没有可识别的音频数据")
                return None

            # 合并所有音频数据
            audio_data = np.concatenate(self.audio_queue)
            logger.info(f"开始识别，音频长度: {len(audio_data)} 采样点")

            # 调用SenseVoice进行语音识别
            text = self.sense_voice.recognize(audio_data)

            # 清空音频队列
            self.audio_queue = []
            
            logger.info(f"识别完成: {text}")
            return text
        except Exception as e:
            logger.error(f"语音识别过程中出错: {str(e)}", exc_info=True)
            return None

    def close(self):
        """
        释放资源
        """
        try:
            if self.is_recording:
                self.stop_recording()
            if hasattr(self, 'sense_voice'):
                self.sense_voice.close()
            logger.info("语音识别器资源已释放")
        except Exception as e:
            logger.error(f"释放资源时出错: {str(e)}", exc_info=True) 