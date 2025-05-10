import os
from dotenv import load_dotenv
from pathlib import Path
# 加载.env文件
load_dotenv()

# 项目根目录
ROOT_DIR = Path(__file__).parent

# Picovoice配置
PICOVOICE_ACCESS_KEY = os.getenv('PICOVOICE_ACCESS_KEY')
WAKE_WORD = "jarvis"

# 音频配置
SAMPLERATE = int(os.getenv('SAMPLERATE', '16000'))
BLOCKSIZE = int(os.getenv('BLOCKSIZE', '1024')) 


# 日志配置
LOG_LEVEL = "INFO"  # 日志级别
LOG_FILE = ROOT_DIR / "logs" / "STT.log"  # 日志文件路径


# sensevoice配置
SAMPLE_RATE = 16000  # 采样率
CHANNELS = 1  # 声道数
CHUNK_SIZE = 1024  # 每次读取的音频块大小

# VAD配置
VAD_CONFIG = {
    "aggressiveness": 1,  # VAD灵敏度，范围0-3，0最不敏感
    "frame_duration": 30,  # VAD帧长度（毫秒）
    "buffer_duration": 0.5,  # VAD缓冲区时长（秒）
}

# 中文语音特征检测配置
SPEECH_CONFIG = {
    "min_volume": 0.02,  # 最小音量阈值
    "max_volume": 0.5,   # 最大音量阈值
    "min_freq": 100,     # 最小频率阈值（Hz）
    "max_freq": 1000,    # 最大频率阈值（Hz）
    "max_silence_frames": 10,  # 最大允许的连续静音帧数
    "min_speech_frames": 3,    # 最小需要的连续语音帧数
}

# sensevoice配置
ASR_CONFIG = {
    "model_path": str(ROOT_DIR / "models" / "SenseVoiceSmall"),
    "sample_rate": 16000,
    "language": "auto",  # 自动检测语言
} 