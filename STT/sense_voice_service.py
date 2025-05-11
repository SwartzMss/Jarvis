from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess
from pathlib import Path
import torch
import numpy as np
from logger_config import logger
from model_downloader import ModelDownloader
from config import ASR_CONFIG
import os
import json

class SenseVoiceService:
    def __init__(self, model_path=None, sample_rate=None, language=None):
        """Initialize speech recognition service with automatic device, model directory and buffer configuration"""
        logger.info("开始初始化语音识别服务...")
        
        # Device detection - prioritize CUDA
        if torch.cuda.is_available():
            self.device = "cuda"
            logger.info("使用CUDA设备进行推理")
        else:
            self.device = "cpu"
            logger.warning("未检测到CUDA，使用CPU设备进行推理")

        # Model directory - fixed location
        root = Path(__file__).parent
        self.model_dir = Path(model_path or ASR_CONFIG["model_path"])
        logger.info(f"模型目录: {self.model_dir}")

        # Ensure model directory exists
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        # Download model files
        logger.info("开始下载模型文件...")
        downloader = ModelDownloader()
        if not downloader.download_sense_voice_model():
            logger.error("模型文件下载失败")
            raise RuntimeError("模型文件下载失败")
        logger.info("模型文件下载完成")

        # Buffer parameters - fixed configuration
        self.sample_rate = sample_rate or ASR_CONFIG["sample_rate"]
        self.language = language or ASR_CONFIG["language"]
        self.buffer_duration = 0.5  # Reduce buffer duration to 0.5 seconds
        self._buffer = []  # list of numpy arrays
        self._buffer_samples = 0
        logger.info(f"音频缓冲区配置 - 采样率: {self.sample_rate}, 缓冲区时长: {self.buffer_duration}秒")

        # Initialize model
        self.model = None
        self._init_model()

    def _init_model(self):
        """Initialize model"""
        logger.info("开始初始化模型...")
        try:
            self.model = AutoModel(
                model=str(self.model_dir),
                device=self.device,
                disable_update=True
            )
            logger.info("模型初始化成功")
        except Exception as e:
            logger.error(f"模型初始化失败: {e}")
            raise

    def recognize(self, audio_data):
        """Recognize speech from audio data"""
        try:
            logger.debug(f"开始识别音频数据，形状: {audio_data.shape}")
            result = self.transcribe(audio_data, language=self.language)
            if "error" in result:
                logger.error(f"识别错误: {result['error']}")
            return result["text"]
        except Exception as e:
            logger.error(f"识别过程出错: {str(e)}")
            return None

    def transcribe(self, audio_data, language=None, use_itn=True):
        """Transcribe audio data"""
        logger.debug(f"收到音频数据: {audio_data.shape}")
        
        # Get numpy waveform
        if isinstance(audio_data, torch.Tensor):
            arr = audio_data.cpu().numpy()
            logger.debug("将PyTorch张量转换为numpy数组")
        elif isinstance(audio_data, np.ndarray):
            arr = audio_data
            logger.debug("使用numpy数组")
        else:
            logger.error(f"不支持的音频数据类型: {type(audio_data)}")
            return {"error": f"不支持的音频数据类型: {type(audio_data)}"}

        # Normalize
        if arr.dtype != np.float32:
            arr = arr.astype(np.float32) / 32767
            logger.debug("音频数据归一化完成")
        # Multi-dimensional processing
        if arr.ndim == 2:
            arr = arr.mean(axis=1)
            logger.debug("多通道音频数据合并完成")

        # Process current audio data directly
        tensor = torch.from_numpy(arr).float().to(self.device)
        try:
            logger.debug("开始模型推理...")
            res = self.model.generate(
                input=tensor,
                cache={},
                language=language or self.language,
                use_itn=use_itn,
                merge_vad=False,
                merge_length_s=self.buffer_duration
            )
            text = rich_transcription_postprocess(res[0]["text"])
            logger.debug(f"原始识别结果: {res[0]['text']}")
            logger.debug(f"后处理结果: {text}")
            return {"text": text, "emotion": res[0].get("emotion", "NEUTRAL"), "event": res[0].get("event", "Speech")}
        except Exception as e:
            logger.error(f"推理过程出错: {e}")
            return {"error": str(e)}

    def close(self):
        """Release resources"""
        try:
            logger.info("开始释放资源...")
            if hasattr(self, 'model'):
                del self.model
            logger.info("资源释放完成")
        except Exception as e:
            logger.error(f"释放资源时出错: {str(e)}")
