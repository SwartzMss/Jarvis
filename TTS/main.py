from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from edge_tts_api import EdgeTTSApi
import uvicorn
from logger_config import logger

app = FastAPI(title="TTS Service API")
tts_api = EdgeTTSApi()

class TTSRequest(BaseModel):
    text: str
    voice: str = "zh-CN-XiaoxiaoNeural"
    rate: str = "+0%"
    volume: str = "+0%"

@app.post("/tts/play")
async def play_text(request: TTSRequest):
    try:
        logger.info(f"收到TTS请求: 文本='{request.text}', 语音='{request.voice}'")
        
        # 更新 TTS 配置
        tts_api.voice = request.voice
        tts_api.rate = request.rate
        tts_api.volume = request.volume
        
        # 播放文本
        logger.info("开始播放TTS...")
        success = await tts_api.play_text(request.text)
        if not success:
            logger.error("TTS播放失败")
            raise HTTPException(status_code=500, detail="TTS playback failed")
        
        logger.info("TTS播放成功")
        return {"status": "success", "message": "Text played successfully"}
    except Exception as e:
        logger.error(f"TTS服务出错: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tts/voices")
async def get_available_voices():
    logger.info("获取可用语音列表")
    # 这里可以返回支持的语音列表
    return {
        "voices": [
            "zh-CN-XiaoxiaoNeural",
            "zh-CN-YunxiNeural",
            "zh-CN-YunyangNeural",
            "zh-CN-XiaochenNeural",
            "zh-CN-XiaohanNeural",
            "zh-CN-XiaomengNeural",
            "zh-CN-XiaomoNeural",
            "zh-CN-XiaoqiuNeural",
            "zh-CN-XiaoruiNeural",
            "zh-CN-XiaoshuangNeural",
            "zh-CN-XiaoxuanNeural",
            "zh-CN-XiaoyanNeural",
            "zh-CN-XiaoyiNeural",
            "zh-CN-XiaozhenNeural"
        ]
    }

if __name__ == "__main__":
    logger.info("启动TTS服务...")
    uvicorn.run(app, host="127.0.0.1", port=8001) 