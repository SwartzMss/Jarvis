import pvporcupine
import pyaudio
import struct
import numpy as np
from logger_config import logger
from config import PICOVOICE_ACCESS_KEY, WAKE_WORD, CUSTOM_WAKE_WORD_MODEL_PATH, SAMPLE_RATE, CHUNK_SIZE
import resampy

class WakeWordDetector:
    def __init__(self, sensitivity=0.5):
        """
        初始化语音唤醒检测器
        :param sensitivity: 灵敏度，范围0-1，值越大越敏感
        """
        try:
            logger.info(f"正在初始化Porcupine，使用唤醒词: {WAKE_WORD}")
            logger.info(f"访问密钥: {PICOVOICE_ACCESS_KEY[:5]}...{PICOVOICE_ACCESS_KEY[-5:]}")
            
            self.porcupine = pvporcupine.create(
                access_key=PICOVOICE_ACCESS_KEY,
                keyword_paths=[CUSTOM_WAKE_WORD_MODEL_PATH] if CUSTOM_WAKE_WORD_MODEL_PATH else None,
                keywords=[WAKE_WORD] if not CUSTOM_WAKE_WORD_MODEL_PATH else None,
                sensitivities=[sensitivity]  # 设置灵敏度
            )
            
            # 获取并打印音频设备信息
            self.audio = pyaudio.PyAudio()
            dev_info = self.audio.get_default_input_device_info()
            self.input_sample_rate = int(dev_info['defaultSampleRate'])
            logger.info(f"默认输入设备: {dev_info['name']}")
            logger.info(f"输入采样率: {self.input_sample_rate}")
            logger.info(f"声道数: {dev_info['maxInputChannels']}")
            
            # 计算正确的帧长度
            self.frame_length = self.porcupine.frame_length
            self.input_chunk_size = self.frame_length  # 使用固定的帧长度
            
            # 配置音频流
            self.stream = self.audio.open(
                rate=self.porcupine.sample_rate,  # 直接使用Porcupine的采样率
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self.frame_length,
                stream_callback=self._audio_callback
            )
            
            # 能量检测相关
            self.energy_threshold = 1000  # 能量阈值
            self.energy_window = 10  # 能量检测窗口大小
            self.energy_buffer = []
            
            self.is_running = True
            
            logger.info(f"音频流配置 - 采样率: {self.porcupine.sample_rate}, 帧长度: {self.frame_length}")
            logger.info(f"灵敏度设置: {sensitivity}")
            logger.info("语音唤醒检测器初始化成功")
        except Exception as e:
            logger.error(f"语音唤醒检测器初始化失败: {str(e)}", exc_info=True)
            raise

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """
        音频回调函数
        """
        try:
            if status:
                logger.warning(f"音频流状态: {status}")
            
            # 将音频数据转换为numpy数组
            audio_data = np.frombuffer(in_data, dtype=np.int16)
            
            # 确保数据长度正确
            if len(audio_data) != self.frame_length:
                logger.warning(f"音频数据长度不匹配: 期望 {self.frame_length}, 实际 {len(audio_data)}")
                return (in_data, pyaudio.paContinue)
            
            # 计算音频能量
            energy = np.sum(np.abs(audio_data)) / len(audio_data)
            self.energy_buffer.append(energy)
            if len(self.energy_buffer) > self.energy_window:
                self.energy_buffer.pop(0)
            
            # 计算平均能量
            avg_energy = np.mean(self.energy_buffer)
            
            # 如果能量超过阈值，进行唤醒词检测
            if avg_energy > self.energy_threshold:
                logger.debug(f"检测到声音，能量值: {avg_energy:.2f}")
                if self.porcupine.process(audio_data) >= 0:
                    logger.info(f"检测到唤醒词 {WAKE_WORD}！")
                    return (in_data, pyaudio.paContinue)
            
            return (in_data, pyaudio.paContinue)
        except Exception as e:
            logger.error(f"音频回调处理出错: {str(e)}", exc_info=True)
            return (in_data, pyaudio.paAbort)

    def set_sensitivity(self, sensitivity):
        """
        设置灵敏度
        :param sensitivity: 灵敏度，范围0-1，值越大越敏感
        """
        try:
            self.porcupine.delete()
            self.porcupine = pvporcupine.create(
                access_key=PICOVOICE_ACCESS_KEY,
                keyword_paths=[CUSTOM_WAKE_WORD_MODEL_PATH] if CUSTOM_WAKE_WORD_MODEL_PATH else None,
                keywords=[WAKE_WORD] if not CUSTOM_WAKE_WORD_MODEL_PATH else None,
                sensitivities=[sensitivity]
            )
            logger.info(f"灵敏度已更新: {sensitivity}")
        except Exception as e:
            logger.error(f"更新灵敏度失败: {str(e)}", exc_info=True)

    def set_energy_threshold(self, threshold):
        """
        设置能量阈值
        :param threshold: 能量阈值，值越小越敏感
        """
        self.energy_threshold = threshold
        logger.info(f"能量阈值已更新: {threshold}")

    def detect(self):
        """
        检测唤醒词
        :return: 如果检测到唤醒词返回True，否则返回False
        """
        try:
            # 音频处理在回调函数中进行
            return False
        except Exception as e:
            logger.error(f"唤醒词检测过程中出错: {str(e)}", exc_info=True)
            return False

    def close(self):
        """
        释放资源
        """
        try:
            self.is_running = False
            if hasattr(self, 'stream'):
                self.stream.stop_stream()
                self.stream.close()
                logger.debug("音频流已关闭")
            if hasattr(self, 'audio'):
                self.audio.terminate()
                logger.debug("PyAudio已终止")
            if hasattr(self, 'porcupine'):
                self.porcupine.delete()
                logger.debug("Porcupine资源已释放")
            logger.info("语音唤醒检测器资源已释放")
        except Exception as e:
            logger.error(f"释放资源时出错: {str(e)}", exc_info=True) 