from queue import Queue, Full
from logger_config import logger
import numpy as np
import time

class AudioBroadcaster:
    def __init__(self):
        """初始化音频广播器"""
        logger.info("初始化音频广播器...")
        self.subscribers = []
        self.is_running = True
        self._last_warning_time = 0  # 添加最后警告时间记录
        logger.info("音频广播器初始化完成")

    def subscribe(self, maxsize=1000):
        """订阅音频数据"""
        logger.info("创建新的音频订阅队列...")
        queue = Queue(maxsize=maxsize)
        self.subscribers.append(queue)
        logger.info(f"音频订阅队列创建成功，当前订阅者数量: {len(self.subscribers)}")
        return queue

    def publish(self, audio_data):
        """发布音频数据到所有订阅者"""
        if not self.is_running:
            # 每5秒最多打印一次警告
            current_time = time.time()
            if current_time - self._last_warning_time >= 5:
                logger.warning("广播器已关闭，无法发布数据")
                self._last_warning_time = current_time
            return
            
        logger.debug(f"开始广播音频数据 - 形状: {audio_data.shape}, 类型: {audio_data.dtype}")
        
        # 记录数据统计信息
        max_amplitude = np.max(np.abs(audio_data))
        min_amplitude = np.min(np.abs(audio_data))
        mean_amplitude = np.mean(np.abs(audio_data))
        logger.debug(f"音频数据统计 - 最大幅度: {max_amplitude:.2f}, 最小幅度: {min_amplitude:.2f}, 平均幅度: {mean_amplitude:.2f}")
        
        # 发布到所有订阅者
        for i, queue in enumerate(self.subscribers):
            try:
                if not queue.full():
                    queue.put(audio_data, block=False)
                    logger.debug(f"数据已发布到订阅者 {i+1}/{len(self.subscribers)}")
                else:
                    logger.warning(f"订阅者 {i+1} 的队列已满，丢弃数据")
            except Full:
                logger.warning(f"订阅者 {i+1} 的队列已满，丢弃数据")
            except Exception as e:
                logger.error(f"向订阅者 {i+1} 发布数据时出错: {str(e)}")

    def close(self):
        """关闭广播器"""
        logger.info("开始关闭音频广播器...")
        self.is_running = False
        # 向所有订阅者发送结束信号
        for i, queue in enumerate(self.subscribers):
            try:
                queue.put(None)
                logger.debug(f"已向订阅者 {i+1} 发送结束信号")
            except Exception as e:
                logger.error(f"向订阅者 {i+1} 发送结束信号时出错: {str(e)}")
        logger.info("音频广播器已关闭") 