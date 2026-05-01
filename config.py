import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")  # deprecated, kept for compatibility
LEMONFOX_API_KEY = os.getenv("LEMONFOX_API_KEY", "")
LEMONFOX_BASE_URL = os.getenv("LEMONFOX_BASE_URL", "https://api.lemonfox.ai/v1")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

# ASR
WHISPER_MODEL = "whisper-1"
ASR_LANGUAGE = "ja"

# Translation
TRANSLATE_MODEL = "deepseek-v4-pro"

# TTS (Edge TTS)
TTS_VOICE = "zh-CN-XiaoxiaoNeural"
TTS_RATE = "+10%"
TTS_PROXY = os.getenv("TTS_PROXY", "http://127.0.0.1:10808")

# Mixer
DEFAULT_DELAY = 0.3          # Chinese TTS starts at segment start + delay (seconds)
DEFAULT_DUCK_RATIO = 1.0     # Original volume when ducked (0-1). 1.0 = no ducking
DEFAULT_CHINESE_VOLUME = 0.10
FADE_IN_MS = 50
FADE_OUT_MS = 50
DUCK_FADE_MS = 100           # Time to fade down/up original audio
