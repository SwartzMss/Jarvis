import asyncio
from edge_tts_api import EdgeTTSApi

if __name__ == "__main__":
    tts = EdgeTTSApi()
    text = "你好,你是狗子吗"
    # 同步调用
    ok = tts.sync_play_text(text)
    print("同步播放：", ok)

    # 异步调用
    #async def main():
    #    ok2 = await tts.play_text("这是一段异步播放的测试语音。")
    #    print("异步播放：", ok2)

    #asyncio.run(main())