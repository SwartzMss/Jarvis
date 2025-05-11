import sounddevice as sd
from queue import Queue, Empty, Full
import threading
import numpy as np
import asyncio
import os
import resampy
from wake_word import WakeWordDetector
from speech_recognition import SpeechRecognizer
from tts_client import TTSClient
from logger_config import logger
from audio_broadcaster import AudioBroadcaster

class AudioInput:
    def __init__(self):
        """
        初始化音频输入
        """
        # 目标采样率和帧长度
        self.target_rate = 16000  # ASR要求的采样率
        self.frame_length = 512   # 帧长度
        
        # 设备采样率和帧长度
        self.device_rate = None
        self.device_frame_length = None
        
        # 查找VB-Audio Virtual Cable设备
        self.device = self._find_vb_audio_device()
        
        # 创建音频广播器
        logger.info("创建音频广播器...")
        self.broadcaster = AudioBroadcaster()
        
        # 创建唤醒词检测队列
        self.wake_queue = self.broadcaster.subscribe(maxsize=1000)
        
        # 创建 ASR 队列
        logger.info("订阅ASR音频队列...")
        self.asr_queue = self.broadcaster.subscribe(maxsize=1000)
        logger.info(f"ASR队列创建成功，最大容量: 1000")
        
        # 创建语音识别器
        logger.info("初始化语音识别器...")
        self.speech_recognizer = SpeechRecognizer()
        logger.info("语音识别器初始化完成")
        
        self.in_stream = None
        self.is_running = False
        self.overflow_count = 0  # 添加溢出计数器
        
        # 初始化唤醒词检测器
        logger.info("初始化唤醒词检测器...")
        self.wake_word_detector = WakeWordDetector()
        logger.info("唤醒词检测器初始化完成")
        
        # 创建TTS客户端
        self.tts_client = TTSClient()
        
        # 打印设备信息
        logger.info("可用的输入设备：")
        try:
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:  # 只显示输入设备
                    logger.info(f"{i}: {dev['name']} (输入通道: {dev['max_input_channels']}, 采样率: {dev['default_samplerate']}Hz)")
        except Exception as e:
            logger.error(f"获取设备列表时出错: {str(e)}")
        
        logger.info(f"当前使用的设备: {self.device  if self.device  is not None else '默认设备'}")

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
                audio_data = resampy.resample(
                    audio_data.astype(np.float32),
                    self.device_rate,
                    self.target_rate,
                ).astype(np.int16)
            
            # 4. 重采样之后长度可能因取整偏差而略有出入，统一成 512
            if len(audio_data) > self.frame_length:
                logger.debug(f"截断音频数据: {len(audio_data)} -> {self.frame_length}")
                audio_data = audio_data[: self.frame_length]
            elif len(audio_data) < self.frame_length:
                logger.debug(f"填充音频数据: {len(audio_data)} -> {self.frame_length}")
                audio_data = np.pad(
                    audio_data,
                    (0, self.frame_length - len(audio_data)),
                    mode="constant",
                    constant_values=0,
                )
            
            # 5. 确保最终数据类型是int16
            audio_data = audio_data.astype(np.int16)
            
            # 记录最终音频数据的基本信息
            logger.debug(f"最终音频数据 - 形状: {audio_data.shape}, 类型: {audio_data.dtype}, "
                        f"最小值: {np.min(audio_data)}, 最大值: {np.max(audio_data)}, "
                        f"平均绝对值: {np.mean(np.abs(audio_data)):.2f}")
            
            # 发布音频数据
            logger.debug("开始发布音频数据到广播器...")
            self.broadcaster.publish(audio_data)
            logger.debug("音频数据发布完成")
            
        except Exception as e:
            logger.error(f"音频处理错误: {str(e)}", exc_info=True)

    async def wake_word_loop(self):
        """唤醒词检测循环"""
        logger.info("启动唤醒词检测循环")
        while self.is_running:
            try:
                pcm = self.wake_queue.get(timeout=0.1)
                if pcm is None:
                    break
                    
                # 使用唤醒词检测器
                keyword_index = self.wake_word_detector.process(pcm)
                if keyword_index >= 0:
                    logger.info(f"检测到唤醒词！关键词索引: {keyword_index}")
                    # 播放回应
                    self.tts_client.text_to_speech("主人我在")
                    # 激活语音识别
                    self.speech_recognizer.activate()
                    
            except Empty:
                continue
            except Exception as e:
                logger.error(f"唤醒词检测循环错误: {str(e)}")
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
            self.device_frame_length = int(self.frame_length * self.device_rate / self.target_rate)
            logger.info(f"设备帧长: {self.device_frame_length}")
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
                latency='high'
            )
            self.in_stream.start()
            logger.info(f"音频输入流启动成功，使用设备: {self.device if self.device is not None else '默认设备'}")
        except Exception as e:
            logger.error(f"启动音频输入流失败: {str(e)}", exc_info=True)
            self.is_running = False
            return
        
        # 启动处理线程
        logger.info("启动处理线程...")
        
        # 启动唤醒词检测线程
        def run_wake_word_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.wake_word_loop())
            
        self.wake_thread = threading.Thread(
            target=run_wake_word_loop,
            daemon=True
        )
        self.wake_thread.start()
        
        # 启动语音识别线程
        def run_asr_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            logger.info("开始启动语音识别处理循环...")
            loop.run_until_complete(self.speech_recognizer.start(self.asr_queue))
            logger.info("语音识别处理循环已结束")
            
        self.asr_thread = threading.Thread(
            target=run_asr_loop,
            daemon=True
        )
        self.asr_thread.start()
        logger.info("语音识别线程已启动")
        
        logger.info("音频处理启动完成")

    def stop(self):
        """停止音频处理，释放所有资源"""
        if not self.is_running:
            return
            
        logger.info("开始停止音频处理...")
        self.is_running = False
        
        # 关闭广播器
        logger.info("开始关闭音频广播器...")
        self.broadcaster.close()
        logger.info("音频广播器已关闭")
        
        # 停止语音识别
        logger.info("开始停止语音识别...")
        self.speech_recognizer.stop()
        logger.info("语音识别已停止")
        
        # 关闭TTS客户端
        try:
            logger.info("关闭TTS客户端...")
            self.tts_client.close()
            logger.info("TTS客户端已关闭")
        except Exception as e:
            logger.error(f"关闭TTS客户端失败: {str(e)}", exc_info=True)
        
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
        
        # 等待处理线程结束
        if hasattr(self, 'wake_thread'):
            logger.info("等待唤醒词检测线程结束...")
            self.wake_thread.join(timeout=1.0)
            
        if hasattr(self, 'asr_thread'):
            logger.info("等待语音识别线程结束...")
            self.asr_thread.join(timeout=1.0)
        
        # 释放唤醒词检测器
        try:
            logger.info("释放唤醒词检测器...")
            self.wake_word_detector.delete()
            logger.info("唤醒词检测器已释放")
        except Exception as e:
            logger.error(f"释放唤醒词检测器失败: {str(e)}", exc_info=True)
        
        logger.info("音频处理已完全停止") 