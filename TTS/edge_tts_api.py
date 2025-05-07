import asyncio
import edge_tts
import miniaudio
import numpy as np
import aiohttp
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class EdgeTTSApi:
    def __init__(
        self,
        *,
        voice="zh-CN-XiaoxiaoNeural",
        rate="+0%",
        volume="+0%",
        max_retries=3,
        retry_delay=1.0,
    ):
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        logger.info(f"初始化 EdgeTTS API: voice={voice}, rate={rate}, volume={volume}, max_retries={max_retries}")

    async def _create_communicate(self, text: str) -> edge_tts.Communicate:
        """创建 Communicate 实例，处理令牌过期问题"""
        try:
            logger.debug(f"创建 Communicate 实例: text={text[:50]}...")
            return edge_tts.Communicate(
                text=text,
                voice=self.voice,
                rate=self.rate,
                volume=self.volume,
            )
        except Exception as e:
            logger.error(f"创建 Communicate 实例失败: {str(e)}")
            raise

    async def text_to_audio(self, text: str) -> Tuple[Optional[np.ndarray], Optional[int]]:
        """将文本转换为音频数据
        
        Args:
            text: 要转换的文本
            
        Returns:
            tuple: (音频数据(numpy.ndarray), 采样率(int))
        """
        logger.info(f"开始转换文本: {text[:50]}...")
        
        for attempt in range(self.max_retries):
            try:
                comm = await self._create_communicate(text)
                mp3_buf = bytearray()
                chunk_count = 0

                async for item in comm.stream():
                    if isinstance(item, (bytes, bytearray)):
                        mp3_buf.extend(item)
                        chunk_count += 1
                    elif isinstance(item, dict) and item.get("type") == "audio":
                        mp3_buf.extend(item["data"])
                        chunk_count += 1

                logger.info(f"收到 {chunk_count} 个音频块，总大小: {len(mp3_buf)} 字节")

                if not mp3_buf:
                    logger.error("EdgeTTS error: empty audio")
                    if attempt < self.max_retries - 1:
                        logger.info(f"重试中 ({attempt + 1}/{self.max_retries})...")
                        await asyncio.sleep(self.retry_delay)
                        continue
                    return None, None

                # MP3 → PCM (16‑bit signed)
                logger.debug("开始解码 MP3 数据")
                snd = miniaudio.decode(
                    bytes(mp3_buf),
                    output_format=miniaudio.SampleFormat.SIGNED16,
                )
                logger.info(f"解码完成: 采样率={snd.sample_rate}Hz, 声道数={snd.nchannels}, 总帧数={len(snd.samples)}")
                
                # 转换为numpy数组并保持声道信息
                audio_data = np.frombuffer(snd.samples, dtype=np.int16)
                # 重塑为 (frames, channels) 格式
                audio_data = audio_data.reshape(-1, snd.nchannels)
                logger.debug(f"音频数据统计: shape={audio_data.shape}, min={np.min(audio_data)}, max={np.max(audio_data)}, mean={np.mean(audio_data):.2f}")
                
                # 检查数据范围
                if np.max(np.abs(audio_data)) > 32767:
                    logger.warning(f"音频数据超出范围: max={np.max(np.abs(audio_data))}, 进行归一化")
                    audio_data = np.clip(audio_data, -32768, 32767)
                
                # 确保数据是连续的
                audio_data = np.ascontiguousarray(audio_data)
                
                # 检查数据有效性
                if np.isnan(audio_data).any():
                    logger.error("音频数据包含 NaN 值")
                    if attempt < self.max_retries - 1:
                        logger.info(f"重试中 ({attempt + 1}/{self.max_retries})...")
                        await asyncio.sleep(self.retry_delay)
                        continue
                    return None, None
                if np.isinf(audio_data).any():
                    logger.error("音频数据包含 Inf 值")
                    if attempt < self.max_retries - 1:
                        logger.info(f"重试中 ({attempt + 1}/{self.max_retries})...")
                        await asyncio.sleep(self.retry_delay)
                        continue
                    return None, None
                
                logger.info("音频数据转换完成")
                return audio_data, snd.sample_rate

            except aiohttp.ClientError as e:
                if attempt < self.max_retries - 1:
                    logger.warning(f"Edge TTS 请求失败: {str(e)}, 重试中 ({attempt + 1}/{self.max_retries})...")
                    await asyncio.sleep(self.retry_delay)
                    continue
                logger.error(f"Edge TTS 请求失败: {str(e)}")
                return None, None
            except Exception as e:
                if attempt < self.max_retries - 1:
                    logger.warning(f"Edge TTS 转换出错: {str(e)}, 重试中 ({attempt + 1}/{self.max_retries})...")
                    await asyncio.sleep(self.retry_delay)
                    continue
                logger.error(f"Edge TTS 转换出错: {str(e)}")
                return None, None
            finally:
                # 兼容不同版本的 session 字段
                sess = getattr(comm, "session", None) or getattr(comm, "_session", None)
                if sess and not sess.closed:
                    await sess.close()

        return None, None

    def sync_text_to_audio(self, text: str) -> Tuple[Optional[np.ndarray], Optional[int]]:
        """同步版本的文本转音频"""
        return asyncio.run(self.text_to_audio(text)) 