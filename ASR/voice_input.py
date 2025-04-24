import sounddevice as sd
import numpy as np
import threading
import queue
import librosa
import webrtcvad
import logging
import sys
from sense_voice_service import SenseVoiceService

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class VoiceInput:
    """
    语音输入类，支持自动重采样、多通道混合或选择、可配置缓冲长度，并添加VAD检测。
    """
    def __init__(self):
        """
        初始化语音输入类，所有参数都在内部设置
        """
        logger.info("初始化 VoiceInput...")
        
        # 自动检测默认设备信息
        dev_info = sd.query_devices(kind='input')
        self.input_rate = int(dev_info['default_samplerate'])
        self.channels = dev_info['max_input_channels']

        # 目标格式设置
        self.target_rate = 16000  # 模型期望的采样率
        self.mix_channels = True  # 是否将多声道音频取均值混合为单声道
        self.lib_resample = True  # 是否使用 librosa 重采样
        self.chunk_duration = 0.1  # 处理时长0.1秒
        self.chunk_frames = int(self.chunk_duration * self.target_rate)

        # VAD配置
        self.vad_aggressiveness = 0  # 降低VAD敏感度，范围0-3，0最不敏感
        self.vad_frame_duration = 30  # VAD检测的帧长度，单位毫秒
        self.vad = webrtcvad.Vad(self.vad_aggressiveness)
        self.vad_frame_size = int(self.target_rate * self.vad_frame_duration / 1000)
        self.vad_buffer = np.zeros((0,), dtype=np.float32)  # 用于VAD检测的缓冲区
        self.vad_buffer_duration = 0.5  # 增加VAD检测的缓冲区时长到0.5秒
        self.vad_buffer_size = int(self.vad_buffer_duration * self.target_rate)
        
        # 中文语音特征检测配置
        self.min_volume = 0.02  # 最小音量阈值
        self.max_volume = 0.5   # 最大音量阈值
        self.min_freq = 100     # 最小频率阈值（Hz）
        self.max_freq = 1000    # 最大频率阈值（Hz）
        
        # 语音缓存配置
        self.speech_buffer = np.zeros((0,), dtype=np.float32)  # 用于累积语音片段
        self.is_speaking = False  # 是否正在说话
        self.silence_frames = 0  # 连续静音帧计数
        self.max_silence_frames = 10  # 增加最大允许的连续静音帧数
        self.min_speech_frames = 3  # 最小需要连续检测到语音的帧数
        
        logger.debug(f"VAD配置 - 敏感度: {self.vad_aggressiveness}, 帧大小: {self.vad_frame_size}, 缓冲区大小: {self.vad_buffer_size}")

        # 缓冲与队列
        self.audio_queue = queue.Queue()  # 用于存储待处理的音频数据
        self.transcribe_queue = queue.Queue()  # 用于存储待转写的音频数据

        # 录音状态
        self.recording = False

        # 初始化服务
        try:
            self.svc = SenseVoiceService()
            logger.info("SenseVoice 服务初始化成功")
        except Exception as e:
            logger.error(f"SenseVoice 服务初始化失败: {e}")
            self.svc = None
            
        # 文本回调函数
        self.on_text_received = None

    def _audio_callback(self, indata, frames, time, status):
        """音频回调函数"""
        if status:
            logger.warning(f"录音状态: {status}")
        # 放入线程安全队列
        self.audio_queue.put(indata.copy())

    def start(self):
        """开始录音并启动处理线程"""
        if self.recording:
            logger.warning("录音已经在进行中")
            return
            
        logger.info("开始录音...")
        self.recording = True

        # 启动录音线程
        self.record_thread = threading.Thread(target=self._record_loop, daemon=True)
        self.record_thread.start()
        
        # 启动转写线程
        self.transcribe_thread = threading.Thread(target=self._transcribe_loop, daemon=True)
        self.transcribe_thread.start()
        
        logger.info("录音和转写线程已启动")

    def _record_loop(self):
        """录音线程主循环"""
        logger.info("启动录音线程")
        try:
            # 计算块大小，确保至少包含一个VAD帧
            blocksize = int(self.target_rate * self.vad_frame_duration / 1000)  # 30ms的采样点数
            logger.info(f"设置音频块大小: {blocksize} 采样点")
            
            with sd.InputStream(
                samplerate=self.input_rate,
                channels=self.channels,
                dtype='float32',
                blocksize=blocksize,  # 设置块大小
                callback=self._audio_callback,
            ):
                logger.info("音频输入流已打开")
                while self.recording:
                    try:
                        chunk = self.audio_queue.get(timeout=1)
                        self._process_chunk(chunk)
                    except queue.Empty:
                        continue
        except Exception as e:
            logger.error(f"录音错误: {e}")
            self.recording = False

    def _transcribe_loop(self):
        """转写线程主循环"""
        logger.info("启动转写线程")
        while self.recording:
            try:
                # 从转写队列获取音频数据
                audio_data = self.transcribe_queue.get(timeout=0.5)
                if audio_data is None:
                    logger.info("转写队列中没有数据")
                    continue

                logger.info("开始转写")   
                # 处理音频数据
                result = self.svc.transcribe(audio_data, language="auto")
                if result.get("error"):
                    logger.error(f"转写错误: {result['error']}")
                elif result.get("text"):
                    logger.info(f"识别结果: {result['text']}")
                    # 调用文本回调函数
                    if self.on_text_received is not None:
                        self.on_text_received(result["text"])
                    
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"转写错误: {e}")
                continue
                
        logger.info("转写线程已停止")

    def _check_chinese_speech(self, audio_data):
        """检查是否符合中文语音特征"""
        # 计算音量
        volume = np.max(np.abs(audio_data))
        if volume < self.min_volume or volume > self.max_volume:
            logger.debug(f"音量 {volume:.4f} 超出范围 [{self.min_volume}, {self.max_volume}]")
            return False
            
        # 计算频谱
        n_fft = 2048
        hop_length = 512
        D = np.abs(librosa.stft(audio_data, n_fft=n_fft, hop_length=hop_length))
        freqs = librosa.fft_frequencies(sr=self.target_rate, n_fft=n_fft)
        
        # 计算主要频率成分
        power = np.sum(D, axis=1)
        main_freq = freqs[np.argmax(power)]
        
        if main_freq < self.min_freq or main_freq > self.max_freq:
            logger.debug(f"主要频率 {main_freq:.1f}Hz 超出范围 [{self.min_freq}, {self.max_freq}]Hz")
            return False
            
        return True

    def _process_chunk(self, raw_chunk):
        """处理音频块"""        
        # 原始浮点 PCM [-1, 1]
        data = raw_chunk.astype(np.float32)

        # 处理多通道 -> 单通道
        if data.ndim == 2:
            if self.mix_channels:
                mono = data.mean(axis=1)
            else:
                mono = data[:, 0]
        else:
            mono = data.flatten()

        # 重采样到目标采样率
        if self.input_rate != self.target_rate:
            resampled = librosa.resample(
                mono, orig_sr=self.input_rate, target_sr=self.target_rate
            )
        else:
            resampled = mono

        # 累积音频数据到VAD缓冲区
        self.vad_buffer = np.concatenate([self.vad_buffer, resampled])
        if len(self.vad_buffer) > self.vad_buffer_size:
            self.vad_buffer = self.vad_buffer[-self.vad_buffer_size:]
            
            # 进行 VAD 检测
            is_speech = self._vad_detect(self.vad_buffer)
            logger.debug(f"VAD检测结果: {is_speech}")
            
            if is_speech:
                # 检查是否符合中文语音特征
                if not self._check_chinese_speech(self.vad_buffer):
                    is_speech = False
                    logger.debug("不符合中文语音特征")
            
            if is_speech:
                # 检测到语音
                self.silence_frames = 0  # 重置静音计数
                if not self.is_speaking:
                    # 从静音变为语音，开始新的语音片段
                    self.is_speaking = True
                    self.speech_buffer = np.zeros((0,), dtype=np.float32)  # 清空之前的缓存
                    logger.info("🎤 检测到语音开始")
                
                # 累积音频数据到语音缓冲区
                self.speech_buffer = np.concatenate([self.speech_buffer, resampled])
            else:
                # 检测到静音
                if self.is_speaking:
                    self.silence_frames += 1
                    if self.silence_frames >= self.max_silence_frames:
                        # 连续静音帧数达到阈值，认为语音结束
                        self.is_speaking = False
                        logger.info("🔕 检测到语音结束")
                        
                        # 将累积的语音数据放入转写队列
                        if len(self.speech_buffer) > 0:
                            logger.info("📤 发送语音片段到转写服务")
                            self.transcribe_queue.put(self.speech_buffer)
                            self.speech_buffer = np.zeros((0,), dtype=np.float32)
                    else:
                        # 仍在语音片段中，继续累积音频数据
                        self.speech_buffer = np.concatenate([self.speech_buffer, resampled])

    def _vad_detect(self, audio_data):
        """使用 WebRTC VAD 检测语音活动"""
        # 将浮点音频数据转换为 16 位整数
        audio_int16 = (audio_data * 32767).astype(np.int16)
        
        # 将音频数据分割成 VAD 帧
        frames = []
        for i in range(0, len(audio_int16), self.vad_frame_size):
            frame = audio_int16[i:i + self.vad_frame_size]
            if len(frame) == self.vad_frame_size:
                frames.append(frame)
        
        # 检测每个帧
        speech_frames = 0
        for frame in frames:
            if self.vad.is_speech(frame.tobytes(), self.target_rate):
                speech_frames += 1
        
        # 如果超过一半的帧被检测为语音，则认为有语音活动
        return speech_frames > len(frames) / 2

    def stop(self):
        """停止录音"""
        if not self.recording:
            logger.warning("录音已经停止")
            return
            
        logger.info("正在停止录音...")
        self.recording = False
        
        # 等待线程结束
        if hasattr(self, 'record_thread'):
            self.record_thread.join(timeout=1)
        if hasattr(self, 'transcribe_thread'):
            self.transcribe_thread.join(timeout=1)
            
        logger.info("录音已停止")
