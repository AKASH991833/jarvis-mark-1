import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

def _b(name, default="false"):
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "y", "on")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()   # free Groq chat brain (fallback)
OPENCODE_MODEL = os.getenv("OPENCODE_MODEL", "opencode/deepseek-v4.1-flash-free").strip()  # free model id rotates: check `opencode models`
# Fallback order of brains when backend=auto. Keep 'ollama' last: it is local, nothing leaves the PC.
BRAIN_CHAIN = [b.strip().lower() for b in os.getenv("BRAIN_CHAIN", "gemini,groq,opencode,ollama").split(",") if b.strip()]
STT_ENGINE = os.getenv("STT_ENGINE", "auto").strip().lower()
VOICE = os.getenv("VOICE", "hi-IN-MadhurNeural").strip()
VOICE_RATE = os.getenv("VOICE_RATE", "+5%").strip()
USER_NAME = os.getenv("USER_NAME", "Akash").strip()
WAKE_WORD_ENABLED = _b("WAKE_WORD_ENABLED", "false")
WAKE_WORD = os.getenv("WAKE_WORD", "jarvis").strip().lower()
TTS_ENGINE = os.getenv("TTS_ENGINE", "auto").strip().lower()
GEMINI_VOICE = os.getenv("GEMINI_VOICE", "Alnilam").strip()   # deep "Jarvis-like" voice; alternatives: Achird, Algieba, Charon, Orus
GEMINI_TTS_MODEL = os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts").strip()
WEATHER_CITY = os.getenv("WEATHER_CITY", "Mumbai").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest").strip()
# Fallback chain: known-stable models first (older names can be closed to new keys), newer ones after. First one that works is used.
MODEL_CHAIN = list(dict.fromkeys([GEMINI_MODEL, "gemini-flash-latest", "gemini-flash-lite-latest", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.6-flash"]))
TTS_CHAIN = list(dict.fromkeys([GEMINI_TTS_MODEL, "gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts", "gemini-3.1-flash-tts-preview"]))
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "").strip()
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()

DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
MEMORY_FILE = DATA_DIR / "memory.json"
LOG_FILE = DATA_DIR / "jarvis.log"
SHOT_DIR = Path.home() / "Pictures" / "Jarvis"

def key_ok():
    return bool(GEMINI_API_KEY) and "PASTE" not in GEMINI_API_KEY
