import pvporcupine
import numpy as np
from config import PICOVOICE_ACCESS_KEY, WAKE_WORD

class WakeWordDetector:
    def __init__(self):
        """初始化唤醒词检测器
        
        Args:
            access_key (str): Picovoice访问密钥
            wake_word (str): 唤醒词，默认使用"jarvis"
        """
        self.porcupine = pvporcupine.create(
            access_key=PICOVOICE_ACCESS_KEY,
            keywords=[WAKE_WORD],
            sensitivities=[0.7]
        )
        
    def process(self, pcm):
        """处理音频数据
        
        Args:
            pcm (numpy.ndarray): 音频数据
            
        Returns:
            int: 检测到的唤醒词索引，-1表示未检测到
        """
        try:
            return self.porcupine.process(pcm)
        except Exception as e:
            print(f"唤醒词检测错误: {str(e)}")
            return -1
            
    def delete(self):
        """释放资源"""
        self.porcupine.delete() 