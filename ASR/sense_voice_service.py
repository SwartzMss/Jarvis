from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess
import os
from pathlib import Path
import torch
import numpy as np
import traceback
import yaml
import logging
from tools.model_downloader import ModelDownloader

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class SenseVoiceService:
    def __init__(self):
        """初始化语音识别服务，自动管理设备、模型目录和缓冲配置"""
        logger.info("初始化 SenseVoice 服务...")
        
        # 设备检测 - 优先使用 CUDA
        if torch.cuda.is_available():
            self.device = "cuda"
            logger.info("使用 CUDA 设备")
        else:
            self.device = "cpu"
            logger.warning("未检测到 CUDA，使用 CPU 设备")

        # 模型目录 - 固定位置
        root = Path(__file__).parent
        self.model_dir = root / "models" / "SenseVoiceSmall"
        logger.info(f"模型目录: {self.model_dir}")
        
        # 确保模型目录存在
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        # 下载模型文件
        logger.info("开始下载模型文件...")
        downloader = ModelDownloader()
        if not downloader.download_sense_voice_model():
            logger.error("模型文件下载失败")
            raise RuntimeError("模型文件下载失败")
        logger.info("模型文件下载完成")

        # 缓冲参数 - 固定配置
        self.sample_rate = 16000
        self.buffer_duration = 0.5  # 减小缓冲时长到0.5秒
        self._buffer = []  # list of numpy arrays
        self._buffer_samples = 0
        logger.info(f"音频缓冲配置 - 采样率: {self.sample_rate}, 缓冲时长: {self.buffer_duration}秒")

        # 初始化模型
        self.model = None
        self._init_model()

    def _init_model(self):
        """初始化模型"""
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

    def transcribe(self, audio_data, language="auto", use_itn=True):
        """转写音频数据"""
        logger.debug(f"收到音频数据: {audio_data.shape}")
        
        # 获取 numpy waveform
        if isinstance(audio_data, torch.Tensor):
            arr = audio_data.cpu().numpy()
        elif isinstance(audio_data, np.ndarray):
            arr = audio_data
        else:
            logger.error(f"不支持的类型: {type(audio_data)}")
            return {"error": f"不支持类型: {type(audio_data)}"}

        # 归一化
        if arr.dtype != np.float32:
            arr = arr.astype(np.float32) / 32767
        # 多维处理
        if arr.ndim == 2:
            arr = arr.mean(axis=1)

        # 直接处理当前音频数据
        tensor = torch.from_numpy(arr).float().to(self.device)
        try:
            logger.debug("开始模型推理...")
            res = self.model.generate(
                input=tensor,
                cache={},
                language=language,
                use_itn=use_itn,
                merge_vad=False,
                merge_length_s=self.buffer_duration
            )
            text = rich_transcription_postprocess(res[0]["text"])
            logger.info(f"识别结果: {text}")
            return {"text": text, "emotion": res[0].get("emotion", "NEUTRAL"), "event": res[0].get("event", "Speech")}
        except Exception as e:
            logger.error(f"推理错误: {e}")
            return {"error": str(e)}
