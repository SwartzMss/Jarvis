import asyncio
import signal
import sys

from edge_tts_api import EdgeTTSApi
from audio_output import AudioOutput

# 信号处理：优雅退出
def signal_handler(signum, frame):
    print("\n正在停止程序…")
    if hasattr(signal_handler, 'audio_out'):
        signal_handler.audio_out.stop()
    sys.exit(0)

async def main():
    # 初始化 TTS API 和自适应播放器
    tts_api = EdgeTTSApi()
    audio_out = AudioOutput(blocksize=1024)  # 自动检测设备采样率
    audio_out.start()
    signal_handler.audio_out = audio_out

    # 注册中断信号
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("TTS 系统已启动，输入文字（q 退出）：")

    while True:
        try:
            text = input().strip()
        except EOFError:
            break
        except Exception as e:
            print("输入错误：", e)
            break

        if text.lower() == 'q':
            break
            
        # 处理空输入
        if not text:
            continue

        # 合成并播放
        audio_data, sr = await tts_api.text_to_audio(text)
        if audio_data is not None:
            audio_out.play_audio(audio_data, sr)
            print("播放完成")
        else:
            print("语音合成失败")

    # 结束时关闭播放流
    audio_out.stop()
    print("程序已退出")

if __name__ == '__main__':
    asyncio.run(main())
