import sounddevice as sd
from queue import Queue, Empty
import threading
import numpy as np
import asyncio
import os
import resampy
from wake_word import WakeWordDetector

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
        self.asr_queue = Queue()
        self.in_stream = None
        self.is_running = False
        
        # 初始化唤醒词检测器
        self.wake_word_detector = WakeWordDetector()
        
        # 打印设备信息
        print("\n可用的输入设备：")
        try:
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:  # 只显示输入设备
                    print(f"{i}: {dev['name']} (输入通道: {dev['max_input_channels']}, 采样率: {dev['default_samplerate']}Hz)")
        except Exception as e:
            print(f"获取设备列表时出错: {str(e)}")
        
        print(f"\n当前使用的设备: {device if device is not None else '默认设备'}")

    def _find_vb_audio_device(self):
        """查找VB-Audio Virtual Cable设备"""
        try:
            devices = sd.query_devices()
            # 优先使用采样率为16000Hz的设备
            for i, dev in enumerate(devices):
                if (dev['max_input_channels'] > 0 and 
                    'CABLE Output' in dev['name'] and 
                    dev['default_samplerate'] == 16000.0):
                    print(f"找到VB-Audio Virtual Cable设备: {dev['name']}")
                    return i
            
            # 如果没有16000Hz的设备，使用44100Hz的设备
            for i, dev in enumerate(devices):
                if (dev['max_input_channels'] > 0 and 
                    'CABLE Output' in dev['name'] and 
                    dev['default_samplerate'] == 44100.0):
                    print(f"找到VB-Audio Virtual Cable设备: {dev['name']}")
                    return i
            
            # 如果还是没有找到，使用任何CABLE Output设备
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0 and 'CABLE Output' in dev['name']:
                    print(f"找到VB-Audio Virtual Cable设备: {dev['name']}")
                    return i
            
            print("未找到VB-Audio Virtual Cable设备，将使用默认设备")
            return None
        except Exception as e:
            print(f"查找VB-Audio设备时出错: {str(e)}")
            return None

    def audio_callback(self, indata, frames, time, status):
        """音频回调函数"""
        try:
            # 1. 转换为numpy数组并确保是int16类型
            audio_data = indata.copy().flatten().astype(np.int16)
            
            # 2. 确保读取长度正确
            if len(audio_data) != self.device_frame_length:
                print(f"帧长异常: 期待 {self.device_frame_length}, 实际 {len(audio_data)}")
                return
            
            # 3. 如果设备采样率 ≠ 16 kHz，则重采样
            if self.device_rate != self.target_rate:
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
            
            # 4. 重采样之后长度可能因取整偏差而略有出入，统一成 512
            if len(audio_data) > self.frame_length:
                audio_data = audio_data[:self.frame_length]
            elif len(audio_data) < self.frame_length:
                audio_data = np.pad(
                    audio_data,
                    (0, self.frame_length - len(audio_data)),
                    mode="constant",
                    constant_values=0,
                )
            
            # 5. 确保最终数据类型是int16
            audio_data = audio_data.astype(np.int16)
            
            # 6. 放入队列
            self.asr_queue.put(audio_data)
            
        except Exception as e:
            print(f"音频处理错误: {str(e)}")

    async def process_audio(self, pcm):
        """处理音频数据"""
        try:
            # 使用唤醒词检测器
            keyword_index = self.wake_word_detector.process(pcm)
            if keyword_index >= 0:
                print(f"检测到唤醒词！")
                return True
            return False
        except Exception as e:
            print(f"处理错误: {str(e)}")
            return False

    async def wake_word_loop(self):
        """唤醒词检测循环"""
        while self.is_running:
            try:
                pcm = self.asr_queue.get(timeout=0.1)  # 添加超时
                if pcm is None:
                    break
                await self.process_audio(pcm)
            except Empty:
                continue
            except Exception as e:
                print(f"唤醒词检测循环错误: {str(e)}")
                continue

    def start(self):
        """启动音频处理"""
        if self.is_running:
            return
            
        self.is_running = True
        
        # 获取设备信息
        try:
            device_info = sd.query_devices(self.device)
            self.device_rate = int(device_info['default_samplerate'])
            print(f"使用设备采样率: {self.device_rate}Hz")
        except Exception as e:
            print(f"获取设备信息失败: {str(e)}")
            self.is_running = False
            return
        
        # 初始化音频输入流
        try:
            self.in_stream = sd.InputStream(
                device=self.device,  # 使用指定的设备
                samplerate=self.device_rate,  # 使用设备的默认采样率
                blocksize=self.device_frame_length,
                channels=1,
                callback=self.audio_callback,
                dtype=np.int16
            )
            self.in_stream.start()
            print(f"音频输入流启动成功，使用设备: {self.device if self.device is not None else '默认设备'}")
        except Exception as e:
            print(f"启动音频输入流失败: {str(e)}")
            self.is_running = False
            return
        
        # 启动处理线程
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.process_thread = threading.Thread(
            target=lambda: loop.run_until_complete(self.wake_word_loop()),
            daemon=True
        )
        self.process_thread.start()

    def stop(self):
        """停止音频处理"""
        if not self.is_running:
            return
            
        self.is_running = False
        
        # 停止音频流
        if self.in_stream:
            try:
                self.in_stream.stop()
                self.in_stream.close()
                self.in_stream = None
            except Exception as e:
                print(f"关闭音频输入流失败: {str(e)}")
        
        # 清空队列
        while not self.asr_queue.empty():
            try:
                self.asr_queue.get_nowait()
            except Empty:
                break
        
        # 等待处理线程结束
        if hasattr(self, 'process_thread'):
            self.process_thread.join(timeout=1.0)
        
        # 释放唤醒词检测器
        try:
            self.wake_word_detector.delete()
        except Exception as e:
            print(f"释放唤醒词检测器失败: {str(e)}") 