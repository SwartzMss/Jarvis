import numpy as np
from queue import Queue, Empty
import threading
import asyncio
from logger_config import logger
from config import SAMPLE_RATE, CHANNELS, CHUNK_SIZE, ASR_CONFIG
from sense_voice_service import SenseVoiceService
from agent_client import AgentClient
import time

class SpeechRecognizer:
    def __init__(self):
        """
        初始化语音识别器
        """
        self.is_running = False
        self.is_active = False
        self.audio_buffer = []
        self.sentence_buffer = ""  # 句子缓冲区
        self.silence_frames = 0
        self.max_silence_frames = 20  # 约1秒的静音 (20帧 * 0.05秒/帧 = 1秒)
        self.min_audio_frames = 10    # 最小音频帧数 (约0.5秒)
        self.silence_threshold = 0.05 # 静音阈值 (提高阈值，减少环境噪音影响)
        self.max_buffer_size = 40     # 最大缓冲区大小，约2秒的音频 (40帧 * 0.05秒/帧 = 2秒)
        self.min_amplitude_threshold = 200  # 最小有效音频幅度阈值
        
        # 初始化Agent客户端
        self.agent_client = AgentClient()
        
        # 定时器相关参数
        self.last_audio_time = 0  # 上次收到音频数据的时间
        self.silence_timeout = 1.0  # 静音超时时间（秒）
        self.has_valid_audio = False  # 是否有有效音频
        self.has_valid_text = False  # 是否有有效文字
        
        # 初始化语音识别服务
        logger.info("初始化语音识别服务...")
        self.asr_service = SenseVoiceService(
            model_path=ASR_CONFIG["model_path"],
            sample_rate=ASR_CONFIG["sample_rate"],
            language=ASR_CONFIG["language"]
        )
        logger.info("语音识别服务初始化完成")
        
    def activate(self):
        """激活语音识别"""
        logger.info("激活语音识别")
        self.is_active = True
        self.audio_buffer = []
        self.silence_frames = 0
        
    def deactivate(self):
        """停用语音识别"""
        logger.info("停用语音识别")
        self.is_active = False
        self.audio_buffer = []
        self.silence_frames = 0
        
    def is_silence(self, audio_data: np.ndarray) -> bool:
        """
        检查音频数据是否为静音
        
        Args:
            audio_data: 音频数据
            
        Returns:
            bool: 是否为静音
        """
        return np.abs(audio_data).mean() < self.silence_threshold
        
    def is_valid_audio(self, audio_data: np.ndarray) -> bool:
        """
        检查音频数据是否有效
        
        Args:
            audio_data: 音频数据
            
        Returns:
            bool: 是否为有效音频
        """
        # 计算音频数据的统计特征
        max_amplitude = np.max(np.abs(audio_data))
        mean_amplitude = np.mean(np.abs(audio_data))
        
        # 检查音频是否有效
        is_valid = (max_amplitude > self.min_amplitude_threshold and 
                   mean_amplitude > self.silence_threshold)
        
        if not is_valid:
            logger.debug(f"音频数据无效 - 最大幅度: {max_amplitude:.2f}, 平均幅度: {mean_amplitude:.2f}")
            
        return is_valid
        
    async def process_audio(self, audio_queue: Queue):
        """处理音频数据"""
        try:
            while self.is_running:
                if not self.is_active:
                    await asyncio.sleep(0.1)
                    continue
                    
                try:
                    # 获取音频数据
                    audio_data = audio_queue.get(timeout=0.1)
                    logger.info(f"处理音频数据: {audio_data}")
                    if audio_data is None:
                        break
                    logger.info(f"处理音频数据: {audio_data}")
                    # 检查是否为静音
                    if self.is_silence(audio_data):
                        self.silence_frames += 1
                        if self.silence_frames >= self.max_silence_frames and len(self.audio_buffer) >= self.min_audio_frames:
                            # 处理累积的音频数据
                            audio_segment = np.concatenate(self.audio_buffer)
                            text = self.asr_service.recognize(audio_segment)
                            if text:
                                logger.info(f"识别结果: {text}")
                            # 重置缓冲区
                            self.audio_buffer = []
                            self.silence_frames = 0
                            # 停用语音识别
                            self.deactivate()
                    else:
                        self.silence_frames = 0
                        self.audio_buffer.append(audio_data)
                        
                except Empty:
                    continue
                except Exception as e:
                    logger.error(f"处理音频数据时出错: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"语音识别处理循环错误: {str(e)}")
        finally:
            self.deactivate()
            
    async def start(self, audio_queue: Queue):
        """启动语音识别处理循环"""
        try:
            logger.info("开始启动语音识别处理循环...")
            self.is_running = True
            self.audio_buffer = []
            self.is_active = True  # 默认激活ASR
            self.last_audio_time = time.time()  # 初始化时间戳
            
            logger.info("开始监听音频队列...")
            while self.is_running:
                try:
                    # 检查队列是否为空
                    if audio_queue.empty():
                        # 检查是否超过静音超时
                        current_time = time.time()
                        if self.has_valid_audio and (current_time - self.last_audio_time) > self.silence_timeout:
                            logger.info(f"检测到静音超时: {current_time - self.last_audio_time:.1f}秒")
                            # 如果还有未处理的音频数据，先处理完
                            if len(self.audio_buffer) >= self.min_audio_frames:
                                await self._process_audio()
                            # 如果句子缓冲区有内容，输出句子
                            if self.sentence_buffer.strip():
                                sentence = self.sentence_buffer.strip()
                                logger.info(f"输出句子: {sentence}")
                                # 发送到Agent
                                await self.agent_client.send_message(sentence)
                                self.sentence_buffer = ""
                                self.has_valid_text = False
                            self.has_valid_audio = False
                        await asyncio.sleep(0.1)
                        continue
                        
                    audio_data = audio_queue.get(timeout=0.1)
                    
                    if audio_data is None:
                        logger.info("收到结束信号，退出处理循环")
                        break
                    
                    # 检查音频数据是否有效
                    if not self.is_valid_audio(audio_data):
                        continue
                        
                    # 更新最后音频时间和标志
                    self.last_audio_time = time.time()
                    self.has_valid_audio = True
                    
                    # 检查是否激活
                    if not self.is_active:
                        continue
                        
                    # 添加到缓冲区
                    self.audio_buffer.append(audio_data)
                    
                    # 检查缓冲区大小
                    if len(self.audio_buffer) >= self.max_buffer_size:
                        await self._process_audio()
                        
                except Empty:
                    continue
                except Exception as e:
                    logger.error(f"处理音频数据时出错: {str(e)}", exc_info=True)
                    continue
                    
            logger.info("语音识别处理循环已结束")
            
        except Exception as e:
            logger.error(f"语音识别处理循环出错: {str(e)}", exc_info=True)
        finally:
            self.is_running = False
            logger.info("语音识别处理循环已完全停止")

    def stop(self):
        """停止语音识别"""
        if not self.is_running:
            return
            
        logger.info("停止语音识别...")
        self.is_running = False
        self.deactivate()
        
        # 如果句子缓冲区还有内容，输出最后的句子
        if self.sentence_buffer.strip():
            sentence = self.sentence_buffer.strip()
            logger.info(f"输出最后的句子: {sentence}")
            self.sentence_buffer = ""
            
        # 释放语音识别服务资源
        try:
            self.asr_service.close()
            logger.info("语音识别服务已关闭")
        except Exception as e:
            logger.error(f"关闭语音识别服务失败: {str(e)}")

    def close(self):
        """
        释放资源
        """
        try:
            if self.is_running:
                self.stop()
            # 关闭Agent客户端
            asyncio.create_task(self.agent_client.close())
            logger.info("语音识别器资源已释放")
        except Exception as e:
            logger.error(f"释放资源时出错: {str(e)}", exc_info=True)

    def is_valid_text(self, text: str) -> bool:
        """
        检查文本是否有效（只包含文字、数字和基本标点）
        
        Args:
            text: 待检查的文本
            
        Returns:
            bool: 是否为有效文本
        """
        if not text or not text.strip():
            return False
            
        # 移除空白字符
        text = text.strip()
        
        # 检查是否只包含有效字符
        valid_chars = set('，。！？、；：""''（）【】《》…—')
        for char in text:
            # 检查是否为中文、英文、数字或基本标点
            if not (('\u4e00' <= char <= '\u9fff') or  # 中文
                   ('a' <= char.lower() <= 'z') or     # 英文
                   ('0' <= char <= '9') or             # 数字
                   (char in valid_chars)):             # 基本标点
                logger.debug(f"文本包含无效字符: {char}")
                return False
                
        return True
        
    def is_sentence_end(self, text: str) -> bool:
        """
        检查文本是否以句子结束标点结尾
        
        Args:
            text: 待检查的文本
            
        Returns:
            bool: 是否为句子结束
        """
        if not text:
            return False
            
        # 检查是否以句子结束标点结尾
        end_punctuations = {'。', '？', '！', '.', '?', '!'}
        return text[-1] in end_punctuations
        
    def is_empty_chunk(self, text: str) -> bool:
        """
        检查文本片段是否为空或只包含标点
        
        Args:
            text: 待检查的文本
            
        Returns:
            bool: 是否为空片段
        """
        if not text or not text.strip():
            return True
            
        # 移除空白字符
        text = text.strip()
        
        # 检查是否只包含标点
        punctuation_only = True
        for char in text:
            if not (char in '，。！？、；：""''（）【】《》…—,.!?;:"\'()[]<>-'):
                punctuation_only = False
                break
                
        return punctuation_only
        
    def should_output_sentence(self, chunk: str, current_time: float) -> bool:
        """
        检查是否应该输出当前句子
        
        Args:
            chunk: 最新的文本片段
            current_time: 当前时间
            
        Returns:
            bool: 是否应该输出句子
        """
        # 1. 标点触发：检查是否以句子结束标点结尾
        if self.is_sentence_end(chunk):
            logger.debug("检测到句子结束标点")
            return True
            
        # 2. 时长触发：检查是否超过静音超时时间
        if current_time - self.last_audio_time > self.silence_timeout:
            logger.debug(f"超过静音超时时间: {current_time - self.last_audio_time:.1f}秒")
            return True
            
        return False
        
    def process_text_chunk(self, chunk: str, current_time: float) -> str:
        """
        处理文本片段，累积到句子缓冲区
        
        Args:
            chunk: 新的文本片段
            current_time: 当前时间
            
        Returns:
            str: 如果形成完整句子则返回，否则返回空字符串
        """
        # 检查是否为空片段
        if self.is_empty_chunk(chunk):
            # 如果已经累积了有效音频，检查是否超过静音超时
            if self.has_valid_audio and (current_time - self.last_audio_time) > self.silence_timeout:
                # 输出当前缓冲区内容
                if self.sentence_buffer.strip():
                    sentence = self.sentence_buffer.strip()
                    self.sentence_buffer = ""
                    self.has_valid_audio = False
                    logger.info(f"检测到静音超时，输出句子: {sentence}")
                    return sentence
            return ""
            
        # 更新最后有效文本时间
        self.last_audio_time = current_time
        self.has_valid_text = True
        
        # 清理文本片段
        chunk = chunk.strip()
        
        # 检查文本是否有效
        if not self.is_valid_text(chunk):
            return ""
            
        # 拼接到句子缓冲区
        if self.sentence_buffer:
            self.sentence_buffer += " " + chunk
        else:
            self.sentence_buffer = chunk
            
        logger.debug(f"当前句子缓冲区: {self.sentence_buffer}")
        return ""
        
    async def _process_audio(self):
        """处理累积的音频数据"""
        try:
            if len(self.audio_buffer) < self.min_audio_frames:
                logger.debug(f"音频数据不足，跳过处理 (当前: {len(self.audio_buffer)}, 最小: {self.min_audio_frames})")
                self.audio_buffer = []
                return
                
            # 检查累积的音频是否有效
            audio_segment = np.concatenate(self.audio_buffer)
            if not self.is_valid_audio(audio_segment):
                logger.debug("累积的音频数据无效，跳过处理")
                self.audio_buffer = []
                return
                
            logger.info(f"开始处理累积的音频数据，缓冲区大小: {len(self.audio_buffer)}")
            text = self.asr_service.recognize(audio_segment)
            
            # 处理识别结果
            if text and self.is_valid_text(text):
                logger.info(f"识别到有效文本: {text}")
                # 拼接到句子缓冲区
                if self.sentence_buffer:
                    self.sentence_buffer += " " + text
                else:
                    self.sentence_buffer = text
                    
                # 更新有效文本标志
                self.has_valid_text = True
            else:
                logger.debug("未能识别出有效文本")
                
            # 重置音频缓冲区
            self.audio_buffer = []
            
        except Exception as e:
            logger.error(f"处理音频数据时出错: {str(e)}", exc_info=True)
            self.audio_buffer = []  # 发生错误时清空缓冲区 