import sounddevice as sd
from queue import Queue, Empty
import numpy as np
import threading
import resampy
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class AudioOutput:
    """
    自适应声道的音频输出类。

    用法：
      audio_out = AdaptiveAudioOutput(blocksize=1024)  # 自动检测设备采样率
      audio_out.start()
      # ...play_audio 每次传入不同声道的音频数据
      audio_out.play_audio(audio_data, input_sr)
      audio_out.stop()
    """
    def __init__(self, blocksize=1024, dtype='int16', samplerate=None):
        """
        初始化音频输出
        
        Args:
            blocksize: 音频块大小
            dtype: 音频数据类型
            samplerate: 采样率，如果为None则自动检测设备默认采样率
        """
        # 获取设备默认采样率
        if samplerate is None:
            try:
                device_info = sd.query_devices(kind='output')
                self.samplerate = int(device_info['default_samplerate'])
                logger.info(f"检测到设备默认采样率: {self.samplerate}Hz")
            except Exception as e:
                logger.warning(f"无法获取设备采样率，使用默认值44100Hz: {str(e)}")
                self.samplerate = 44100
        else:
            self.samplerate = samplerate
            
        self.blocksize  = blocksize
        self.dtype      = dtype
        self._stream    = None
        self._channels  = None
        self._queue     = Queue()
        logger.info(f"初始化音频输出: samplerate={self.samplerate}Hz, blocksize={blocksize}, dtype={dtype}")

    def _ensure_stream(self, channels: int):
        """
        如果流不存在或声道数变化，就创建/重建一个新的 OutputStream。
        """
        # 已有且声道未变，直接返回
        if self._stream and self._channels == channels:
            return

        # 关闭旧流
        if self._stream:
            logger.info(f"关闭旧音频流: channels={self._channels}")
            self._stream.stop()
            self._stream.close()

        self._channels = channels
        logger.info(f"创建新音频流: channels={channels}")
        # 创建新的输出流
        self._stream = sd.OutputStream(
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            channels=self._channels,
            dtype=self.dtype,
            callback=self._audio_callback,
        )
        self._stream.start()
        logger.info("音频流启动成功")

    def _audio_callback(self, outdata, frames, time, status):
        """
        sounddevice 的回调函数：从队列取一帧音频写入 outdata，队列空时输出静音。
        """
        if status:
            logger.warning(f"音频回调状态: {status}")
        try:
            chunk = self._queue.get_nowait()
            # 检查数据格式
            if chunk.shape != (frames, self._channels):
                logger.error(f"音频块形状错误: 期望 ({frames}, {self._channels}), 实际 {chunk.shape}")
                outdata.fill(0)
                return
            # 确保数据范围正确
            if np.max(np.abs(chunk)) > 32767:
                logger.warning(f"音频块数据超出范围: max={np.max(np.abs(chunk))}")
                chunk = np.clip(chunk, -32768, 32767)
            outdata[:] = chunk
        except Empty:
            outdata.fill(0)
        except Exception as e:
            logger.error(f"音频输出异常: {e}")
            outdata.fill(0)

    def _normalize_audio(self, audio: np.ndarray) -> np.ndarray:
        """标准化音频数据到int16范围"""
        if np.max(np.abs(audio)) > 32767:
            logger.warning(f"音频数据超出范围: max={np.max(np.abs(audio))}, 进行归一化")
            # 使用浮点数计算以避免溢出
            audio = audio.astype(np.float32)
            scale = 32767.0 / np.max(np.abs(audio))
            audio = (audio * scale).astype(np.int16)
        return audio

    def play_audio(self, audio_data: np.ndarray, input_sr: int):
        """
        将一段 numpy 数组 audio_data 推入播放队列。

        audio_data: 1D 或 2D 数组，如果是 1D 则视为单声道；如果是 2D，每行代表一帧，每列一个声道。
        input_sr: 传入数据的采样率。
        """
        logger.info(f"开始播放音频: shape={audio_data.shape}, input_sr={input_sr}Hz")
        
        # 检查输入数据
        if not isinstance(audio_data, np.ndarray):
            logger.error(f"输入数据类型错误: {type(audio_data)}")
            return
        
        # 转 numpy 并确保 int16
        audio = np.array(audio_data, dtype=np.int16)
        logger.debug(f"音频数据统计: min={np.min(audio)}, max={np.max(audio)}, mean={np.mean(audio):.2f}")
        
        # 标准化音频数据
        audio = self._normalize_audio(audio)

        # 重采样到目标采样率
        if input_sr != self.samplerate:
            logger.info(f"重采样: {input_sr}Hz -> {self.samplerate}Hz")
            # 对每个声道分别重采样
            if audio.ndim == 2:
                # 计算重采样后的长度
                new_length = int(len(audio) * self.samplerate / input_sr)
                resampled = np.zeros((new_length, audio.shape[1]), dtype=np.float32)
                
                # 对每个声道进行重采样
                for ch in range(audio.shape[1]):
                    # 转换为float32进行重采样
                    ch_data = audio[:, ch].astype(np.float32) / 32767.0
                    resampled[:, ch] = resampy.resample(ch_data, input_sr, self.samplerate, filter='kaiser_best')
                
                # 转回int16
                audio = (resampled * 32767.0).astype(np.int16)
            else:
                # 单声道重采样
                audio = audio.astype(np.float32) / 32767.0
                audio = resampy.resample(audio, input_sr, self.samplerate, filter='kaiser_best')
                audio = (audio * 32767.0).astype(np.int16)
            
            logger.debug(f"重采样后统计: min={np.min(audio)}, max={np.max(audio)}, mean={np.mean(audio):.2f}")

        # 根据维度判断声道数
        if audio.ndim == 1:
            channels = 1
            audio = audio.reshape(-1, 1)
        else:
            channels = audio.shape[1]
        logger.info(f"音频声道数: {channels}")

        # 确保流已针对当前声道数就绪
        self._ensure_stream(channels)

        # 分块入队
        total_chunks = 0
        for i in range(0, len(audio), self.blocksize):
            chunk = audio[i : i + self.blocksize]
            # 最后一块补零
            if len(chunk) < self.blocksize:
                pad = np.zeros((self.blocksize - len(chunk), channels), dtype=np.int16)
                chunk = np.vstack([chunk, pad])
            self._queue.put(chunk)
            total_chunks += 1
        
        logger.info(f"音频数据分块完成: 共 {total_chunks} 块")

    def start(self):
        """
        预启动：建立一个默认的双声道流（如果后续播放是单声道，则会自动重建）。
        """
        logger.info("启动音频输出")
        # 先用双声道打开，避免第一次 play_audio 的延迟
        self._ensure_stream(2)

    def stop(self):
        """
        停止并关闭流。
        """
        logger.info("停止音频输出")
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None