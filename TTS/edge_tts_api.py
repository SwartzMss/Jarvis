# file: edge_tts_api.py
import asyncio
import edge_tts
import miniaudio
import simpleaudio as sa


class EdgeTTSApi:
    def __init__(
        self,
        *,
        voice="zh-CN-XiaoxiaoNeural",
        rate="+0%",
        volume="+0%",
    ):
        self.voice = voice
        self.rate = rate
        self.volume = volume

    # ---------- 核心：异步播放 ----------
    async def play_text(self, text: str) -> bool:
        comm = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
            volume=self.volume,
        )
        mp3_buf = bytearray()

        try:
            async for item in comm.stream():
                # 新版只 yield bytes；旧版 yield dict
                if isinstance(item, (bytes, bytearray)):
                    mp3_buf.extend(item)
                elif isinstance(item, dict) and item.get("type") == "audio":
                    mp3_buf.extend(item["data"])
        finally:
            # 兼容不同版本的 session 字段
            sess = getattr(comm, "session", None) or getattr(comm, "_session", None)
            if sess and not sess.closed:
                await sess.close()

        if not mp3_buf:
            print("❌ EdgeTTS play error: empty audio")
            return False

        # 2) MP3 → PCM (16‑bit signed)
        snd = miniaudio.decode(
            bytes(mp3_buf),
            output_format=miniaudio.SampleFormat.SIGNED16,
        )
        pcm_bytes = snd.samples.tobytes()

        # 3) simpleaudio 播放
        wave = sa.WaveObject(
            pcm_bytes,
            num_channels=snd.nchannels,
            bytes_per_sample=2,
            sample_rate=snd.sample_rate,
        )
        play_obj = wave.play()
        await asyncio.get_running_loop().run_in_executor(None, play_obj.wait_done)
        return True

    # ---------- 同步包装 ----------
    def sync_play_text(self, text: str) -> bool:
        return asyncio.run(self.play_text(text))

