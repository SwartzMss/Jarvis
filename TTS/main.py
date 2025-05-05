from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from edge_tts_api import EdgeTTSApi
import uvicorn

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
        # 更新 TTS 配置
        tts_api.voice = request.voice
        tts_api.rate = request.rate
        tts_api.volume = request.volume
        
        # 播放文本
        success = await tts_api.play_text(request.text)
        if not success:
            raise HTTPException(status_code=500, detail="TTS playback failed")
        
        return {"status": "success", "message": "Text played successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tts/voices")
async def get_available_voices():
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
    uvicorn.run(app, host="127.0.0.1", port=8001) 