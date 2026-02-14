import os
from dotenv import load_dotenv
import logging

load_dotenv()

class Config:
    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    # Models
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "medium")
    LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:3b")
    VISION_MODEL = os.getenv("VISION_MODEL", "moondream2")
    USE_GPU = os.getenv("USE_GPU", "True").lower() == "true"
    CUDA_DEVICE = os.getenv("CUDA_DEVICE", "0")

    # Twilio (optional)
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

    # Database encryption
    DB_ENCRYPTION_PASSWORD = os.getenv("DB_ENCRYPTION_PASSWORD", "change_me")

    # Cloud offloading (opt-in)
    ENABLE_CLOUD = os.getenv("ENABLE_CLOUD", "False").lower() == "true"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")   # if using GPT-4
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "logs/assistant.log")

    @staticmethod
    def setup_logging():
        logging.basicConfig(
            level=getattr(logging, Config.LOG_LEVEL),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=[
                logging.FileHandler(Config.LOG_FILE),
                logging.StreamHandler()
            ]
        )
