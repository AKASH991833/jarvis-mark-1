"""Telegram remote control, proactive agent, voice gate."""
import os, re, io, json, time, wave, threading, datetime
from pathlib import Path
from . import config, bus

DATA = config.DATA_DIR
PRO = DATA / "proactive.json"
def _pc():
    from . import pc
    return pc
def _say(t):
    try: _pc().notify(t)
    except Exception: print(t)
def _jl(p, d):
    try: return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception: return d
def _js(p, v): Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")

# ============================================================== 1. TELEGRAM REMOTE
_brain = {"ask": None}
_tg_local = threading.local()
_ask_lock = threading.Lock()
TOKEN = lambda: os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OWNER = lambda: os.getenv("TELEGRAM_CHAT_ID", "").strip()
HELP = ("Jarvis remote commands:\n/status - PC health\n/shot - screenshot\n/lock - lock PC\n/shutdown - shut down (asks YES)\n"
        "/open <app or website>\n/download <url> (asks YES)\n/say <text> - Jarvis speaks on PC\n/note <text>\n/ask <anything> - any Jarvis command (dangerous ones ask YES here)\n/help")

def _api(method, **kw):
    import requests
    return requests.post(f"https://api.telegram.org/bot{TOKEN()}/{method}", data=kw, timeout=60).json()
def _send(chat, text):
    try: _api("sendMessage", chat_id=chat, text=text[:3900])
    except Exception: pass
def _wait_yes(chat, question):
    _send(chat, question + " Reply YES or NO.")
    end = time.time() + 90
    while time.time() < end:
        for u in _poll(1):
            m = u.get("message", {})
            if str(m.get("chat", {}).get("id")) == chat:
                t = (m.get("text") or "").strip().lower()
                if t in ("yes", "y", "haan", "ha"): return True
                if t in ("no", "n", "nahi", "cancel"): return False
    _send(chat, "No answer, cancelled."); return False
_off = [0]
def _poll(timeout=30):
    try:
        r = _api("getUpdates", offset=_off[0], timeout=timeout)
        ups = r.get("result", [])
        if ups: _off[0] = ups[-1]["update_id"] + 1
        return ups
    except Exception:
        time.sleep(5); return []

def handle_command(chat, text):
    """Runs one remote command. Returns reply text."""
    pc = _pc(); tools = {t.__name__: t for t in pc.TOOLS}
    cmd, _, arg = text.strip().partition(" "); cmd = cmd.lower().split("@")[0]; arg = arg.strip()
    _tg_local.confirm = lambda q: _wait_yes(chat, q)
    try:
        if cmd in ("/start", "/help"): return HELP
        if cmd == "/status": return tools["watchdog_status"]() + "\n" + tools["top_processes"](4)
        if cmd == "/shot":
            r = tools["take_screenshot"]()
            m = re.search(r"(/|[A-Za-z]:\\)[^\n]*\.png", str(r))
            if m and Path(m.group(0)).exists():
                import requests
                with open(m.group(0), "rb") as f:
                    requests.post(f"https://api.telegram.org/bot{TOKEN()}/sendPhoto", data={"chat_id": chat}, files={"photo": f}, timeout=60)
                return "Screenshot sent."
            return str(r)
        if cmd == "/lock": return tools["power"]("lock") if _wait_yes(chat, "Lock the PC?") else "Cancelled."
        if cmd == "/shutdown": return tools["power"]("shutdown")
        if cmd == "/open": return tools["open_app"](arg) if arg else "Usage: /open chrome"
        if cmd == "/download": return tools["download_file"](arg) if arg else "Usage: /download <url>"
        if cmd == "/say": _say(arg); return "Said on PC."
        if cmd == "/note": return tools["add_note"](arg)
        if cmd == "/ask":
            if not _brain["ask"]: return "Brain not ready yet."
            with _ask_lock: return _brain["ask"](arg) or "(no reply)"
        return "Unknown command. Send /help"
    except Exception as e:
        return f"Error: {e}"
    finally:
        _tg_local.confirm = None

