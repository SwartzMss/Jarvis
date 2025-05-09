import os
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

# Picovoice配置
PICOVOICE_ACCESS_KEY = os.getenv('PICOVOICE_ACCESS_KEY')
WAKE_WORD = "jarvis"

# 音频配置
SAMPLERATE = int(os.getenv('SAMPLERATE', '16000'))
BLOCKSIZE = int(os.getenv('BLOCKSIZE', '1024')) 