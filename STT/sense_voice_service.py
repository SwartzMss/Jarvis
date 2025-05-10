from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess
from pathlib import Path
import torch
import numpy as np
from logger_config import logger
from model_downloader import ModelDownloader
from config import ASR_CONFIG

class SenseVoiceService:
    def __init__(self, model_path=None, sample_rate=None, language=None):
        """Initialize speech recognition service with automatic device, model directory and buffer configuration"""
        logger.info("Initializing SenseVoice service...")
        
        # Device detection - prioritize CUDA
        if torch.cuda.is_available():
            self.device = "cuda"
            logger.info("Using CUDA device")
        else:
            self.device = "cpu"
            logger.warning("CUDA not detected, using CPU device")

        # Model directory - fixed location
        root = Path(__file__).parent
        self.model_dir = Path(model_path or ASR_CONFIG["model_path"])
        logger.info(f"Model directory: {self.model_dir}")
        
        # Ensure model directory exists
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        # Download model files
        logger.info("Starting model file download...")
        downloader = ModelDownloader()
        if not downloader.download_sense_voice_model():
            logger.error("Model file download failed")
            raise RuntimeError("Model file download failed")
        logger.info("Model file download completed")

        # Buffer parameters - fixed configuration
        self.sample_rate = sample_rate or ASR_CONFIG["sample_rate"]
        self.language = language or ASR_CONFIG["language"]
        self.buffer_duration = 0.5  # Reduce buffer duration to 0.5 seconds
        self._buffer = []  # list of numpy arrays
        self._buffer_samples = 0
        logger.info(f"Audio buffer configuration - Sample rate: {self.sample_rate}, Buffer duration: {self.buffer_duration} seconds")

        # Initialize model
        self.model = None
        self._init_model()

    def _init_model(self):
        """Initialize model"""
        logger.info("Starting model initialization...")
        try:
            self.model = AutoModel(
                model=str(self.model_dir),
                device=self.device,
                disable_update=True
            )
            logger.info("Model initialized successfully")
        except Exception as e:
            logger.error(f"Model initialization failed: {e}")
            raise

    def recognize(self, audio_data):
        """Recognize speech from audio data"""
        try:
            result = self.transcribe(audio_data, language=self.language)
            if "error" in result:
                logger.error(f"Recognition error: {result['error']}")
                return None
            return result["text"]
        except Exception as e:
            logger.error(f"Recognition error: {str(e)}")
            return None

    def transcribe(self, audio_data, language=None, use_itn=True):
        """Transcribe audio data"""
        logger.debug(f"Received audio data: {audio_data.shape}")
        
        # Get numpy waveform
        if isinstance(audio_data, torch.Tensor):
            arr = audio_data.cpu().numpy()
        elif isinstance(audio_data, np.ndarray):
            arr = audio_data
        else:
            logger.error(f"Unsupported type: {type(audio_data)}")
            return {"error": f"Unsupported type: {type(audio_data)}"}

        # Normalize
        if arr.dtype != np.float32:
            arr = arr.astype(np.float32) / 32767
        # Multi-dimensional processing
        if arr.ndim == 2:
            arr = arr.mean(axis=1)

        # Process current audio data directly
        tensor = torch.from_numpy(arr).float().to(self.device)
        try:
            logger.debug("Starting model inference...")
            res = self.model.generate(
                input=tensor,
                cache={},
                language=language or self.language,
                use_itn=use_itn,
                merge_vad=False,
                merge_length_s=self.buffer_duration
            )
            text = rich_transcription_postprocess(res[0]["text"])
            return {"text": text, "emotion": res[0].get("emotion", "NEUTRAL"), "event": res[0].get("event", "Speech")}
        except Exception as e:
            logger.error(f"Inference error: {e}")
            return {"error": str(e)}

    def close(self):
        """Release resources"""
        try:
            if hasattr(self, 'model'):
                del self.model
            logger.info("SenseVoice service resources released")
        except Exception as e:
            logger.error(f"Error releasing resources: {str(e)}")