"""Voice output. First choice: Gemini TTS voice 'Achird' (free tier, same key).
Automatic fallback: edge-tts hi-IN-MadhurNeural (free, unlimited, very natural Hindi)."""
import asyncio, os, tempfile, threading, re, time, wave
from . import config, bus

_lock = threading.Lock()
_pg = None
_client = None
_gem_off_until = 0.0
last_engine = ""

def set_client(c):
    global _client
    _client = c

def _clean(text):
    text = re.sub(r"[*_`#>]+", "", text)
    text = re.sub(r"https?://\S+", "link", text)
    return text.strip()

def _init_audio():
    global _pg
    if _pg is None:
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        import pygame
        pygame.mixer.init()
        _pg = pygame
    return _pg

def _gemini_tts(text, path):
    from google.genai import types
    cfg = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=config.GEMINI_VOICE))))
    r = _client.models.generate_content(model=config.GEMINI_TTS_MODEL, contents=text, config=cfg)
    pcm = r.candidates[0].content.parts[0].inline_data.data
    if not pcm:
        raise RuntimeError("empty audio")
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)

async def _edge(text, path):
    import edge_tts
    await edge_tts.Communicate(text, config.VOICE, rate=config.VOICE_RATE).save(path)

def _make_audio(text):
    global _gem_off_until, last_engine
    tmp = tempfile.gettempdir()
    if config.TTS_ENGINE in ("auto", "gemini") and _client is not None and time.time() >= _gem_off_until:
        p = os.path.join(tmp, f"jarvis_{os.getpid()}.wav")
        try:
            _gemini_tts(text, p); last_engine = "gemini-" + config.GEMINI_VOICE; bus.info["voice"] = "GEMINI " + config.GEMINI_VOICE.upper(); return p
        except Exception as e:
            # free-tier limit / API change: skip Gemini voice for 10 minutes, use edge-tts
            _gem_off_until = time.time() + 600
            bus.log("info", f"Gemini voice busy, using backup voice for a while ({str(e)[:80]})")
    p = os.path.join(tmp, f"jarvis_{os.getpid()}.mp3")
    asyncio.run(_edge(text, p)); last_engine = "edge-" + config.VOICE
    return p

def speak(text, show=True):
    text = _clean(text)
    if not text:
        return
    if show:
        bus.log("jarvis", text)
    with _lock:
        try:
            bus.state("speaking")
            path = _make_audio(text)
            pg = _init_audio()
            pg.mixer.music.load(path)
            pg.mixer.music.play()
            while pg.mixer.music.get_busy():
                pg.time.wait(80)
            pg.mixer.music.unload()
        except Exception as e:
            bus.log("info", f"voice problem: {e}")
        finally:
            bus.state("idle")
