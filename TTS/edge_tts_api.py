# file: edge_tts_api.py
import asyncio
import edge_tts
import miniaudio
import simpleaudio as sa
import aiohttp
from logger_config import logger


class EdgeTTSApi:
    def __init__(
        self,
        *,
        voice="zh-CN-XiaoxiaoNeural",
        rate="+0%",
        volume="+0%",
        max_retries=3,
    ):
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.max_retries = max_retries

    async def _create_communicate(self, text: str) -> edge_tts.Communicate:
        """创建 Communicate 实例，处理令牌过期问题"""
        try:
            return edge_tts.Communicate(
                text=text,
                voice=self.voice,
                rate=self.rate,
                volume=self.volume,
            )
        except Exception as e:
            logger.error(f"创建 Communicate 实例失败: {str(e)}")
            raise

    async def play_text(self, text: str) -> bool:
        """播放文本，包含重试机制"""
        for attempt in range(self.max_retries):
            try:
                comm = await self._create_communicate(text)
                mp3_buf = bytearray()

                async for item in comm.stream():
                    if isinstance(item, (bytes, bytearray)):
                        mp3_buf.extend(item)
                    elif isinstance(item, dict) and item.get("type") == "audio":
                        mp3_buf.extend(item["data"])

                if not mp3_buf:
                    logger.error("EdgeTTS play error: empty audio")
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

            except aiohttp.ClientError as e:
                if "403" in str(e) and attempt < self.max_retries - 1:
                    logger.warning(f"Edge TTS 访问令牌可能过期，正在重试 ({attempt + 1}/{self.max_retries})")
                    await asyncio.sleep(1)  # 等待一秒后重试
                    continue
                logger.error(f"Edge TTS 请求失败: {str(e)}")
                return False
            except Exception as e:
                logger.error(f"Edge TTS 播放出错: {str(e)}")
                return False
            finally:
                # 兼容不同版本的 session 字段
                sess = getattr(comm, "session", None) or getattr(comm, "_session", None)
                if sess and not sess.closed:
                    await sess.close()

        return False

    # ---------- 同步包装 ----------
    def sync_play_text(self, text: str) -> bool:
        return asyncio.run(self.play_text(text))