def _tg_loop():
    notified = set()
    while TOKEN():
        for u in _poll(30):
            m = u.get("message") or {}
            chat = str(m.get("chat", {}).get("id", "")); text = m.get("text") or ""
            if not chat or not text: continue
            if not OWNER():
                if chat not in notified:
                    notified.add(chat)
                    _send(chat, f"Jarvis here. Your chat id is {chat}. To make me obey only YOU, put TELEGRAM_CHAT_ID={chat} in the .env file and restart Jarvis. Commands are disabled until then.")
                continue
            if chat != OWNER(): continue          # strangers are ignored
            bus.log("info", "Telegram: " + text[:60])
            _send(chat, handle_command(chat, text))
_tg_on = [False]
def start_telegram():
    if _tg_on[0] or not TOKEN(): return
    _tg_on[0] = True; threading.Thread(target=_tg_loop, daemon=True).start()
    # route confirmations asked by tools during a remote command to Telegram
    pc = _pc(); orig = pc.confirm
    pc.confirm = lambda q: (_tg_local.confirm(q) if getattr(_tg_local, "confirm", None) else orig(q))

def telegram_status() -> str:
    """Say whether Telegram remote control is set up and what is missing."""
    if not TOKEN(): return "Telegram off hai. BotFather se bot banao, token .env me TELEGRAM_BOT_TOKEN= ke baad daalo (README step)."
    if not OWNER(): return "Token mil gaya. Ab bot ko Telegram me koi message bhejo, wo tumhara chat id batayega; use .env me TELEGRAM_CHAT_ID= ke baad daalo."
    return "Telegram remote control ON, sirf tumhare chat ke liye."

# ============================================================== 2. PROACTIVE AGENT
def _pd(): 
    d = _jl(PRO, {}); d.setdefault("recurring", []); d.setdefault("intentions", []); d.setdefault("fired", {}); return d
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
def add_recurring_event(title: str, time_24h: str, days: str = "mon,tue,wed,thu,fri", app_or_url: str = "", note: str = "") -> str:
    """Set a recurring meeting/habit. 5 minutes before, Jarvis speaks a heads-up, opens the app or URL and reads the note. time_24h like 10:30, days like 'mon,wed'."""
    if not re.match(r"^\d{1,2}:\d{2}$", time_24h): return "Time 24h format me do, jaise 10:30."
    ds = [d for d in (x.strip().lower()[:3] for x in days.split(",")) if d in DAYS]
    if not ds: return "Days samajh nahi aaye (mon,tue,...)."
    d = _pd(); d["recurring"].append({"title": title, "time": time_24h.zfill(5), "days": ds, "open": app_or_url, "note": note}); _js(PRO, d)
    return f"Set: '{title}' {time_24h} par ({','.join(ds)}), 5 min pehle yaad dilaunga."
def list_recurring() -> str:
    """List recurring events and pending follow-ups."""
    d = _pd()
    r = [f"{i}. {e['title']} {e['time']} {','.join(e['days'])}" for i, e in enumerate(d["recurring"])]
    n = [f"{i}. {x['text']} (due {x['due']})" for i, x in enumerate(d["intentions"]) if not x["done"]]
    return "Recurring:\n" + ("\n".join(r) or "-") + "\nFollow-ups:\n" + ("\n".join(n) or "-")
def remove_recurring(index: int) -> str:
    """Remove a recurring event by its number from list_recurring."""
    d = _pd()
    if 0 <= index < len(d["recurring"]): e = d["recurring"].pop(index); _js(PRO, d); return f"'{e['title']}' hata diya."
    return "Wo number nahi mila."
def add_intention(text: str, hours_from_now: float = 24) -> str:
    """Remember something the user said he will do (e.g. 'kal subah email bhejna hai'). Jarvis nudges when it is due until it is marked done. Call this whenever he states an intention."""
    d = _pd(); due = (datetime.datetime.now() + datetime.timedelta(hours=hours_from_now)).strftime("%Y-%m-%d %H:%M")
    d["intentions"].append({"text": text, "due": due, "done": False, "nudges": 0, "last": ""}); _js(PRO, d)
    return f"Yaad rakh liya: '{text}', {due} par yaad dilaunga."
