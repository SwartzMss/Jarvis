import pvporcupine
import pyaudio
import numpy as np
import resampy
import asyncio
from logger_config import logger
from config import (
    PICOVOICE_ACCESS_KEY,
    WAKE_WORD,
    CUSTOM_WAKE_WORD_MODEL_PATH,
)
from tts_client import tts_client

class WakeWordDetector:
    def __init__(self, sensitivity: float = 0.8):
        """初始化 Porcupine + PyAudio，并做好重采样准备"""
        # 获取当前运行的事件循环
        self.loop = asyncio.get_running_loop()
        
        # 用于存储正在进行的TTS任务
        self.current_tts_task = None
        
        # 1. 创建 Porcupine 引擎（其固定采样率 = 16 000 Hz）
        self.porcupine = pvporcupine.create(
            access_key=PICOVOICE_ACCESS_KEY,
            keyword_paths=[CUSTOM_WAKE_WORD_MODEL_PATH] if CUSTOM_WAKE_WORD_MODEL_PATH else None,
            keywords=[WAKE_WORD] if not CUSTOM_WAKE_WORD_MODEL_PATH else None,
            sensitivities=[sensitivity],
        )
        self.target_rate = self.porcupine.sample_rate        # 16000
        self.frame_length = self.porcupine.frame_length       # 512

        # 2. 打印音频设备信息
        self.audio = pyaudio.PyAudio()
        dev_info = self.audio.get_default_input_device_info()
        self.device_rate = int(dev_info["defaultSampleRate"])  # 例如 44100
        logger.info(
            f"输入设备: {dev_info['name']} | 原生采样率: {self.device_rate} Hz | "
            f"Porcupine 采样率: {self.target_rate} Hz"
        )

        # 3. 计算"读多少帧"才能在重采样后得到正好 512 帧
        #    device_frames ≈ 512 * Rdevice / 16000
        self.device_frame_length = int(
            round(self.frame_length * self.device_rate / self.target_rate)
        )
        logger.info(
            f"回调每次读取 {self.device_frame_length} 帧（{self.device_rate} Hz）→ "
            f"重采样后 ≈ {self.frame_length} 帧（{self.target_rate} Hz）"
        )

        # 4. 打开流（用声卡原生速率采）
        self.stream = self.audio.open(
            rate=self.device_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=self.device_frame_length,
            stream_callback=self._audio_callback,
        )

        logger.info("Wake‑word detector 初始化完成 ✅")

    async def _play_tts(self, text: str):
        """播放TTS的异步函数"""
        try:
            logger.info("开始播放TTS...")
            success = await tts_client.play_text(text)
            if success:
                logger.info("TTS播放完成")
            else:
                logger.error("TTS播放失败")
        except Exception as e:
            logger.error(f"TTS播放出错: {str(e)}", exc_info=True)

    # --------------------------------------------------------------------- #
    #                                回调                                   #
    # --------------------------------------------------------------------- #
    def _audio_callback(self, in_data, frame_count, time_info, status):
        try:
            # 1. bytes → int16 ndarray
            audio_data = np.frombuffer(in_data, dtype=np.int16)

            # 2. 确保读取长度正确
            if len(audio_data) != self.device_frame_length:
                logger.warning(
                    f"帧长异常: 期待 {self.device_frame_length}, 实际 {len(audio_data)}"
                )
                return (in_data, pyaudio.paContinue)

            # 3. 如果设备采样率 ≠ 16 kHz，则重采样
            if self.device_rate != self.target_rate:
                audio_data = resampy.resample(
                    audio_data.astype(np.float32),
                    self.device_rate,
                    self.target_rate,
                ).astype(np.int16)

            # 4. 重采样之后长度可能因取整偏差而略有出入，统一成 512
            if len(audio_data) > self.frame_length:
                audio_data = audio_data[: self.frame_length]
            elif len(audio_data) < self.frame_length:
                audio_data = np.pad(
                    audio_data,
                    (0, self.frame_length - len(audio_data)),
                    mode="constant",
                    constant_values=0,
                )

            # 5. 送入 Porcupine
            if self.porcupine.process(audio_data) >= 0:
                logger.info(f"⚡ 检测到唤醒词: {WAKE_WORD}")
                # 播放提示音
                if self.current_tts_task is None or self.current_tts_task.done():
                    # 使用call_soon_threadsafe将任务安全地提交到主事件循环
                    self.loop.call_soon_threadsafe(
                        lambda: self._schedule_tts("主人，有啥吩咐")
                    )
                    logger.info("已创建新的TTS播放任务")

            return (in_data, pyaudio.paContinue)

        except Exception as exc:
            logger.error("音频回调异常", exc_info=True)
            return (in_data, pyaudio.paAbort)

    def _schedule_tts(self, text: str):
        """在主事件循环中调度TTS任务"""
        if self.current_tts_task is None or self.current_tts_task.done():
            self.current_tts_task = asyncio.create_task(self._play_tts(text))

    # --------------------------------------------------------------------- #
    #                         外部可调用的工具函数                           #
    # --------------------------------------------------------------------- #
    def close(self):
        """释放资源"""
        try:
            self.stream.stop_stream()
            self.stream.close()
            self.audio.terminate()
            self.porcupine.delete()
            # 等待TTS任务完成
            if self.current_tts_task and not self.current_tts_task.done():
                self.loop.run_until_complete(self.current_tts_task)
            logger.info("Wake‑word detector 已关闭并清理资源")
        except Exception as exc:
            logger.error("关闭时异常", exc_info=True)
