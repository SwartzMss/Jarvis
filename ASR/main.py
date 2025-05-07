import os
import signal
import sys
import threading
import time
from audio_input import AudioInput

def signal_handler(signum, frame):
    """信号处理函数"""
    print("\n正在停止程序...")
    if audio_input:
        audio_input.stop()
    sys.exit(0)

def main():
    """主函数"""
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 初始化音频输入（默认会尝试使用VB-Audio Virtual Cable）
    global audio_input
    audio_input = AudioInput(
        samplerate=16000,
        blocksize=1024
    )
    
    try:
        # 启动音频处理
        audio_input.start()
        print("正在监听唤醒词，按 Ctrl+C 停止")
        
        # 保持程序运行
        while True:
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n正在停止程序...")
    finally:
        if audio_input:
            audio_input.stop()

if __name__ == "__main__":
    main() 