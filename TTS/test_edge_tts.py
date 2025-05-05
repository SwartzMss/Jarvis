import asyncio
from edge_tts_api import EdgeTTSApi

if __name__ == "__main__":
    tts = EdgeTTSApi()
    text = "你好,你是狗子吗"
    # 同步调用
    ok = tts.sync_play_text(text)
    print("同步播放：", ok)
