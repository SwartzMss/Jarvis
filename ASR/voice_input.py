import sounddevice as sd
import numpy as np
import threading
import queue
import librosa
import webrtcvad
from logger_config import logger
from sense_voice_service import SenseVoiceService

class VoiceInput:
    """
    Voice input class supporting automatic resampling, multi-channel mixing or selection,
    configurable buffer length, and VAD detection.
    """
    def __init__(self):
        """
        Initialize voice input class with internal parameter settings
        """
        logger.info("Initializing VoiceInput...")
        
        # Auto-detect default device info
        dev_info = sd.query_devices(kind='input')
        self.input_rate = int(dev_info['default_samplerate'])
        self.channels = dev_info['max_input_channels']

        # Target format settings
        self.target_rate = 16000  # Model expected sample rate
        self.mix_channels = True  # Whether to mix multi-channel audio to mono
        self.lib_resample = True  # Whether to use librosa resampling
        self.chunk_duration = 0.1  # Processing duration 0.1 seconds
        self.chunk_frames = int(self.chunk_duration * self.target_rate)

        # VAD configuration
        self.vad_aggressiveness = 0  # Lower VAD sensitivity, range 0-3, 0 least sensitive
        self.vad_frame_duration = 30  # VAD frame length in milliseconds
        self.vad = webrtcvad.Vad(self.vad_aggressiveness)
        self.vad_frame_size = int(self.target_rate * self.vad_frame_duration / 1000)
        self.vad_buffer = np.zeros((0,), dtype=np.float32)  # Buffer for VAD detection
        self.vad_buffer_duration = 0.5  # Increase VAD buffer duration to 0.5 seconds
        self.vad_buffer_size = int(self.vad_buffer_duration * self.target_rate)
        
        # Chinese speech feature detection configuration
        self.min_volume = 0.02  # Minimum volume threshold
        self.max_volume = 0.5   # Maximum volume threshold
        self.min_freq = 100     # Minimum frequency threshold (Hz)
        self.max_freq = 1000    # Maximum frequency threshold (Hz)
        
        # Speech buffer configuration
        self.speech_buffer = np.zeros((0,), dtype=np.float32)  # For accumulating speech segments
        self.is_speaking = False  # Whether currently speaking
        self.silence_frames = 0  # Continuous silence frame count
        self.max_silence_frames = 10  # Increase maximum allowed continuous silence frames
        self.min_speech_frames = 3  # Minimum required continuous speech frames
        
        logger.debug(f"VAD configuration - Sensitivity: {self.vad_aggressiveness}, Frame size: {self.vad_frame_size}, Buffer size: {self.vad_buffer_size}")

        # Buffer and queue
        self.audio_queue = queue.Queue()  # For storing audio data to be processed
        self.transcribe_queue = queue.Queue()  # For storing audio data to be transcribed

        # Recording state
        self.recording = False

        # Initialize service
        try:
            self.svc = SenseVoiceService()
            logger.info("SenseVoice service initialized successfully")
        except Exception as e:
            logger.error(f"SenseVoice service initialization failed: {e}")
            self.svc = None
            
        # Text callback function
        self.on_text_received = None

    def _audio_callback(self, indata, frames, time, status):
        """Audio callback function"""
        if status:
            logger.warning(f"Recording status: {status}")
        # Put into thread-safe queue
        self.audio_queue.put(indata.copy())

    def start(self):
        """Start recording and processing threads"""
        if self.recording:
            logger.warning("Recording already in progress")
            return
            
        logger.info("Starting recording...")
        self.recording = True

        # Start recording thread
        self.record_thread = threading.Thread(target=self._record_loop, daemon=True)
        self.record_thread.start()
        
        # Start transcription thread
        self.transcribe_thread = threading.Thread(target=self._transcribe_loop, daemon=True)
        self.transcribe_thread.start()
        
        logger.info("Recording and transcription threads started")

    def _record_loop(self):
        """Recording thread main loop"""
        logger.info("Starting recording thread")
        try:
            # Calculate block size to ensure at least one VAD frame
            blocksize = int(self.target_rate * self.vad_frame_duration / 1000)  # 30ms samples
            logger.info(f"Setting audio block size: {blocksize} samples")
            
            with sd.InputStream(
                samplerate=self.input_rate,
                channels=self.channels,
                dtype='float32',
                blocksize=blocksize,
                callback=self._audio_callback,
            ):
                logger.info("Audio input stream opened")
                while self.recording:
                    try:
                        chunk = self.audio_queue.get(timeout=1)
                        self._process_chunk(chunk)
                    except queue.Empty:
                        continue
        except Exception as e:
            logger.error(f"Recording error: {e}")
            self.recording = False

    def _transcribe_loop(self):
        """Transcription thread main loop"""
        logger.info("Starting transcription thread")
        while self.recording:
            try:
                # Get audio data from transcription queue
                audio_data = self.transcribe_queue.get(timeout=0.5)
                if audio_data is None:
                    logger.info("No data in transcription queue")
                    continue

                logger.info("Starting transcription")   
                # Process audio data
                result = self.svc.transcribe(audio_data, language="auto")
                if result.get("error"):
                    logger.error(f"Transcription error: {result['error']}")
                elif result.get("text"):
                    # Call text callback function
                    if self.on_text_received is not None:
                        self.on_text_received(result["text"])
                    
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Transcription error: {e}")
                continue
                
        logger.info("Transcription thread stopped")

    def _check_chinese_speech(self, audio_data):
        """Check if audio matches Chinese speech characteristics"""
        # Calculate volume
        volume = np.max(np.abs(audio_data))
        if volume < self.min_volume or volume > self.max_volume:
            logger.debug(f"Volume {volume:.4f} out of range [{self.min_volume}, {self.max_volume}]")
            return False
            
        # Calculate spectrum
        n_fft = 2048
        hop_length = 512
        D = np.abs(librosa.stft(audio_data, n_fft=n_fft, hop_length=hop_length))
        freqs = librosa.fft_frequencies(sr=self.target_rate, n_fft=n_fft)
        
        # Calculate main frequency components
        power = np.sum(D, axis=1)
        main_freq = freqs[np.argmax(power)]
        
        if main_freq < self.min_freq or main_freq > self.max_freq:
            logger.debug(f"Main frequency {main_freq:.1f}Hz out of range [{self.min_freq}, {self.max_freq}]Hz")
            return False
            
        return True

    def _process_chunk(self, raw_chunk):
        """Process audio chunk"""        
        # Original float PCM [-1, 1]
        data = raw_chunk.astype(np.float32)

        # Process multi-channel -> mono
        if data.ndim == 2:
            if self.mix_channels:
                mono = data.mean(axis=1)
            else:
                mono = data[:, 0]
        else:
            mono = data.flatten()

        # Resample to target rate
        if self.input_rate != self.target_rate:
            resampled = librosa.resample(
                mono, orig_sr=self.input_rate, target_sr=self.target_rate
            )
        else:
            resampled = mono

        # Accumulate audio data to VAD buffer
        self.vad_buffer = np.concatenate([self.vad_buffer, resampled])
        if len(self.vad_buffer) > self.vad_buffer_size:
            self.vad_buffer = self.vad_buffer[-self.vad_buffer_size:]
            
            # Perform VAD detection
            is_speech = self._vad_detect(self.vad_buffer)
            logger.debug(f"VAD detection result: {is_speech}")
            
            if is_speech:
                # Check if matches Chinese speech characteristics
                if not self._check_chinese_speech(self.vad_buffer):
                    is_speech = False
                    logger.debug("Does not match Chinese speech characteristics")
            
            if is_speech:
                # Speech detected
                self.silence_frames = 0  # Reset silence count
                if not self.is_speaking:
                    # Transition from silence to speech, start new speech segment
                    self.is_speaking = True
                    self.speech_buffer = np.zeros((0,), dtype=np.float32)  # Clear previous buffer
                    logger.info("[MIC] Speech detected")
                
                # Accumulate audio data to speech buffer
                self.speech_buffer = np.concatenate([self.speech_buffer, resampled])
            else:
                # Silence detected
                if self.is_speaking:
                    self.silence_frames += 1
                    if self.silence_frames >= self.max_silence_frames:
                        # Continuous silence frames reached threshold, consider speech ended
                        self.is_speaking = False
                        logger.info("[SILENCE] Speech ended")
                        
                        # Put accumulated speech data into transcription queue
                        if len(self.speech_buffer) > 0:
                            self.transcribe_queue.put(self.speech_buffer)
                            self.speech_buffer = np.zeros((0,), dtype=np.float32)
                    else:
                        # Still in speech segment, continue accumulating audio data
                        self.speech_buffer = np.concatenate([self.speech_buffer, resampled])

    def _vad_detect(self, audio_data):
        """Use WebRTC VAD to detect speech activity"""
        # Convert float audio data to 16-bit integer
        audio_int16 = (audio_data * 32767).astype(np.int16)
        
        # Split audio data into VAD frames
        frames = []
        for i in range(0, len(audio_int16), self.vad_frame_size):
            frame = audio_int16[i:i + self.vad_frame_size]
            if len(frame) == self.vad_frame_size:
                frames.append(frame)
        
        # Detect each frame
        speech_frames = 0
        for frame in frames:
            if self.vad.is_speech(frame.tobytes(), self.target_rate):
                speech_frames += 1
        
        # If more than half of frames are detected as speech, consider it speech activity
        return speech_frames > len(frames) / 2

    def stop(self):
        """Stop recording"""
        if not self.recording:
            logger.warning("Recording already stopped")
            return
            
        logger.info("Stopping recording...")
        self.recording = False
        
        # Wait for threads to end
        if hasattr(self, 'record_thread'):
            self.record_thread.join(timeout=1)
        if hasattr(self, 'transcribe_thread'):
            self.transcribe_thread.join(timeout=1)
            
        logger.info("Recording stopped")
