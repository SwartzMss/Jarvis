import logging
import sys

# 创建logger实例
logger = logging.getLogger("TTS_Service")
logger.setLevel(logging.INFO)

# 创建控制台处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)

# 创建格式化器
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 设置格式化器
console_handler.setFormatter(formatter)

# 添加处理器到logger
logger.addHandler(console_handler) 