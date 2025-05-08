import sounddevice as sd
from queue import Queue, Empty
import threading
import numpy as np
import asyncio
import os
import resampy
import logging
from wake_word import WakeWordDetector

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,  # 改为 DEBUG 级别以获取更多信息
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AudioInput:
    def __init__(self, samplerate=16000, blocksize=1024, device=None):
        """
        初始化音频输入
        
        Args:
            samplerate: 采样率
            blocksize: 块大小
            device: 音频设备名称或索引，None表示使用默认设备
        """
        # 目标采样率和帧长度
        self.target_rate = 16000  # Porcupine要求的采样率
        self.frame_length = 512   # Porcupine要求的帧长度
        
        # 设备采样率和帧长度
        self.device_rate = samplerate
        self.device_frame_length = blocksize
        
        # 查找VB-Audio Virtual Cable设备
        if device is None:
            device = self._find_vb_audio_device()
        
        self.device = device
        self.asr_queue = Queue(maxsize=100)  # 限制队列大小
        self.in_stream = None
        self.is_running = False
        self.overflow_count = 0  # 添加溢出计数器
        
        # 初始化唤醒词检测器
        logger.info("初始化唤醒词检测器...")
        self.wake_word_detector = WakeWordDetector()
        logger.info("唤醒词检测器初始化完成")
        
        # 打印设备信息
        logger.info("\n可用的输入设备：")
        try:
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:  # 只显示输入设备
                    logger.info(f"{i}: {dev['name']} (输入通道: {dev['max_input_channels']}, 采样率: {dev['default_samplerate']}Hz)")
        except Exception as e:
            logger.error(f"获取设备列表时出错: {str(e)}")
        
        logger.info(f"当前使用的设备: {device if device is not None else '默认设备'}")

    def _find_vb_audio_device(self):
        """查找VB-Audio Virtual Cable设备"""
        try:
            devices = sd.query_devices()
            # 优先使用采样率为16000Hz的设备
            for i, dev in enumerate(devices):
                if (dev['max_input_channels'] > 0 and 
                    'CABLE Output' in dev['name'] and 
                    dev['default_samplerate'] == 16000.0):
                    logger.info(f"找到VB-Audio Virtual Cable设备: {dev['name']}")
                    return i
            
            # 如果没有16000Hz的设备，使用44100Hz的设备
            for i, dev in enumerate(devices):
                if (dev['max_input_channels'] > 0 and 
                    'CABLE Output' in dev['name'] and 
                    dev['default_samplerate'] == 44100.0):
                    logger.info(f"找到VB-Audio Virtual Cable设备: {dev['name']}")
                    return i
            
            # 如果还是没有找到，使用任何CABLE Output设备
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0 and 'CABLE Output' in dev['name']:
                    logger.info(f"找到VB-Audio Virtual Cable设备: {dev['name']}")
                    return i
            
            logger.warning("未找到VB-Audio Virtual Cable设备，将使用默认设备")
            return None
        except Exception as e:
            logger.error(f"查找VB-Audio设备时出错: {str(e)}")
            return None

    def audio_callback(self, indata, frames, time, status):
        """音频回调函数"""
        try:
            if status:
                self.overflow_count += 1
                if self.overflow_count % 10 == 0:
                    logger.warning(f"音频回调状态: {status}, 溢出次数: {self.overflow_count}")
            
            # 1. 转换为numpy数组并确保是int16类型
            audio_data = indata.copy().flatten().astype(np.int16)
            
            # 记录原始音频数据的基本信息
            max_amplitude = np.max(np.abs(audio_data))
            min_amplitude = np.min(np.abs(audio_data))
            mean_amplitude = np.mean(np.abs(audio_data))
            logger.debug(f"原始音频数据 - 形状: {audio_data.shape}, 类型: {audio_data.dtype}, "
                        f"最小值: {np.min(audio_data)}, 最大值: {np.max(audio_data)}, "
                        f"平均绝对值: {mean_amplitude:.2f}, 最大绝对值: {max_amplitude}")
            
            # 检查音频数据是否有效（降低阈值到10）
            if max_amplitude < 10:  # 降低阈值
                logger.debug(f"音频数据幅度太小 (最大绝对值: {max_amplitude:.2f})，可能是静音")
                return
            
            # 2. 确保读取长度正确
            if len(audio_data) != self.device_frame_length:
                logger.warning(f"帧长异常: 期待 {self.device_frame_length}, 实际 {len(audio_data)}")
                return
            
            # 3. 如果设备采样率 ≠ 16 kHz，则重采样
            if self.device_rate != self.target_rate:
                logger.debug(f"重采样: {self.device_rate}Hz -> {self.target_rate}Hz")
                # 转换为float32进行重采样
                audio_float = audio_data.astype(np.float32) / 32767.0
                # 重采样
                resampled = resampy.resample(
                    audio_float,
                    self.device_rate,
                    self.target_rate,
                )
                # 转回int16
                audio_data = (resampled * 32767).astype(np.int16)
                logger.debug(f"重采样后 - 形状: {audio_data.shape}, 类型: {audio_data.dtype}, "
                           f"最大值: {np.max(audio_data)}, 最小值: {np.min(audio_data)}")
            
            # 4. 重采样之后长度可能因取整偏差而略有出入，统一成 512
            if len(audio_data) > self.frame_length:
                logger.debug(f"截断音频数据: {len(audio_data)} -> {self.frame_length}")
                audio_data = audio_data[:self.frame_length]
            elif len(audio_data) < self.frame_length:
                logger.debug(f"填充音频数据: {len(audio_data)} -> {self.frame_length}")
                # 使用线性插值填充
                x_old = np.linspace(0, 1, len(audio_data))
                x_new = np.linspace(0, 1, self.frame_length)
                audio_data = np.interp(x_new, x_old, audio_data).astype(np.int16)
            
            # 5. 确保最终数据类型是int16
            audio_data = audio_data.astype(np.int16)
            
            # 记录最终音频数据的基本信息
            logger.debug(f"最终音频数据 - 形状: {audio_data.shape}, 类型: {audio_data.dtype}, "
                        f"最小值: {np.min(audio_data)}, 最大值: {np.max(audio_data)}, "
                        f"平均绝对值: {np.mean(np.abs(audio_data)):.2f}")
            
            # 6. 放入队列，如果队列满了就丢弃数据
            try:
                self.asr_queue.put_nowait(audio_data)
            except Queue.Full:
                logger.warning("音频队列已满，丢弃数据")
            
        except Exception as e:
            logger.error(f"音频处理错误: {str(e)}", exc_info=True)

    async def process_audio(self, pcm):
        """处理音频数据"""
        try:
            # 记录音频数据的基本信息
            logger.debug(f"处理音频数据 - 形状: {pcm.shape}, 类型: {pcm.dtype}, "
                        f"最小值: {np.min(pcm)}, 最大值: {np.max(pcm)}, "
                        f"平均值: {np.mean(pcm)}")
            
            # 使用唤醒词检测器
            keyword_index = self.wake_word_detector.process(pcm)
            if keyword_index >= 0:
                logger.info(f"检测到唤醒词！关键词索引: {keyword_index}")
                return True
            return False
        except Exception as e:
            logger.error(f"处理错误: {str(e)}", exc_info=True)
            return False

    async def wake_word_loop(self):
        """唤醒词检测循环"""
        logger.info("启动唤醒词检测循环")
        while self.is_running:
            try:
                pcm = self.asr_queue.get(timeout=0.1)  # 添加超时
                if pcm is None:
                    break
                await self.process_audio(pcm)
            except Empty:
                continue
            except Exception as e:
                logger.error(f"唤醒词检测循环错误: {str(e)}", exc_info=True)
                continue
        logger.info("唤醒词检测循环结束")

    def start(self):
        """启动音频处理"""
        if self.is_running:
            return
            
        self.is_running = True
        logger.info("开始启动音频处理...")
        
        # 获取设备信息
        try:
            device_info = sd.query_devices(self.device)
            self.device_rate = int(device_info['default_samplerate'])
            logger.info(f"使用设备采样率: {self.device_rate}Hz")
            logger.info(f"设备信息: {device_info}")
        except Exception as e:
            logger.error(f"获取设备信息失败: {str(e)}", exc_info=True)
            self.is_running = False
            return
        
        # 初始化音频输入流
        try:
            logger.info("初始化音频输入流...")
            self.in_stream = sd.InputStream(
                device=self.device,
                samplerate=self.device_rate,
                blocksize=self.device_frame_length,
                channels=1,
                callback=self.audio_callback,
                dtype=np.int16,
                latency='low'
            )
            self.in_stream.start()
            logger.info(f"音频输入流启动成功，使用设备: {self.device if self.device is not None else '默认设备'}")
        except Exception as e:
            logger.error(f"启动音频输入流失败: {str(e)}", exc_info=True)
            self.is_running = False
            return
        
        # 启动处理线程
        logger.info("启动处理线程...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.process_thread = threading.Thread(
            target=lambda: loop.run_until_complete(self.wake_word_loop()),
            daemon=True
        )
        self.process_thread.start()
        logger.info("音频处理启动完成")

    def stop(self):
        """停止音频处理"""
        if not self.is_running:
            return
            
        logger.info("开始停止音频处理...")
        self.is_running = False
        
        # 停止音频流
        if self.in_stream:
            try:
                logger.info("停止音频输入流...")
                self.in_stream.stop()
                self.in_stream.close()
                self.in_stream = None
                logger.info("音频输入流已停止")
            except Exception as e:
                logger.error(f"关闭音频输入流失败: {str(e)}", exc_info=True)
        
        # 清空队列
        logger.info("清空音频队列...")
        while not self.asr_queue.empty():
            try:
                self.asr_queue.get_nowait()
            except Empty:
                break
        
        # 等待处理线程结束
        if hasattr(self, 'process_thread'):
            logger.info("等待处理线程结束...")
            self.process_thread.join(timeout=1.0)
        
        # 释放唤醒词检测器
        try:
            logger.info("释放唤醒词检测器...")
            self.wake_word_detector.delete()
            logger.info("唤醒词检测器已释放")
        except Exception as e:
            logger.error(f"释放唤醒词检测器失败: {str(e)}", exc_info=True)
        
        logger.info("音频处理已完全停止") 