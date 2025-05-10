from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio
import logging
from edge_tts_api import EdgeTTSApi
from audio_output import AudioOutput

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('tts_server.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="TTS API", description="文本转语音服务 API")

# 初始化 TTS API 和音频输出
logger.info("正在初始化 TTS 服务...")
tts_api = EdgeTTSApi()
audio_out = AudioOutput(blocksize=1024)
audio_out.start()
logger.info("TTS 服务初始化完成")

class TTSRequest(BaseModel):
    text: str
    voice: str = "zh-CN-XiaoxiaoNeural"
    rate: str = "+0%"
    volume: str = "+0%"

@app.post("/tts")
async def text_to_speech(request: TTSRequest):
    """
    将文本转换为语音并直接播放
    
    - **text**: 要转换的文本
    - **voice**: 语音角色（可选，默认为 zh-CN-XiaoxiaoNeural）
    - **rate**: 语速（可选，默认为 +0%）
    - **volume**: 音量（可选，默认为 +0%）
    """
    try:
        logger.info(f"收到 TTS 请求: text='{request.text[:50]}...', voice={request.voice}, rate={request.rate}, volume={request.volume}")
        
        # 设置 TTS 参数
        tts_api.voice = request.voice
        tts_api.rate = request.rate
        tts_api.volume = request.volume
        
        # 转换文本为音频
        logger.info("开始转换文本为音频...")
        audio_data, sample_rate = await tts_api.text_to_audio(request.text)
        
        if audio_data is None or sample_rate is None:
            logger.error("语音合成失败")
            raise HTTPException(status_code=500, detail="语音合成失败")
            
        # 直接播放音频
        logger.info(f"开始播放音频: 采样率={sample_rate}Hz, 数据大小={len(audio_data)}")
        audio_out.play_audio(audio_data, sample_rate)
        
        logger.info("音频播放已开始")
        return {"status": "success", "message": "音频播放已开始"}
        
    except Exception as e:
        logger.error(f"处理请求时发生错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    """API 根路径，返回服务信息"""
    logger.info("收到根路径请求")
    return {
        "service": "TTS API",
        "version": "1.0.0",
        "endpoints": {
            "/tts": "POST - 文本转语音并播放",
            "/": "GET - API 信息"
        }
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("正在启动 TTS 服务器...")
    uvicorn.run(app, host="127.0.0.1", port=8001) 