def mark_intention_done(text_contains: str) -> str:
    """Mark a remembered follow-up as done (matches by words)."""
    d = _pd(); n = 0
    for x in d["intentions"]:
        if not x["done"] and text_contains.lower() in x["text"].lower(): x["done"] = True; n += 1
    _js(PRO, d); return f"{n} follow-up done mark kiya."
def research_topic_summary(topic: str) -> str:
    """Give a short summary of a topic (Wikipedia + web). Used when the user is reading about something new; only suggests, never changes anything."""
    return _pc().wikipedia_summary(topic)

_tick_seen = {}
def _tick():
    now = datetime.datetime.now(); d = _pd(); changed = False
    for e in d["recurring"]:
        if DAYS[now.weekday()] not in e["days"]: continue
        h, m = map(int, e["time"].split(":")); t = now.replace(hour=h, minute=m, second=0, microsecond=0)
        lead = (t - now).total_seconds()
        key = f"{e['title']}-{now.date()}-{e['time']}"
        if 0 <= lead <= 5 * 60 and key not in d["fired"]:
            d["fired"][key] = 1; changed = True
            _say(f"Heads up {config.USER_NAME}: {e['title']} {e['time']} par hai, 5 minute me." + (f" {e['note']}" if e.get("note") else ""))
            if e.get("open"):
                try:
                    pc = _pc(); (pc.open_website if e["open"].startswith("http") else pc.open_app)(e["open"])
                except Exception: pass
    for x in d["intentions"]:
        if x["done"] or x["nudges"] >= 3: continue
        due = datetime.datetime.strptime(x["due"], "%Y-%m-%d %H:%M")
        if now >= due and (not x["last"] or now - datetime.datetime.strptime(x["last"], "%Y-%m-%d %H:%M") > datetime.timedelta(hours=1)):
            x["nudges"] += 1; x["last"] = now.strftime("%Y-%m-%d %H:%M"); changed = True
            _say(f"Yaad dilana tha: {x['text']}. Ho gaya? Agar ho gaya to bolo 'done'.")
    if len(d["fired"]) > 200: d["fired"] = {}
    if changed: _js(PRO, d)

_topic = {"title": "", "since": 0, "offered": 0}
def _topic_watch():
    try: import pygetwindow as gw
    except Exception: return
    while True:
        time.sleep(60)
        try:
            w = gw.getActiveWindow(); t = (w.title if w else "") or ""
            if not re.search(r"(Chrome|Edge|Firefox)", t): continue
            t = re.sub(r"\s*[-\u2013\u2014]\s*(Google Chrome|Microsoft Edge|Mozilla Firefox).*$", "", t).strip()
            if t != _topic["title"]: _topic.update(title=t, since=time.time()); continue
            if time.time() - _topic["since"] > 120 and time.time() - _topic["offered"] > 1800 and len(t) > 12 and "youtube" not in t.lower() and "whatsapp" not in t.lower():
                _topic["offered"] = time.time()
                _say(f"Tum '{t[:50]}' padh rahe ho. Iska short summary chahiye? Bolo 'haan summary do'.")
                bus.info["suggest_topic"] = t
        except Exception: pass

def start_proactive():
    def loop():
        while True:
            try: _tick()
            except Exception: pass
            time.sleep(30)
    threading.Thread(target=loop, daemon=True).start()
    if os.getenv("PROACTIVE_BROWSING", "false").strip().lower() in ("1", "true", "yes", "on"):
        threading.Thread(target=_topic_watch, daemon=True).start()

