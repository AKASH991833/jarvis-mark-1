"""Voice input: mic recording with simple voice detection + speech-to-text."""
import io, wave, time
import numpy as np
from . import config, bus

RATE = 16000
FRAME = 480  # 30 ms

def record(max_wait=8.0, max_len=20.0, silence_end=1.1):
    """Return WAV bytes of one spoken phrase, or None if nobody spoke."""
    import sounddevice as sd
    frames, started, quiet = [], False, 0.0
    t0 = time.time()
    with sd.InputStream(samplerate=RATE, channels=1, dtype="int16", blocksize=FRAME) as st:
        # measure room noise for 0.4 s
        noise = [np.abs(st.read(FRAME)[0]).mean() for _ in range(13)]
        thr = max(350.0, float(np.mean(noise)) * 3.0)
        loud = 0
        while True:
            data, _ = st.read(FRAME)
            level = float(np.abs(data).mean())
            bus.level(min(1.0, level / 6000.0))
            now = time.time()
            if not started:
                loud = loud + 1 if level > thr else 0
                frames.append(data.copy())
                frames = frames[-10:]
                if loud >= 3:
                    started, t_start = True, now
                elif now - t0 > max_wait:
                    return None
            else:
                frames.append(data.copy())
                quiet = quiet + FRAME / RATE if level < thr else 0.0
                if quiet >= silence_end or now - t_start > max_len:
                    break
    audio = np.concatenate(frames)
    if len(audio) < RATE * 0.5:
        return None
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes(audio.tobytes())
    return buf.getvalue()

_local = None

def _stt_groq(wav):
    import requests
    r = requests.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
        files={"file": ("a.wav", wav, "audio/wav")},
        data={"model": "whisper-large-v3-turbo", "temperature": "0",
              "prompt": "Hinglish: Hindi aur English mix. Jarvis, open Chrome, YouTube, folder, file."},
        timeout=30)
    r.raise_for_status()
    return r.json().get("text", "").strip()

def _stt_local(wav):
    global _local
    if _local is None:
        from faster_whisper import WhisperModel
        _local = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = _local.transcribe(io.BytesIO(wav), beam_size=1, vad_filter=True,
                                initial_prompt="Hinglish: Hindi aur English mix.")
    return " ".join(s.text for s in segs).strip()

def _stt_gemini(wav, client):
    from google.genai import types
    prompt = ("Transcribe this audio exactly. The speaker mixes Hindi and English (Hinglish). "
              "Write Hindi words in Devanagari and English words in English. "
              "Output ONLY the transcript. If there is no clear human speech, output nothing.")
    last = None
    for m in config.MODEL_CHAIN[:5]:
        try:
            r = client.models.generate_content(
                model=m, contents=[prompt, types.Part.from_bytes(data=wav, mime_type="audio/wav")])
            return (r.text or "").strip()
        except Exception as e:
            last = e
    raise last

def transcribe(wav, client):
    eng = config.STT_ENGINE
    order = {"groq": ["groq"], "gemini": ["gemini"], "local": ["local"],
             "auto": (["groq"] if config.GROQ_API_KEY else []) + ["gemini", "local"]}.get(eng, ["gemini"])
    err = None
    for e in order:
        try:
            if e == "groq": return _stt_groq(wav)
            if e == "gemini": return _stt_gemini(wav, client)
            if e == "local": return _stt_local(wav)
        except Exception as ex:
            err = ex
    print(f"[hearing problem: {err}]")
    return ""
