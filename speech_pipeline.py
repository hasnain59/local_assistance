import logging
import tempfile
import wave
import asyncio
from pathlib import Path
import whisper
from piper import PiperVoice
import soundfile as sf
import numpy as np

logger = logging.getLogger(__name__)

class SpeechPipeline:
    def __init__(self):
        self.stt_model = None
        self.tts_voice = None
        self._load_models()
    
    def _load_models(self):
        """Load models with error handling."""
        try:
            # STT
            self.stt_model = whisper.load_model(Config.WHISPER_MODEL)
            logger.info(f"Loaded Whisper model: {Config.WHISPER_MODEL}")
        except Exception as e:
            logger.error(f"Failed to load Whisper: {e}")
            self.stt_model = None
        
        try:
            # TTS
            self.tts_voice = PiperVoice.load("en_US-lessac-medium")
            logger.info("Loaded Piper TTS voice")
        except Exception as e:
            logger.error(f"Failed to load Piper: {e}")
            self.tts_voice = None
    
    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe audio bytes to text."""
        if not self.stt_model:
            logger.error("STT model not available")
            return ""
        
        # Save bytes to temp file (Whisper expects file path or numpy)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        
        try:
            # Run whisper in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: self.stt_model.transcribe(tmp_path)
            )
            text = result.get("text", "").strip()
            logger.info(f"Transcribed: {text}")
            return text
        except Exception as e:
            logger.exception("Transcription failed")
            return ""
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    
    async def synthesize(self, text: str) -> bytes:
        """Convert text to speech audio bytes."""
        if not self.tts_voice:
            logger.error("TTS model not available")
            return b""
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.tts_voice.synthesize(text, tmp_path)
            )
            with open(tmp_path, "rb") as f:
                audio_bytes = f.read()
            return audio_bytes
        except Exception as e:
            logger.exception("TTS synthesis failed")
            return b""
        finally:
            Path(tmp_path).unlink(missing_ok=True)