# ============================================================== 3. VOICE GATE
PRINT = DATA / "voiceprint.json"
_gate = {"until": 0.0, "warned": 0.0}
def _mode(): return os.getenv("VOICE_GATE", "off").strip().lower()      # off | pin | voiceprint | both
def _feat(wav):
    import numpy as np
    with wave.open(io.BytesIO(wav)) as w: a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    if len(a) < 8000: return None
    a = a / (np.abs(a).max() + 1e-6); n = 512; fr = []
    for i in range(0, len(a) - n, n // 2):
        s = np.abs(np.fft.rfft(a[i:i + n] * np.hanning(n)))
        if s.mean() > 0.05: fr.append(np.log1p(np.array([b.mean() for b in np.array_split(s[:256], 32)])))
    if len(fr) < 5: return None
    v = np.mean(fr, axis=0); return (v - v.mean()) / (v.std() + 1e-6)
def _cos(a, b):
    import numpy as np
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
def enroll_voice() -> str:
    """Record 4 short phrases of the owner's voice to build a basic voiceprint (for VOICE_GATE=voiceprint or both)."""
    from . import listen
    import numpy as np
    vs = []
    for i in range(4):
        _say("Kuch bhi bolo, ek lambi line." if i == 0 else "Aur ek line bolo.")
        wav = listen.record(max_wait=8.0, max_len=8.0)
        f = _feat(wav) if wav else None
        if f is not None: vs.append(f)
    if len(vs) < 3: return "Awaaz kam record hui, dobara try karo shaant jagah par."
    m = np.mean(vs, axis=0); sims = [_cos(v, m) for v in vs]
    _js(PRINT, {"mean": m.tolist(), "min_self": min(sims)})
    return "Voiceprint save ho gaya (basic). Ab .env me VOICE_GATE=voiceprint ya both karo."
def _norm_digits(s):
    tr = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
          "teen": "3", "char": "4", "paanch": "5", "chhe": "6", "chheh": "6", "saat": "7", "aath": "8", "nau": "9", "shunya": "0", "ek": "1", "do": "2", "शून्य": "0", "एक": "1", "दो": "2", "तीन": "3", "चार": "4", "पांच": "5", "पाँच": "5", "छह": "6", "छः": "6", "सात": "7", "आठ": "8", "नौ": "9"}
    s = s.lower()
    for k, v in tr.items(): s = s.replace(k, v)
    s = s.translate(str.maketrans("०१२३४५६७८९", "0123456789"))
    return re.sub(r"\D", "", s)
def gate_check(text, wav):
    """Return (allowed, message_to_speak_or_None). wav=None means typed input (always allowed)."""
    m = _mode()
    if m == "off" or wav is None: return True, None
    low = text.lower()
    pin = os.getenv("VOICE_PIN", "").strip()
    now = time.time()
    # PIN unlock phrase: "jarvis unlock 1 2 3 4"
    if m in ("pin", "both") and pin and re.search(r"(unlock|अनलॉक|khol)", low):
        if _norm_digits(low) == pin or _norm_digits(low).endswith(pin):
            _gate["until"] = now + float(os.getenv("VOICE_GATE_MINUTES", "30")) * 60
            return False, "Unlock ho gaya. Ab tumhare commands chalenge."
        return False, "PIN galat hai."
    ok_print = True
    if m in ("voiceprint", "both"):
        pr = _jl(PRINT, None)
        if not pr: return True, None if now - _gate["warned"] < 600 else _warn("Voiceprint abhi bana nahi, gate band hai. 'enroll voice' bolo.")
        f = _feat(wav)
        thr = float(os.getenv("VOICE_GATE_THRESHOLD", "0.80"))
        ok_print = f is not None and _cos(f, __import__("numpy").array(pr["mean"])) >= thr
    if m == "voiceprint": return (ok_print, None if ok_print else _deny())
    if m == "both":
        if now < _gate["until"] and ok_print: return True, None
        return False, _deny()
    if m == "pin":
        if now < _gate["until"]: return True, None
        return False, _deny("Commands locked hain. Bolo 'jarvis unlock' aur apna PIN.")
    return True, None
def _warn(t): _gate["warned"] = time.time(); return t
def _deny(t="Ye awaaz pehchani nahi gayi. Command nahi chalaunga."):
    if time.time() - _gate["warned"] < 20: return None
    _gate["warned"] = time.time(); return t
def voice_gate_status() -> str:
    """Report the voice gate mode and whether a voiceprint exists."""
    return f"Voice gate mode: {_mode()}. Voiceprint: {'saved' if PRINT.exists() else 'not saved'}. PIN: {'set' if os.getenv('VOICE_PIN') else 'not set'}."

REMOTE_TOOLS = [telegram_status, add_recurring_event, list_recurring, remove_recurring, add_intention, mark_intention_done,
                research_topic_summary, enroll_voice, voice_gate_status]
def start_all(brain_ask=None):
    _brain["ask"] = brain_ask
    start_telegram(); start_proactive()
